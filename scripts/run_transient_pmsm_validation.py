"""Run the frozen leave-one-record-out transient PMSM stress test."""

from __future__ import annotations

import argparse
import hashlib
import json
import warnings
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

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
    robust_reference_parameters,
    robust_transform,
)
from pmsm_sci.faults.oneclass import (
    METHOD_SPECS,
    build_oneclass_estimator,
    independent_training_columns,
    oneclass_anomaly_scores,
)
from pmsm_sci.faults.transient_external import record_disjoint_split

SOURCE_MOTORS = ("1kW", "1.5kW", "3kW")
SOURCE_REFERENCE_BLOCKS = tuple(range(24))
PRIMARY_SEED = 20_260_820
SENSITIVITY_SEEDS = (20_260_820, 1201, 2402, 3603, 4804)
ALPHA = 0.05
MINIMUM_CALIBRATION_WINDOWS = 19
ARITHMETIC_RIDGE = 0.001
LOG_RIDGE = 0.01
ISOLATION_TREES = 500
BOOTSTRAP_REPLICATES = 10_000
BOOTSTRAP_SEED = 20_260_821
SPLIT_SALT = "20260821"
STOCHASTIC_METHODS = {
    "target_isolation_forest",
    "source_target_isolation_forest",
    "target_min_cov_det",
    "source_target_min_cov_det",
}
TRANSFER_PAIRS = (
    ("entity_balanced_covariance", "target_sample_covariance", "arithmetic_covariance"),
    (
        "log_euclidean_entity_covariance",
        "target_log_covariance",
        "log_euclidean_covariance",
    ),
    ("source_target_ocsvm_rbf", "target_ocsvm_rbf", "ocsvm_rbf"),
    (
        "source_target_isolation_forest",
        "target_isolation_forest",
        "isolation_forest",
    ),
    ("source_target_min_cov_det", "target_min_cov_det", "min_cov_det"),
)


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        while chunk := stream.read(8 * 1024 * 1024):
            digest.update(chunk)
    return digest.hexdigest()


def common_feature_columns(source: pd.DataFrame, target: pd.DataFrame) -> list[str]:
    """Freeze the common scale-free arm with unobservable zero sequence removed."""

    columns = [
        column
        for column in feature_columns(source, "scale_free")
        if column != "zero_sequence_ratio"
    ]
    missing = sorted(set(columns).difference(target.columns))
    if missing:
        raise ValueError(f"Target feature table is missing common features: {missing}")
    if "zero_sequence_ratio" in columns or len(columns) != 26:
        raise AssertionError(f"Expected 26 common observable features, got {len(columns)}")
    return columns


def source_reference_geometry(
    source: pd.DataFrame, columns: list[str]
) -> tuple[list[np.ndarray], list[np.ndarray], dict[str, object]]:
    """Return one healthy covariance and one transformed pool per KAIST motor."""

    references = {motor: list(SOURCE_REFERENCE_BLOCKS) for motor in SOURCE_MOTORS}
    transformed, parameters = healthy_relative_features(source, columns, references)
    covariances: list[np.ndarray] = []
    entity_rows: list[np.ndarray] = []
    row_counts: dict[str, int] = {}
    healthy = source["is_healthy"].astype(bool)
    for motor in SOURCE_MOTORS:
        mask = (
            source["motor_id"].eq(motor)
            & healthy
            & source["block_id"].isin(SOURCE_REFERENCE_BLOCKS)
        ).to_numpy()
        rows = transformed[mask]
        if rows.shape != (360, len(columns)):
            raise AssertionError(f"Unexpected 10 kHz source geometry for {motor}: {rows.shape}")
        entity_rows.append(rows)
        covariances.append(sample_covariance(rows))
        row_counts[motor] = len(rows)
    return covariances, entity_rows, {
        "robust_parameters": parameters,
        "rows_by_motor": row_counts,
    }


def evenly_spaced_rows(values: np.ndarray, count: int) -> np.ndarray:
    """Select a deterministic time-ordered subset without replacement."""

    data = np.asarray(values, dtype=np.float64)
    if data.ndim != 2 or count < 1 or count > len(data):
        raise ValueError("invalid row array or requested count")
    indices = np.floor(np.linspace(0, len(data), count, endpoint=False)).astype(int)
    if len(np.unique(indices)) != count:
        raise AssertionError("even row selection produced duplicates")
    return data[indices]


