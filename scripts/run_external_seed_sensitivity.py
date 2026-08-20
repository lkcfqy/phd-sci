"""Post-reveal five-seed robustness audit for frozen external stochastic baselines."""

from __future__ import annotations

import argparse
import json
import warnings
from datetime import UTC, datetime
from pathlib import Path

import numpy as np
import pandas as pd
import sklearn

from pmsm_sci.faults.baseline import feature_columns
from pmsm_sci.faults.external_validation import (
    ADAPTATION_BLOCKS,
    ADAPTATION_LOAD_NM,
    robust_reference_parameters,
    robust_transform,
)
from pmsm_sci.faults.oneclass import (
    METHOD_SPECS,
    OneClassSpec,
    build_oneclass_estimator,
    independent_training_columns,
    oneclass_anomaly_scores,
)

if __package__:
    from scripts.run_external_pmsm_validation import (
        evaluate_system_scores,
        file_sha256,
        source_reference_geometry,
    )
else:
    from run_external_pmsm_validation import (  # type: ignore[import-not-found]
        evaluate_system_scores,
        file_sha256,
        source_reference_geometry,
    )

SEEDS = (20_260_820, 1_201, 2_402, 3_603, 4_804)
PRIMARY_SEED = SEEDS[0]
ALPHA = 0.05
ISOLATION_TREES = 500
SUBSYSTEMS = ("SubSys1", "SubSys2")
EXPECTED_METHODS = (
    "target_isolation_forest",
    "source_target_isolation_forest",
    "target_min_cov_det",
    "source_target_min_cov_det",
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--frozen-results-dir",
        type=Path,
        default=Path("results/external_pmsm_validation"),
    )
    parser.add_argument(
        "--results-dir",
        type=Path,
        default=Path("results/external_seed_sensitivity"),
    )
    return parser.parse_args()


def sensitivity_specs() -> tuple[OneClassSpec, ...]:
    """Return exactly the four predeclared stochastic baseline variants."""

    selected = tuple(spec for spec in METHOD_SPECS if spec.name in EXPECTED_METHODS)
    if tuple(spec.name for spec in selected) != EXPECTED_METHODS:
        raise AssertionError("The frozen one-class specifications have changed")
    if any(not spec.stochastic for spec in selected):
        raise AssertionError("Every seed-sensitivity method must be stochastic")
    return selected


def load_frozen_inputs(
    frozen_results_dir: Path,
) -> tuple[pd.DataFrame, pd.DataFrame, list[str], dict[str, object]]:
    """Load feature tables only after their hashes match the frozen reveal metadata."""

    metadata_path = frozen_results_dir / "run_metadata.json"
    if not metadata_path.is_file():
        raise FileNotFoundError(metadata_path)
    metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
    if metadata.get("fault_reveal_required") is not True:
        raise ValueError("Seed sensitivity requires the completed frozen fault reveal")
    if float(metadata.get("alpha", np.nan)) != ALPHA:
        raise ValueError("Frozen alpha does not match the seed-sensitivity protocol")
    if int(metadata.get("primary_seed", -1)) != PRIMARY_SEED:
        raise ValueError("Frozen primary seed does not match the predeclared seed list")

    source_path = Path(str(metadata["source_features"]))
    external_path = Path(str(metadata["external_features"]))
    if file_sha256(source_path) != metadata["source_features_sha256"]:
        raise ValueError("Source feature hash differs from the frozen reveal")
    if file_sha256(external_path) != metadata["external_features_sha256"]:
        raise ValueError("External feature hash differs from the frozen reveal")
    source = pd.read_csv(source_path)
    external = pd.read_csv(external_path)
    columns = feature_columns(source, "scale_free")
    if columns != metadata["feature_columns"]:
        raise ValueError("Scale-free feature columns differ from the frozen reveal")
    if set(external["subsystem"].astype(str).unique()) != set(SUBSYSTEMS):
        raise ValueError("External features do not contain both frozen subsystems")
    if external.loc[~external["is_healthy"].astype(bool), "record_id"].nunique() != 48:
        raise ValueError("External feature table must contain all 48 revealed faults")
    return source, external, columns, metadata


def _training_values(
    spec: OneClassSpec,
    adaptation_values: np.ndarray,
    source_balanced_values: np.ndarray,
) -> np.ndarray:
    if spec.training_scope == "target":
        return adaptation_values
    if spec.training_scope == "source_target_balanced":
        return np.concatenate([source_balanced_values, adaptation_values], axis=0)
    raise ValueError(f"Unsupported training scope: {spec.training_scope}")


