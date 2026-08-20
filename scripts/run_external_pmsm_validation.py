"""Run the frozen healthy-only external PMSM calibration and optional fault reveal.

The default run is intentionally valid with only the eight staged healthy records.
When frozen-code fault features are later added to the same feature table, passing
``--require-faults`` performs the one-time confirmatory reveal without changing the
fit, feature, calibration, or aggregation logic.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import warnings
from datetime import UTC, datetime
from pathlib import Path

import numpy as np
import pandas as pd
import sklearn
from sklearn.covariance import LedoitWolf
from sklearn.metrics import average_precision_score, roc_auc_score

from pmsm_sci.faults.baseline import feature_columns, healthy_relative_features
from pmsm_sci.faults.conformal import conformal_p_values, conformal_threshold
from pmsm_sci.faults.covariance import (
    entity_balanced_covariance,
    log_euclidean_entity_covariance,
    mahalanobis_scores,
    regularize_covariance,
    sample_covariance,
)
from pmsm_sci.faults.external_validation import (
    ADAPTATION_BLOCKS,
    ADAPTATION_LOAD_NM,
    ANALYSIS_BLOCKS,
    CALIBRATION_LOADS_NM,
    HEALTH_TEST_LOADS_NM,
    external_health_role,
    robust_reference_parameters,
    robust_transform,
    system_block_scores,
)
from pmsm_sci.faults.oneclass import (
    METHOD_SPECS,
    build_oneclass_estimator,
    independent_training_columns,
    oneclass_anomaly_scores,
    stratified_record_bootstrap_interval,
)
from pmsm_sci.faults.statistics import wilson_interval

SOURCE_MOTORS = ("1kW", "1.5kW", "3kW")
SOURCE_REFERENCE_BLOCKS = tuple(range(24))
SOURCE_BALANCED_BLOCKS = (0, 8, 15, 23)
PRIMARY_SEED = 20_260_820
COVARIANCE_METHODS = (
    "target_ledoit",
    "target_sample_covariance",
    "source_covariance",
    "entity_balanced_covariance",
    "log_euclidean_entity_covariance",
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--source-features",
        type=Path,
        default=Path("data/processed/kaist_current_features.csv.gz"),
    )
    parser.add_argument(
        "--external-features",
        type=Path,
        default=Path(
            "data/processed/external_dual_three_phase_health_features.csv.gz"
        ),
    )
    parser.add_argument(
        "--results-dir", type=Path, default=Path("results/external_pmsm_validation")
    )
    parser.add_argument("--alpha", type=float, default=0.05)
    parser.add_argument("--ridge-fraction", type=float, default=1e-3)
    parser.add_argument("--log-ridge-fraction", type=float, default=1e-2)
    parser.add_argument("--isolation-trees", type=int, default=500)
    parser.add_argument("--require-faults", action="store_true")
    return parser.parse_args()


def file_sha256(path: Path, chunk_size: int = 8 * 1024 * 1024) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        while chunk := stream.read(chunk_size):
            digest.update(chunk)
    return digest.hexdigest()


def external_roles(frame: pd.DataFrame) -> pd.Series:
    """Assign frozen roles without allowing a fault row into a health subset."""

    healthy = frame["is_healthy"].astype(bool)
    roles = pd.Series("fault_test", index=frame.index, dtype="object")
    roles.loc[healthy] = external_health_role(frame.loc[healthy])
    return roles


def source_reference_geometry(
    frame: pd.DataFrame, columns: list[str]
) -> tuple[np.ndarray, list[np.ndarray], np.ndarray, dict[str, object]]:
    """Fit source-only robust coordinates and equal-motor reference sets."""

    reference_blocks = {
        motor: list(SOURCE_REFERENCE_BLOCKS) for motor in SOURCE_MOTORS
    }
    transformed, parameters = healthy_relative_features(
        frame, columns, reference_blocks
    )
    covariances: list[np.ndarray] = []
    balanced_rows: list[np.ndarray] = []
    rows_by_motor: dict[str, int] = {}
    for motor in SOURCE_MOTORS:
        healthy = frame["is_healthy"].astype(bool)
        covariance_mask = (
            frame["motor_id"].eq(motor)
            & healthy
            & frame["block_id"].isin(SOURCE_REFERENCE_BLOCKS)
        ).to_numpy()
        balanced_mask = (
            frame["motor_id"].eq(motor)
            & healthy
            & frame["block_id"].isin(SOURCE_BALANCED_BLOCKS)
        ).to_numpy()
        covariance_values = transformed[covariance_mask]
        balanced_values = transformed[balanced_mask]
        if covariance_values.shape[0] != 360 or balanced_values.shape[0] != 60:
            raise AssertionError(
                f"Unexpected healthy source rows for {motor}: "
                f"{covariance_values.shape[0]} and {balanced_values.shape[0]}"
            )
        covariances.append(sample_covariance(covariance_values))
        balanced_rows.append(balanced_values)
        rows_by_motor[motor] = len(balanced_values)
    return (
        transformed,
        covariances,
        np.concatenate(balanced_rows, axis=0),
        {"parameters": parameters, "balanced_rows_by_motor": rows_by_motor},
    )


def covariance_scores(
    target_values: np.ndarray,
    adaptation_values: np.ndarray,
    source_covariances: list[np.ndarray],
    *,
    ridge_fraction: float,
    log_ridge_fraction: float,
) -> dict[str, np.ndarray]:
    target_covariance = sample_covariance(adaptation_values)
    zero = np.zeros(target_values.shape[1], dtype=np.float64)
    ledoit = LedoitWolf().fit(adaptation_values)
    matrices = {
        "target_sample_covariance": regularize_covariance(
            target_covariance, ridge_fraction
        ),
        "source_covariance": entity_balanced_covariance(
            source_covariances, ridge_fraction
        ),
        "entity_balanced_covariance": entity_balanced_covariance(
            [*source_covariances, target_covariance], ridge_fraction
        ),
        "log_euclidean_entity_covariance": log_euclidean_entity_covariance(
            [*source_covariances, target_covariance], log_ridge_fraction
        ),
    }
    scores = {
        name: mahalanobis_scores(target_values, matrix, zero)
        for name, matrix in matrices.items()
    }
    scores["target_ledoit"] = mahalanobis_scores(
        target_values, ledoit.covariance_, ledoit.location_
    )
    return scores


def oneclass_scores(
    target_values: np.ndarray,
    adaptation_values: np.ndarray,
    source_balanced_values: np.ndarray,
    columns: list[str],
    *,
    isolation_trees: int,
) -> tuple[dict[str, np.ndarray], dict[str, object]]:
    scores: dict[str, np.ndarray] = {}
    diagnostics: dict[str, object] = {}
    for spec in METHOD_SPECS:
        if spec.training_scope == "target":
            train = adaptation_values
        else:
            train = np.concatenate([source_balanced_values, adaptation_values], axis=0)
        retained = np.arange(train.shape[1], dtype=np.int64)
        if spec.estimator_kind == "min_cov_det":
            retained = independent_training_columns(train)
        estimator = build_oneclass_estimator(
            spec.estimator_kind,
            seed=PRIMARY_SEED,
            isolation_trees=isolation_trees,
        )
        with warnings.catch_warnings(record=True) as captured:
            warnings.simplefilter("always")
            estimator.fit(train[:, retained])
        scores[spec.name] = oneclass_anomaly_scores(
            estimator, spec.estimator_kind, target_values[:, retained]
        )
        retained_set = set(retained.tolist())
        diagnostics[spec.name] = {
            "training_scope": spec.training_scope,
            "estimator_kind": spec.estimator_kind,
            "training_rows": len(train),
            "retained_features": len(retained),
            "dropped_features": [
                column for index, column in enumerate(columns) if index not in retained_set
            ],
            "fit_warnings": sorted({str(item.message) for item in captured}),
        }
    return scores, diagnostics


def record_metadata(frame: pd.DataFrame) -> pd.DataFrame:
    fields = ["record_id", "load_nm", "is_healthy", "fault_turns", "fault_phase"]
    missing = set(fields).difference(frame.columns)
    if missing:
        raise ValueError(f"external features are missing metadata: {sorted(missing)}")
    metadata = frame[fields].drop_duplicates()
    if metadata["record_id"].duplicated().any():
        raise ValueError("A record has inconsistent health or fault metadata")
    return metadata


def evaluate_system_scores(
    frame: pd.DataFrame,
    window_scores: np.ndarray,
    *,
    method: str,
    alpha: float,
    require_faults: bool,
) -> tuple[dict[str, object], pd.DataFrame, pd.DataFrame]:
    blocks = system_block_scores(frame, window_scores)
    blocks = blocks.merge(record_metadata(frame), on=["record_id", "load_nm"])
    blocks["role"] = external_roles(blocks)
    calibration = blocks.loc[blocks["role"].eq("calibration"), "score"]
    health_test = blocks[blocks["role"].eq("health_test")]
    faults = blocks[blocks["role"].eq("fault_test")]
    if len(calibration) != 24 or len(health_test) != 32:
        raise AssertionError(
            f"Expected 24 calibration and 32 health-test blocks, got "
            f"{len(calibration)} and {len(health_test)}"
        )
    fault_records = faults["record_id"].nunique()
    if require_faults and (fault_records != 48 or len(faults) != 384):
        raise AssertionError(
            "The confirmatory reveal requires exactly 48 fault records and 384 blocks"
        )
    threshold = conformal_threshold(calibration, alpha)
    blocks["p_value"] = conformal_p_values(calibration, blocks["score"])
    blocks["alarm"] = blocks["p_value"] <= alpha
    blocks["method"] = method
    health_test = blocks[blocks["role"].eq("health_test")]
    faults = blocks[blocks["role"].eq("fault_test")]
    false_alarms = int(health_test["alarm"].sum())
    wilson_lower, wilson_upper = wilson_interval(false_alarms, len(health_test))
    per_load_far = health_test.groupby("load_nm", sort=True)["alarm"].mean()
    records = (
        faults.groupby(
            ["record_id", "load_nm", "fault_turns", "fault_phase"],
            observed=True,
            sort=True,
        )
        .agg(
            blocks=("alarm", "size"),
            alarms=("alarm", "sum"),
            block_alarm_rate=("alarm", "mean"),
            mean_score=("score", "mean"),
            max_score=("score", "max"),
        )
        .reset_index()
    )
    summary: dict[str, object] = {
        "method": method,
        "alpha": alpha,
        "threshold": threshold,
        "calibration_records": 3,
        "calibration_blocks": len(calibration),
        "health_test_records": 4,
        "health_test_blocks": len(health_test),
        "false_alarms": false_alarms,
        "healthy_block_false_alarm_rate": false_alarms / len(health_test),
        "descriptive_wilson_lower": wilson_lower,
        "descriptive_wilson_upper": wilson_upper,
        "max_heldout_load_false_alarm_rate": float(per_load_far.max()),
        "h1_empirical_pass": bool(
            wilson_upper <= 0.12 and per_load_far.max() <= 0.15
        ),
        "faults_available": bool(len(faults)),
        "fault_records": int(fault_records),
        "fault_blocks": len(faults),
        "fault_block_detection_rate": None,
        "fault_record_macro_detection_rate": None,
        "record_bootstrap_detection_ci_lower": None,
        "record_bootstrap_detection_ci_upper": None,
        "fault_record_any_alarm_rate": None,
        "block_auroc": None,
        "block_auprc": None,
    }
    if len(faults):
        labels = np.concatenate(
            [np.zeros(len(health_test), dtype=int), np.ones(len(faults), dtype=int)]
        )
        evaluation_scores = np.concatenate([health_test["score"], faults["score"]])
        ci_lower, ci_upper = stratified_record_bootstrap_interval(
            records,
            value_column="block_alarm_rate",
            strata_column="fault_turns",
            iterations=10_000,
            seed=711,
        )
        summary.update(
            {
                "fault_block_detection_rate": float(faults["alarm"].mean()),
                "fault_record_macro_detection_rate": float(
                    records["block_alarm_rate"].mean()
                ),
                "record_bootstrap_detection_ci_lower": ci_lower,
                "record_bootstrap_detection_ci_upper": ci_upper,
                "fault_record_any_alarm_rate": float((records["alarms"] > 0).mean()),
                "block_auroc": float(roc_auc_score(labels, evaluation_scores)),
                "block_auprc": float(
                    average_precision_score(labels, evaluation_scores)
                ),
            }
        )
    return summary, blocks, records


def main() -> None:
    args = parse_args()
    if not 0 < args.alpha < 1:
        raise ValueError("alpha must lie strictly between zero and one")
    source = pd.read_csv(args.source_features)
    external = pd.read_csv(args.external_features)
    columns = feature_columns(source, "scale_free")
    missing_features = set(columns).difference(external.columns)
    if missing_features:
        raise ValueError(f"external feature table is missing: {sorted(missing_features)}")
    if set(external["subsystem"].astype(str).unique()) != {"SubSys1", "SubSys2"}:
        raise ValueError("The external table must contain both three-phase subsystems")
    if set(external.loc[external["is_healthy"].astype(bool), "load_nm"].astype(int)) != {
        0,
        5,
        10,
        15,
        20,
        25,
        30,
        35,
    }:
        raise ValueError("The staged external health loads are incomplete")

    _, source_covariances, source_balanced, source_diagnostics = (
        source_reference_geometry(source, columns)
    )
    method_window_scores = {
        method: np.full(len(external), np.nan, dtype=np.float64)
        for method in (*COVARIANCE_METHODS, *(spec.name for spec in METHOD_SPECS))
    }
    subsystem_references: dict[str, object] = {}
    oneclass_diagnostics: dict[str, object] = {}
    for subsystem in ("SubSys1", "SubSys2"):
        mask = external["subsystem"].astype(str).eq(subsystem).to_numpy()
        target_frame = external.loc[mask]
        target_raw = target_frame[columns].to_numpy(dtype=np.float64)
        adaptation = (
            target_frame["is_healthy"].astype(bool)
            & target_frame["load_nm"].astype(int).eq(ADAPTATION_LOAD_NM)
            & target_frame["block_id"].astype(int).isin(ADAPTATION_BLOCKS)
        ).to_numpy()
        if adaptation.sum() != 60:
            raise AssertionError(
                f"Subsystem {subsystem} must have 60 target adaptation windows"
            )
        center, scale = robust_reference_parameters(target_raw[adaptation])
        target_values = robust_transform(target_raw, center, scale)
        adaptation_values = target_values[adaptation]
        subsystem_references[str(subsystem)] = {
            "center": center.tolist(),
            "scale": scale.tolist(),
            "adaptation_rows": int(adaptation.sum()),
            "adaptation_load_nm": ADAPTATION_LOAD_NM,
            "adaptation_blocks": list(ADAPTATION_BLOCKS),
        }
        cov_scores = covariance_scores(
            target_values,
            adaptation_values,
            source_covariances,
            ridge_fraction=args.ridge_fraction,
            log_ridge_fraction=args.log_ridge_fraction,
        )
        oc_scores, diagnostics = oneclass_scores(
            target_values,
            adaptation_values,
            source_balanced,
            columns,
            isolation_trees=args.isolation_trees,
        )
        oneclass_diagnostics[str(subsystem)] = diagnostics
        for method, scores in {**cov_scores, **oc_scores}.items():
            method_window_scores[method][mask] = scores

    args.results_dir.mkdir(parents=True, exist_ok=True)
    summaries: list[dict[str, object]] = []
    for method, scores in method_window_scores.items():
        if not np.isfinite(scores).all():
            raise FloatingPointError(f"{method} has unassigned or non-finite scores")
        summary, blocks, records = evaluate_system_scores(
            external,
            scores,
            method=method,
            alpha=args.alpha,
            require_faults=args.require_faults,
        )
        method_dir = args.results_dir / method
        method_dir.mkdir(parents=True, exist_ok=True)
        blocks.to_csv(method_dir / "system_block_predictions.csv", index=False)
        records.to_csv(method_dir / "fault_record_summary.csv", index=False)
        (method_dir / "summary.json").write_text(
            json.dumps(summary, indent=2), encoding="utf-8"
        )
        summaries.append(summary)
        print(
            f"{method}: health FAR {summary['false_alarms']}/32, "
            f"faults available={summary['faults_available']}"
        )
    pd.DataFrame(summaries).to_csv(args.results_dir / "aggregate_summary.csv", index=False)
    metadata = {
        "created_utc": datetime.now(UTC).isoformat(),
        "source_features": str(args.source_features.resolve()),
        "source_features_sha256": file_sha256(args.source_features),
        "external_features": str(args.external_features.resolve()),
        "external_features_sha256": file_sha256(args.external_features),
        "scikit_learn": sklearn.__version__,
        "feature_arm": "scale_free",
        "feature_columns": columns,
        "analysis_time_seconds": [12, 36],
        "window_seconds": 0.2,
        "block_seconds": 3.0,
        "block_score": "subsystem window maximum, followed by system maximum",
        "source_motors": list(SOURCE_MOTORS),
        "source_covariance_blocks": list(SOURCE_REFERENCE_BLOCKS),
        "source_balanced_blocks": list(SOURCE_BALANCED_BLOCKS),
        "external_adaptation_load_nm": ADAPTATION_LOAD_NM,
        "external_adaptation_blocks": list(ADAPTATION_BLOCKS),
        "external_calibration_load_nm": list(CALIBRATION_LOADS_NM),
        "external_health_test_load_nm": list(HEALTH_TEST_LOADS_NM),
        "analysis_blocks": list(ANALYSIS_BLOCKS),
        "alpha": args.alpha,
        "ridge_fraction": args.ridge_fraction,
        "log_ridge_fraction": args.log_ridge_fraction,
        "primary_seed": PRIMARY_SEED,
        "fault_reveal_required": args.require_faults,
        "source_diagnostics": source_diagnostics,
        "subsystem_references": subsystem_references,
        "oneclass_diagnostics": oneclass_diagnostics,
        "inference_boundary": (
            "Calibration and test blocks are ordered within a few load records; "
            "p-values and Wilson intervals are empirical and descriptive, not an "
            "arbitrary-dependence coverage guarantee."
        ),
    }
    (args.results_dir / "run_metadata.json").write_text(
        json.dumps(metadata, indent=2), encoding="utf-8"
    )


if __name__ == "__main__":
    main()