def covariance_scores(
    target_values: np.ndarray,
    target_fit: np.ndarray,
    source_covariances: list[np.ndarray],
) -> dict[str, np.ndarray]:
    target_covariance = sample_covariance(target_fit)
    zero = np.zeros(target_values.shape[1], dtype=np.float64)
    ledoit = LedoitWolf().fit(target_fit)
    matrices = {
        "target_sample_covariance": regularize_covariance(
            target_covariance, ARITHMETIC_RIDGE
        ),
        "source_covariance": entity_balanced_covariance(
            source_covariances, ARITHMETIC_RIDGE
        ),
        "entity_balanced_covariance": entity_balanced_covariance(
            [*source_covariances, target_covariance], ARITHMETIC_RIDGE
        ),
        "target_log_covariance": regularize_covariance(target_covariance, LOG_RIDGE),
        "log_euclidean_entity_covariance": log_euclidean_entity_covariance(
            [*source_covariances, target_covariance], LOG_RIDGE
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
    target_fit: np.ndarray,
    source_entities: list[np.ndarray],
    *,
    seed: int,
) -> tuple[dict[str, np.ndarray], dict[str, object]]:
    """Fit all frozen one-class methods with equal-row source/target entities."""

    balanced_count = min(len(target_fit), *(len(entity) for entity in source_entities))
    balanced = np.concatenate(
        [
            *(evenly_spaced_rows(entity, balanced_count) for entity in source_entities),
            evenly_spaced_rows(target_fit, balanced_count),
        ],
        axis=0,
    )
    scores: dict[str, np.ndarray] = {}
    diagnostics: dict[str, object] = {}
    for spec in METHOD_SPECS:
        if seed != PRIMARY_SEED and not spec.stochastic:
            continue
        train = target_fit if spec.training_scope == "target" else balanced
        retained = np.arange(train.shape[1], dtype=np.int64)
        if spec.estimator_kind == "min_cov_det":
            retained = independent_training_columns(train)
        estimator = build_oneclass_estimator(
            spec.estimator_kind,
            seed=seed,
            isolation_trees=ISOLATION_TREES,
        )
        with warnings.catch_warnings(record=True) as captured:
            warnings.simplefilter("always")
            estimator.fit(train[:, retained])
        scores[spec.name] = oneclass_anomaly_scores(
            estimator, spec.estimator_kind, target_values[:, retained]
        )
        diagnostics[spec.name] = {
            "training_scope": spec.training_scope,
            "training_rows": len(train),
            "balanced_rows_per_entity": balanced_count,
            "retained_features": len(retained),
            "fit_warnings": sorted({str(item.message) for item in captured}),
        }
    return scores, diagnostics


def fold_metrics(predictions: pd.DataFrame) -> dict[str, object]:
    """Summarize one method/seed/held-out-record prediction table."""

    health = predictions[predictions["segment"].eq("pre_fault")]
    primary_fault = predictions[
        predictions["segment"].eq("post_fault")
        & predictions["primary_post_window"].astype(bool)
    ]
    if health.empty or len(primary_fault) != 5:
        raise ValueError("A main fold requires health windows and five post-fault windows")
    labels = np.concatenate(
        [np.zeros(len(health), dtype=int), np.ones(len(primary_fault), dtype=int)]
    )
    scores = np.concatenate([health["score"], primary_fault["score"]])
    alarms = primary_fault[primary_fault["alarm"].astype(bool)]
    first_alarm = (
        float(alarms["relative_start_seconds"].min()) if not alarms.empty else np.nan
    )
    return {
        "healthy_windows": len(health),
        "false_alarms": int(health["alarm"].sum()),
        "healthy_window_far": float(health["alarm"].mean()),
        "primary_fault_windows": len(primary_fault),
        "detected_fault_windows": int(primary_fault["alarm"].sum()),
        "primary_fault_detection_rate": float(primary_fault["alarm"].mean()),
        "fault_record_any_alarm": bool(primary_fault["alarm"].any()),
        "first_alarm_delay_seconds": first_alarm,
        "first_alarm_right_censored_at_1s": bool(alarms.empty),
        "record_auroc": float(roc_auc_score(labels, scores)),
        "record_auprc": float(average_precision_score(labels, scores)),
    }


def equal_motor_mean(frame: pd.DataFrame, column: str) -> float:
    return float(frame.groupby("motor_id", sort=True)[column].mean().mean())


def summarize_folds(folds: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, object]] = []
    for (method, seed), group in folds.groupby(["method", "seed"], sort=True):
        rows.append(
            {
                "method": method,
                "seed": seed,
                "records": len(group),
                "motors": group["motor_id"].nunique(),
                "false_alarms": int(group["false_alarms"].sum()),
                "healthy_windows": int(group["healthy_windows"].sum()),
                "pooled_healthy_window_far": float(
                    group["false_alarms"].sum() / group["healthy_windows"].sum()
                ),
                "record_macro_healthy_far": float(group["healthy_window_far"].mean()),
                "record_macro_detection_rate": float(
                    group["primary_fault_detection_rate"].mean()
                ),
                "equal_motor_detection_rate": equal_motor_mean(
                    group, "primary_fault_detection_rate"
                ),
                "fault_record_any_alarm_rate": float(
                    group["fault_record_any_alarm"].mean()
                ),
                "right_censored_first_alarm_records": int(
                    group["first_alarm_right_censored_at_1s"].sum()
                ),
                "mean_record_auroc": float(group["record_auroc"].mean()),
                "mean_record_auprc": float(group["record_auprc"].mean()),
            }
        )
    return pd.DataFrame(rows)