def score_all_seeds(
    source: pd.DataFrame,
    external: pd.DataFrame,
    columns: list[str],
) -> tuple[dict[tuple[str, int], np.ndarray], pd.DataFrame]:
    """Fit only the frozen stochastic estimators for every predefined seed."""

    _, _, source_balanced, _ = source_reference_geometry(source, columns)
    scores = {
        (spec.name, seed): np.full(len(external), np.nan, dtype=np.float64)
        for spec in sensitivity_specs()
        for seed in SEEDS
    }
    diagnostics: list[dict[str, object]] = []
    for subsystem in SUBSYSTEMS:
        mask = external["subsystem"].astype(str).eq(subsystem).to_numpy()
        target_frame = external.loc[mask]
        raw = target_frame[columns].to_numpy(dtype=np.float64)
        adaptation = (
            target_frame["is_healthy"].astype(bool)
            & target_frame["load_nm"].astype(int).eq(ADAPTATION_LOAD_NM)
            & target_frame["block_id"].astype(int).isin(ADAPTATION_BLOCKS)
        ).to_numpy()
        if adaptation.sum() != 60:
            raise AssertionError(f"{subsystem}: expected 60 adaptation windows")
        center, scale = robust_reference_parameters(raw[adaptation])
        target_values = robust_transform(raw, center, scale)
        adaptation_values = target_values[adaptation]

        for spec in sensitivity_specs():
            train = _training_values(spec, adaptation_values, source_balanced)
            retained = np.arange(train.shape[1], dtype=np.int64)
            if spec.estimator_kind == "min_cov_det":
                retained = independent_training_columns(train)
            retained_set = set(retained.tolist())
            for seed in SEEDS:
                estimator = build_oneclass_estimator(
                    spec.estimator_kind,
                    seed=seed,
                    isolation_trees=ISOLATION_TREES,
                )
                with warnings.catch_warnings(record=True) as captured:
                    warnings.simplefilter("always")
                    estimator.fit(train[:, retained])
                subsystem_scores = oneclass_anomaly_scores(
                    estimator,
                    spec.estimator_kind,
                    target_values[:, retained],
                )
                scores[(spec.name, seed)][mask] = subsystem_scores
                diagnostic: dict[str, object] = {
                    "method": spec.name,
                    "seed": seed,
                    "subsystem": subsystem,
                    "training_scope": spec.training_scope,
                    "training_rows": len(train),
                    "input_features": len(columns),
                    "retained_features": len(retained),
                    "dropped_features": [
                        column
                        for index, column in enumerate(columns)
                        if index not in retained_set
                    ],
                    "fit_warning_count": len(captured),
                    "fit_warnings": " | ".join(
                        sorted({str(item.message) for item in captured})
                    ),
                }
                if spec.estimator_kind == "min_cov_det":
                    covariance = np.asarray(estimator.covariance_, dtype=np.float64)
                    diagnostic.update(
                        {
                            "covariance_rank": int(np.linalg.matrix_rank(covariance)),
                            "covariance_dimension": int(covariance.shape[0]),
                            "covariance_condition_number": float(
                                np.linalg.cond(covariance)
                            ),
                        }
                    )
                diagnostics.append(diagnostic)
    if any(not np.isfinite(values).all() for values in scores.values()):
        raise FloatingPointError("At least one method-seed score vector is incomplete")
    return scores, pd.DataFrame(diagnostics)