def paired_stratified_bootstrap(
    paired: pd.DataFrame,
    *,
    iterations: int = BOOTSTRAP_REPLICATES,
    seed: int = BOOTSTRAP_SEED,
) -> tuple[float, float, float, float]:
    """Bootstrap whole paired records within motor-by-severity strata."""

    required = {"motor_id", "nominal_severity", "difference"}
    if missing := required.difference(paired.columns):
        raise ValueError(f"Paired table is missing: {sorted(missing)}")
    if iterations < 100:
        raise ValueError("iterations must be at least 100")
    groups = [
        group.reset_index(drop=True)
        for _, group in paired.groupby(
            ["motor_id", "nominal_severity"], sort=True, observed=True
        )
    ]
    if not groups or any(group.empty for group in groups):
        raise ValueError("Bootstrap strata must be non-empty")
    point = equal_motor_mean(paired, "difference")
    rng = np.random.default_rng(seed)
    draws = np.empty(iterations, dtype=np.float64)
    for iteration in range(iterations):
        sampled = pd.concat(
            [
                group.iloc[rng.integers(0, len(group), size=len(group))]
                for group in groups
            ],
            ignore_index=True,
        )
        draws[iteration] = equal_motor_mean(sampled, "difference")
    lower, upper = np.quantile(draws, [0.025, 0.975])
    non_positive = (np.count_nonzero(draws <= 0) + 1) / (iterations + 1)
    non_negative = (np.count_nonzero(draws >= 0) + 1) / (iterations + 1)
    p_value = min(1.0, 2.0 * min(non_positive, non_negative))
    return point, float(lower), float(upper), float(p_value)


def holm_adjust(p_values: np.ndarray) -> np.ndarray:
    values = np.asarray(p_values, dtype=np.float64)
    if values.ndim != 1 or values.size == 0 or np.any((values < 0) | (values > 1)):
        raise ValueError("p_values must be one non-empty vector in [0, 1]")
    order = np.argsort(values)
    adjusted_sorted = np.maximum.accumulate(
        (values.size - np.arange(values.size)) * values[order]
    )
    adjusted = np.empty_like(values)
    adjusted[order] = np.minimum(adjusted_sorted, 1.0)
    return adjusted


def transfer_comparisons(folds: pd.DataFrame) -> pd.DataFrame:
    primary = folds[folds["seed"].eq(PRIMARY_SEED)]
    rows: list[dict[str, object]] = []
    keys = ["record_id", "motor_id", "nominal_severity"]
    for candidate, target, family in TRANSFER_PAIRS:
        candidate_rows = primary[primary["method"].eq(candidate)][
            [*keys, "primary_fault_detection_rate"]
        ].rename(columns={"primary_fault_detection_rate": "candidate"})
        target_rows = primary[primary["method"].eq(target)][
            [*keys, "primary_fault_detection_rate"]
        ].rename(columns={"primary_fault_detection_rate": "target"})
        paired = candidate_rows.merge(target_rows, on=keys, validate="one_to_one")
        if len(paired) != primary["record_id"].nunique():
            raise AssertionError(f"Incomplete paired comparison for {family}")
        paired["difference"] = paired["candidate"] - paired["target"]
        point, lower, upper, p_value = paired_stratified_bootstrap(paired)
        rows.append(
            {
                "family": family,
                "candidate_method": candidate,
                "target_only_method": target,
                "records": len(paired),
                "equal_motor_detection_difference": point,
                "bootstrap_ci_lower": lower,
                "bootstrap_ci_upper": upper,
                "bootstrap_two_sided_p": p_value,
            }
        )
    result = pd.DataFrame(rows)
    result["holm_adjusted_p"] = holm_adjust(
        result["bootstrap_two_sided_p"].to_numpy()
    )
    return result


def evaluate(
    source: pd.DataFrame,
    target: pd.DataFrame,
    compatibility: pd.DataFrame,
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame, dict[str, Any]]:
    """Evaluate every frozen method and stochastic seed without fault-tuned fitting."""

    columns = common_feature_columns(source, target)
    source_covariances, source_entities, source_diagnostics = (
        source_reference_geometry(source, columns)
    )
    valid_records = compatibility.loc[
        compatibility["main_endpoint_compatible"].astype(bool), "record_id"
    ]
    target = target[target["record_id"].isin(valid_records)].reset_index(drop=True)
    if target.empty:
        raise ValueError("No main-compatible target records are available")
    fractions = (
        compatibility.groupby("motor_id", sort=True)["main_endpoint_compatible"]
        .mean()
        .to_dict()
    )
    if any(value < 0.8 for value in fractions.values()):
        raise RuntimeError(
            f"A motor fails the frozen 80% compatibility gate: {fractions}"
        )

    predictions: list[pd.DataFrame] = []
    fold_rows: list[dict[str, object]] = []
    split_rows: list[dict[str, object]] = []
    fit_diagnostics: dict[str, object] = {}
    for motor_id, motor in target.groupby("motor_id", sort=True):
        record_ids = sorted(motor["record_id"].unique())
        for heldout in record_ids:
            candidates = [record for record in record_ids if record != heldout]
            split = record_disjoint_split(heldout, candidates, salt=SPLIT_SALT)
            fit = (
                motor["record_id"].isin(split.fit)
                & motor["segment"].eq("pre_fault")
            ).to_numpy()
            calibration = (
                motor["record_id"].isin(split.calibration)
                & motor["segment"].eq("pre_fault")
            ).to_numpy()
            heldout_mask = motor["record_id"].eq(heldout).to_numpy()
            if fit.sum() < len(columns) + 1:
                raise RuntimeError(f"Insufficient target-fit rows for {heldout}: {fit.sum()}")
            if calibration.sum() < MINIMUM_CALIBRATION_WINDOWS:
                raise RuntimeError(
                    f"Insufficient calibration rows for {heldout}: {calibration.sum()}"
                )
            raw = motor[columns].to_numpy(dtype=np.float64)
            center, scale = robust_reference_parameters(raw[fit])
            values = robust_transform(raw, center, scale)
            target_fit = values[fit]
            for seed in SENSITIVITY_SEEDS:
                method_scores: dict[str, np.ndarray] = {}
                diagnostics: dict[str, object] = {}
                if seed == PRIMARY_SEED:
                    method_scores.update(
                        covariance_scores(values, target_fit, source_covariances)
                    )
                oneclass, oneclass_diagnostics = oneclass_scores(
                    values,
                    target_fit,
                    source_entities,
                    seed=seed,
                )
                method_scores.update(oneclass)
                diagnostics.update(oneclass_diagnostics)
                fit_diagnostics[f"{motor_id}|{heldout}|{seed}"] = diagnostics
                for method, scores in method_scores.items():
                    calibration_scores = scores[calibration]
                    threshold = conformal_threshold(calibration_scores, ALPHA)
                    selected = motor.loc[heldout_mask].copy()
                    selected["score"] = scores[heldout_mask]
                    selected["p_value"] = conformal_p_values(
                        calibration_scores, selected["score"]
                    )
                    selected["alarm"] = selected["p_value"] <= ALPHA
                    selected["threshold"] = threshold
                    selected["calibration_windows"] = int(calibration.sum())
                    selected["fit_records"] = "|".join(split.fit)
                    selected["calibration_records"] = "|".join(split.calibration)
                    selected["method"] = method
                    selected["seed"] = seed
                    predictions.append(selected)
                    summary = fold_metrics(selected)
                    identity = selected.iloc[0]
                    fold_rows.append(
                        {
                            "record_id": heldout,
                            "motor_id": motor_id,
                            "condition": identity["condition"],
                            "fault_turns": int(identity["fault_turns"]),
                            "nominal_severity": float(identity["nominal_severity"]),
                            "method": method,
                            "seed": seed,
                            "threshold": threshold,
                            "calibration_windows": int(calibration.sum()),
                            "fit_record_count": len(split.fit),
                            "calibration_record_count": len(split.calibration),
                            **summary,
                        }
                    )
            split_rows.append(
                {
                    "motor_id": motor_id,
                    "heldout_record_id": heldout,
                    "fit_records": "|".join(split.fit),
                    "calibration_records": "|".join(split.calibration),
                    "fit_windows": int(fit.sum()),
                    "calibration_windows": int(calibration.sum()),
                    "heldout_windows": int(heldout_mask.sum()),
                }
            )
    prediction_frame = pd.concat(predictions, ignore_index=True)
    folds = pd.DataFrame(fold_rows)
    splits = pd.DataFrame(split_rows)
    aggregates = summarize_folds(folds)
    comparisons = transfer_comparisons(folds)
    metadata: dict[str, Any] = {
        "created_utc": datetime.now(UTC).isoformat(),
        "feature_columns": columns,
        "feature_count": len(columns),
        "source_motors": list(SOURCE_MOTORS),
        "source_reference_blocks": list(SOURCE_REFERENCE_BLOCKS),
        "source_diagnostics": source_diagnostics,
        "target_compatible_fraction_by_motor": fractions,
        "split": "leave-one-record-out; whole-record hash fit/calibration",
        "split_salt": SPLIT_SALT,
        "alpha": ALPHA,
        "minimum_calibration_windows": MINIMUM_CALIBRATION_WINDOWS,
        "primary_post_fault_seconds": 1.0,
        "primary_post_fault_windows": 5,
        "arithmetic_ridge": ARITHMETIC_RIDGE,
        "log_ridge": LOG_RIDGE,
        "isolation_trees": ISOLATION_TREES,
        "primary_seed": PRIMARY_SEED,
        "sensitivity_seeds": list(SENSITIVITY_SEEDS),
        "bootstrap_replicates": BOOTSTRAP_REPLICATES,
        "bootstrap_seed": BOOTSTRAP_SEED,
        "fit_diagnostics": fit_diagnostics,
        "scikit_learn": sklearn.__version__,
        "target_fault_rows_used_for_fit": 0,
        "target_fault_rows_used_for_calibration": 0,
        "inference_boundary": (
            "Record-level intervals are descriptive for two physical motors; "
            "continuous windows and repeated conditions are not independent machines."
        ),
    }
    return prediction_frame, folds, aggregates, comparisons, {"splits": splits, **metadata}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--source-features",
        type=Path,
        default=Path("data/processed/kaist_current_features_10khz.csv.gz"),
    )
    parser.add_argument(
        "--target-features",
        type=Path,
        default=Path("data/processed/transient_pmsm_features.csv.gz"),
    )
    parser.add_argument(
        "--compatibility",
        type=Path,
        default=Path("results/transient_feature_build/record_compatibility.csv"),
    )
    parser.add_argument(
        "--results-dir",
        type=Path,
        default=Path("results/transient_pmsm_validation"),
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    source = pd.read_csv(args.source_features)
    target = pd.read_csv(args.target_features)
    compatibility = pd.read_csv(args.compatibility)
    predictions, folds, aggregates, comparisons, metadata = evaluate(
        source, target, compatibility
    )
    splits = metadata.pop("splits")
    metadata.update(
        source_features=str(args.source_features.resolve()),
        source_features_sha256=file_sha256(args.source_features),
        target_features=str(args.target_features.resolve()),
        target_features_sha256=file_sha256(args.target_features),
        compatibility_sha256=file_sha256(args.compatibility),
        predictions=len(predictions),
        fold_summaries=len(folds),
    )
    args.results_dir.mkdir(parents=True, exist_ok=True)
    predictions.to_csv(args.results_dir / "window_predictions.csv.gz", index=False)
    folds.to_csv(args.results_dir / "per_record_summary.csv", index=False)
    aggregates.to_csv(args.results_dir / "aggregate_summary.csv", index=False)
    comparisons.to_csv(args.results_dir / "transfer_comparisons.csv", index=False)
    splits.to_csv(args.results_dir / "record_splits.csv", index=False)
    (args.results_dir / "run_metadata.json").write_text(
        json.dumps(metadata, indent=2, sort_keys=True), encoding="utf-8"
    )
    primary = aggregates[aggregates["seed"].eq(PRIMARY_SEED)]
    print(primary[["method", "pooled_healthy_window_far", "equal_motor_detection_rate"]])


if __name__ == "__main__":
    main()