def reconcile_primary_blocks(
    generated: pd.DataFrame,
    frozen: pd.DataFrame,
    *,
    method: str,
) -> dict[str, object]:
    """Require the primary seed to reproduce the frozen result exactly enough."""

    keys = ["record_id", "load_nm", "block_id"]
    generated_sorted = generated.sort_values(keys, ignore_index=True)
    frozen_sorted = frozen.sort_values(keys, ignore_index=True)
    if len(generated_sorted) != len(frozen_sorted):
        raise AssertionError(f"{method}: primary block row count differs")
    if not generated_sorted[keys].equals(frozen_sorted[keys]):
        raise AssertionError(f"{method}: primary record-block keys differ")
    score_difference = np.abs(
        generated_sorted["score"].to_numpy(dtype=np.float64)
        - frozen_sorted["score"].to_numpy(dtype=np.float64)
    )
    p_difference = np.abs(
        generated_sorted["p_value"].to_numpy(dtype=np.float64)
        - frozen_sorted["p_value"].to_numpy(dtype=np.float64)
    )
    alarm_mismatches = int(
        np.sum(
            generated_sorted["alarm"].astype(bool).to_numpy()
            != frozen_sorted["alarm"].astype(bool).to_numpy()
        )
    )
    max_score_difference = float(score_difference.max(initial=0.0))
    max_p_difference = float(p_difference.max(initial=0.0))
    passed = bool(
        np.allclose(
            generated_sorted["score"],
            frozen_sorted["score"],
            rtol=1e-12,
            atol=1e-12,
        )
        and np.allclose(
            generated_sorted["p_value"],
            frozen_sorted["p_value"],
            rtol=0,
            atol=0,
        )
        and alarm_mismatches == 0
    )
    if not passed:
        raise AssertionError(f"{method}: primary seed does not reproduce frozen scores")
    return {
        "method": method,
        "primary_seed": PRIMARY_SEED,
        "block_rows": len(generated_sorted),
        "max_absolute_score_difference": max_score_difference,
        "max_absolute_p_value_difference": max_p_difference,
        "alarm_mismatches": alarm_mismatches,
        "passed": passed,
    }


def summarize_seed_ranges(summary: pd.DataFrame) -> pd.DataFrame:
    """Summarize five-seed ranges without declaring a post-hoc pass threshold."""

    expected = pd.MultiIndex.from_product(
        [EXPECTED_METHODS, SEEDS], names=["method", "seed"]
    )
    actual = pd.MultiIndex.from_frame(summary[["method", "seed"]])
    if len(summary) != len(expected) or set(actual) != set(expected):
        raise ValueError("Summary must contain exactly four methods by five seeds")
    rows: list[dict[str, object]] = []
    for method in EXPECTED_METHODS:
        group = summary[summary["method"].eq(method)].copy()
        detection = group["fault_record_macro_detection_rate"].astype(float)
        far = group["healthy_block_false_alarm_rate"].astype(float)
        threshold = group["threshold"].astype(float)
        primary = group[group["seed"].eq(PRIMARY_SEED)].iloc[0]
        rows.append(
            {
                "method": method,
                "seeds": len(group),
                "primary_detection_rate": float(
                    primary["fault_record_macro_detection_rate"]
                ),
                "detection_mean": float(detection.mean()),
                "detection_sd": float(detection.std(ddof=1)),
                "detection_min": float(detection.min()),
                "detection_max": float(detection.max()),
                "detection_range": float(detection.max() - detection.min()),
                "max_abs_detection_change_from_primary": float(
                    np.max(np.abs(detection - float(primary["fault_record_macro_detection_rate"])))
                ),
                "primary_false_alarms": int(primary["false_alarms"]),
                "false_alarms_min": int(group["false_alarms"].min()),
                "false_alarms_max": int(group["false_alarms"].max()),
                "far_min": float(far.min()),
                "far_max": float(far.max()),
                "h1_pass_seeds": int(group["h1_empirical_pass"].astype(bool).sum()),
                "threshold_min": float(threshold.min()),
                "threshold_max": float(threshold.max()),
                "block_auroc_min": float(group["block_auroc"].min()),
                "block_auroc_max": float(group["block_auroc"].max()),
                "formal_stability_gate_predeclared": False,
            }
        )
    return pd.DataFrame(rows)


def main() -> None:
    args = parse_args()
    source, external, columns, frozen_metadata = load_frozen_inputs(
        args.frozen_results_dir
    )
    score_vectors, diagnostics = score_all_seeds(source, external, columns)
    summaries: list[dict[str, object]] = []
    block_parts: list[pd.DataFrame] = []
    record_parts: list[pd.DataFrame] = []
    reconciliation: list[dict[str, object]] = []

    for spec in sensitivity_specs():
        for seed in SEEDS:
            summary, blocks, records = evaluate_system_scores(
                external,
                score_vectors[(spec.name, seed)],
                method=spec.name,
                alpha=ALPHA,
                require_faults=True,
            )
            method_diagnostics = diagnostics[
                diagnostics["method"].eq(spec.name) & diagnostics["seed"].eq(seed)
            ]
            summary.update(
                {
                    "seed": seed,
                    "training_scope": spec.training_scope,
                    "estimator_kind": spec.estimator_kind,
                    "fit_warning_count": int(
                        method_diagnostics["fit_warning_count"].sum()
                    ),
                    "max_covariance_condition_number": (
                        float(method_diagnostics["covariance_condition_number"].max())
                        if "covariance_condition_number" in method_diagnostics
                        and method_diagnostics["covariance_condition_number"]
                        .notna()
                        .any()
                        else None
                    ),
                    "post_reveal_robustness_only": True,
                }
            )
            blocks = blocks.copy()
            records = records.copy()
            blocks["seed"] = seed
            records["method"] = spec.name
            records["seed"] = seed
            block_parts.append(blocks)
            record_parts.append(records)
            summaries.append(summary)
            print(
                f"{spec.name} seed={seed}: FAR {summary['false_alarms']}/32, "
                f"detection={summary['fault_record_macro_detection_rate']:.4f}"
            )

            if seed == PRIMARY_SEED:
                frozen_blocks = pd.read_csv(
                    args.frozen_results_dir
                    / spec.name
                    / "system_block_predictions.csv"
                )
                reconciliation.append(
                    reconcile_primary_blocks(
                        blocks,
                        frozen_blocks,
                        method=spec.name,
                    )
                )

    summary_frame = pd.DataFrame(summaries)
    block_frame = pd.concat(block_parts, ignore_index=True)
    record_frame = pd.concat(record_parts, ignore_index=True)
    ranges = summarize_seed_ranges(summary_frame)

    args.results_dir.mkdir(parents=True, exist_ok=True)
    summary_frame.to_csv(args.results_dir / "summary_by_seed.csv", index=False)
    ranges.to_csv(args.results_dir / "aggregate_seed_ranges.csv", index=False)
    block_frame.to_csv(
        args.results_dir / "block_predictions_by_seed.csv.gz",
        index=False,
        compression="gzip",
    )
    record_frame.to_csv(
        args.results_dir / "fault_record_summary_by_seed.csv", index=False
    )
    diagnostics.to_csv(args.results_dir / "fit_diagnostics.csv", index=False)
    pd.DataFrame(reconciliation).to_csv(
        args.results_dir / "primary_seed_reconciliation.csv", index=False
    )

    metadata = {
        "created_utc": datetime.now(UTC).isoformat(),
        "analysis_label": "post-reveal stochastic robustness sensitivity",
        "not_for_model_or_protocol_selection": True,
        "frozen_results_dir": str(args.frozen_results_dir.resolve()),
        "source_features_sha256": frozen_metadata["source_features_sha256"],
        "external_features_sha256": frozen_metadata["external_features_sha256"],
        "scikit_learn": sklearn.__version__,
        "methods": list(EXPECTED_METHODS),
        "seeds": list(SEEDS),
        "primary_seed": PRIMARY_SEED,
        "isolation_forest_trees": ISOLATION_TREES,
        "feature_arm": "scale_free",
        "alpha": ALPHA,
        "adaptation_load_nm": ADAPTATION_LOAD_NM,
        "adaptation_blocks": list(ADAPTATION_BLOCKS),
        "calibration_load_nm": frozen_metadata["external_calibration_load_nm"],
        "calibration_blocks_per_seed": 24,
        "health_test_load_nm": frozen_metadata["external_health_test_load_nm"],
        "health_test_blocks_per_seed": 32,
        "threshold_policy": (
            "For each random seed, mechanically recompute the split-conformal threshold "
            "from that model's scores on the same frozen 24 healthy calibration blocks "
            "at alpha=0.05. No fault score affects a threshold."
        ),
        "models_or_features_selected_from_sensitivity": False,
        "primary_seed_reproduced_frozen_result": True,
        "inference_boundary": (
            "This is a post-reveal robustness analysis on the same single external "
            "dual-three-phase motor. Seed ranges are descriptive and cannot convert the "
            "48 operating-condition records into independent motor replications."
        ),
        "stability_gate": (
            "No formal seed-stability pass/fail threshold was preregistered; report the "
            "full detection and FAR ranges without using them to change the main result."
        ),
    }
    (args.results_dir / "run_metadata.json").write_text(
        json.dumps(metadata, indent=2), encoding="utf-8"
    )


if __name__ == "__main__":
    main()
