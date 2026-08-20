"""Run strict healthy-only one-class baselines under the Paper 1 protocol."""

from __future__ import annotations

import argparse
import hashlib
import json
import warnings
from datetime import UTC, datetime
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
import sklearn
from sklearn.metrics import average_precision_score, roc_auc_score

from pmsm_sci.faults.baseline import (
    block_score_table,
    feature_columns,
    healthy_relative_features,
)
from pmsm_sci.faults.conformal import conformal_p_values, conformal_threshold
from pmsm_sci.faults.oneclass import (
    METHOD_SPECS,
    OneClassSpec,
    build_oneclass_estimator,
    independent_training_columns,
    motor_balanced_reference_mask,
    oneclass_anomaly_scores,
    stratified_record_bootstrap_interval,
)
from pmsm_sci.faults.splits import leave_one_motor_out, partition_contiguous_blocks
from pmsm_sci.faults.statistics import wilson_interval

PRIMARY_SEED = 20_260_820
SENSITIVITY_SEEDS = (20_260_820, 1_201, 2_402, 3_603, 4_804)
BOOTSTRAP_SEED = 711
BOOTSTRAP_ITERATIONS = 10_000


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--features",
        type=Path,
        default=Path("data/processed/kaist_current_features.csv.gz"),
    )
    parser.add_argument(
        "--results-dir", type=Path, default=Path("results/oneclass_baselines")
    )
    parser.add_argument("--alpha", type=float, default=0.05)
    parser.add_argument("--isolation-trees", type=int, default=500)
    parser.add_argument("--block-score-quantile", type=float, default=1.0)
    return parser.parse_args()


def protocol_partition():
    """Return the locked 4/1/20/1/14 target-health partition."""

    return partition_contiguous_blocks(
        40,
        adaptation_fraction=0.12,
        calibration_fraction=0.55,
        guard_blocks=1,
    )


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def evaluate_target_scores(
    target_frame: pd.DataFrame,
    scores: np.ndarray,
    *,
    method: str,
    seed: int,
    alpha: float,
    quantile: float,
) -> tuple[dict[str, object], pd.DataFrame, pd.DataFrame]:
    """Calibrate on disjoint healthy blocks and evaluate untouched health/faults."""

    split = protocol_partition()
    blocks = block_score_table(target_frame, scores, quantile=quantile)
    calibration_mask = (
        blocks["is_healthy"].astype(bool)
        & blocks["block_id"].isin(split.calibration)
    )
    calibration = blocks.loc[calibration_mask, "score"]
    if len(calibration) != 20:
        raise AssertionError(f"Expected 20 target calibration blocks, got {len(calibration)}")

    threshold = conformal_threshold(calibration, alpha)
    blocks["p_value"] = conformal_p_values(calibration, blocks["score"])
    blocks["alarm"] = blocks["p_value"] <= alpha
    blocks["method"] = method
    blocks["seed"] = seed

    healthy_test = blocks[
        blocks["is_healthy"].astype(bool) & blocks["block_id"].isin(split.test)
    ]
    faults = blocks[~blocks["is_healthy"].astype(bool)]
    if len(healthy_test) != 14 or len(faults) != 560:
        raise AssertionError("Unexpected number of healthy-test or fault blocks")
    evaluation = pd.concat([healthy_test, faults], ignore_index=True)
    labels = (~evaluation["is_healthy"].astype(bool)).astype(int)

    record_keys = [
        "motor_id",
        "record_id",
        "fault_family",
        "severity_percent",
        "is_healthy",
        "method",
        "seed",
    ]
    records = (
        evaluation.groupby(record_keys, observed=True, sort=True)
        .agg(
            blocks=("alarm", "size"),
            alarms=("alarm", "sum"),
            block_alarm_rate=("alarm", "mean"),
            mean_score=("score", "mean"),
            max_score=("score", "max"),
        )
        .reset_index()
    )
    fault_records = records[~records["is_healthy"].astype(bool)]
    summary: dict[str, object] = {
        "target_motor": str(target_frame["motor_id"].iloc[0]),
        "method": method,
        "seed": seed,
        "alpha": alpha,
        "threshold": threshold,
        "adaptation_blocks": len(split.adaptation),
        "calibration_blocks": len(calibration),
        "healthy_test_blocks": len(healthy_test),
        "fault_test_blocks": len(faults),
        "fault_records": len(fault_records),
        "false_alarms": int(healthy_test["alarm"].sum()),
        "false_alarm_rate": float(healthy_test["alarm"].mean()),
        "detected_fault_blocks": int(faults["alarm"].sum()),
        "detection_rate": float(faults["alarm"].mean()),
        "fault_record_macro_detection_rate": float(
            fault_records["block_alarm_rate"].mean()
        ),
        "fault_records_with_any_alarm": int((fault_records["alarms"] > 0).sum()),
        "fault_record_any_alarm_rate": float((fault_records["alarms"] > 0).mean()),
        "block_auroc": float(roc_auc_score(labels, evaluation["score"])),
        "block_auprc": float(average_precision_score(labels, evaluation["score"])),
    }
    return summary, blocks, records


def training_mask_for_spec(
    frame: pd.DataFrame,
    *,
    spec: OneClassSpec,
    target_motor: str,
    reference_blocks: dict[str, list[int]],
) -> np.ndarray:
    if spec.training_scope == "target":
        return (
            frame["motor_id"].eq(target_motor)
            & frame["is_healthy"].astype(bool)
            & frame["block_id"].isin(reference_blocks[target_motor])
        ).to_numpy()
    if spec.training_scope == "source_target_balanced":
        return motor_balanced_reference_mask(frame, reference_blocks)
    raise ValueError(f"Unknown training scope: {spec.training_scope}")


def fit_and_score(
    spec: OneClassSpec,
    *,
    train_values: np.ndarray,
    target_values: np.ndarray,
    feature_names: list[str],
    seed: int,
    isolation_trees: int,
) -> tuple[object, np.ndarray, dict[str, object]]:
    retained = np.arange(train_values.shape[1], dtype=np.int64)
    if spec.estimator_kind == "min_cov_det":
        retained = independent_training_columns(train_values)
    model_train_values = train_values[:, retained]
    model_target_values = target_values[:, retained]
    estimator = build_oneclass_estimator(
        spec.estimator_kind,
        seed=seed,
        isolation_trees=isolation_trees,
    )
    with warnings.catch_warnings(record=True) as captured:
        warnings.simplefilter("always")
        estimator.fit(model_train_values)
    scores = oneclass_anomaly_scores(
        estimator, spec.estimator_kind, model_target_values
    )
    diagnostics: dict[str, object] = {
        "fit_warning_count": len(captured),
        "fit_warnings": sorted({str(item.message) for item in captured}),
        "input_features": len(feature_names),
        "retained_features": len(retained),
        "dropped_rank_redundant_features": [
            feature_names[index]
            for index in range(len(feature_names))
            if index not in set(retained.tolist())
        ],
    }
    if spec.estimator_kind == "min_cov_det":
        covariance = np.asarray(estimator.covariance_, dtype=np.float64)
        diagnostics.update(
            {
                "covariance_rank": int(np.linalg.matrix_rank(covariance)),
                "covariance_dimension": int(covariance.shape[0]),
                "covariance_condition_number": float(np.linalg.cond(covariance)),
                "raw_support_rows": int(np.asarray(estimator.raw_support_).sum()),
                "final_support_rows": int(np.asarray(estimator.support_).sum()),
            }
        )
    return estimator, scores, diagnostics


def evaluate_fold(
    frame: pd.DataFrame,
    *,
    source_motors: tuple[str, ...],
    target_motor: str,
    args: argparse.Namespace,
) -> tuple[list[dict[str, object]], list[pd.DataFrame], list[pd.DataFrame]]:
    split = protocol_partition()
    columns = feature_columns(frame, "scale_free")
    reference_blocks = {motor: list(range(24)) for motor in source_motors} | {
        target_motor: split.adaptation.tolist()
    }
    transformed, reference_parameters = healthy_relative_features(
        frame, columns, reference_blocks
    )
    target_mask = frame["motor_id"].eq(target_motor).to_numpy()
    target_frame = frame.loc[target_mask].reset_index(drop=True)
    target_values = transformed[target_mask]

    fold_dir = args.results_dir / f"target_{target_motor}"
    fold_dir.mkdir(parents=True, exist_ok=True)
    (fold_dir / "healthy_reference.json").write_text(
        json.dumps(
            {
                "columns": columns,
                "parameters": reference_parameters,
                "allowed_blocks": reference_blocks,
            },
            indent=2,
        ),
        encoding="utf-8",
    )

    primary_summaries: list[dict[str, object]] = []
    sensitivity_blocks: list[pd.DataFrame] = []
    sensitivity_records: list[pd.DataFrame] = []
    saved_training_scopes: set[str] = set()
    for spec in METHOD_SPECS:
        train_mask = training_mask_for_spec(
            frame,
            spec=spec,
            target_motor=target_motor,
            reference_blocks=reference_blocks,
        )
        train_values = transformed[train_mask]
        training_rows = frame.loc[
            train_mask,
            ["motor_id", "record_id", "block_id", "window_id", "is_healthy"],
        ].copy()
        if not training_rows["is_healthy"].astype(bool).all():
            raise AssertionError("A one-class fit attempted to use a fault row")
        if spec.training_scope not in saved_training_scopes:
            training_rows.to_csv(
                fold_dir / f"training_reference_{spec.training_scope}.csv", index=False
            )
            saved_training_scopes.add(spec.training_scope)

        seeds = SENSITIVITY_SEEDS if spec.stochastic else (PRIMARY_SEED,)
        for seed in seeds:
            estimator, scores, diagnostics = fit_and_score(
                spec,
                train_values=train_values,
                target_values=target_values,
                feature_names=columns,
                seed=seed,
                isolation_trees=args.isolation_trees,
            )
            summary, blocks, records = evaluate_target_scores(
                target_frame,
                scores,
                method=spec.name,
                seed=seed,
                alpha=args.alpha,
                quantile=args.block_score_quantile,
            )
            summary.update(
                {
                    "estimator_kind": spec.estimator_kind,
                    "training_scope": spec.training_scope,
                    "training_rows": int(train_mask.sum()),
                    "training_rows_by_motor": training_rows.groupby("motor_id")
                    .size()
                    .astype(int)
                    .to_dict(),
                    **diagnostics,
                }
            )

            if seed == PRIMARY_SEED:
                method_dir = fold_dir / spec.name
                method_dir.mkdir(parents=True, exist_ok=True)
                blocks.to_csv(method_dir / "block_predictions.csv", index=False)
                records.to_csv(method_dir / "record_summary.csv", index=False)
                (method_dir / "summary.json").write_text(
                    json.dumps(summary, indent=2), encoding="utf-8"
                )
                joblib.dump(estimator, method_dir / "model.joblib")
                primary_summaries.append(summary)
                print(
                    f"target_{target_motor} {spec.name}: "
                    f"FAR {summary['false_alarm_rate']:.3f}, "
                    f"detection {summary['detection_rate']:.3f}, "
                    f"AUROC {summary['block_auroc']:.3f}"
                )

            if spec.stochastic:
                blocks = blocks.copy()
                blocks["target_motor"] = target_motor
                sensitivity_blocks.append(blocks)
                records = records.copy()
                records["target_motor"] = target_motor
                sensitivity_records.append(records)
    return primary_summaries, sensitivity_blocks, sensitivity_records


def aggregate_primary(
    summaries: pd.DataFrame,
    primary_records: pd.DataFrame,
) -> pd.DataFrame:
    rows: list[dict[str, object]] = []
    for method, group in summaries.groupby("method", sort=True):
        healthy_trials = int(group["healthy_test_blocks"].sum())
        false_alarms = int(group["false_alarms"].sum())
        wilson_lower, wilson_upper = wilson_interval(false_alarms, healthy_trials)
        records = primary_records[
            primary_records["method"].eq(method)
            & ~primary_records["is_healthy"].astype(bool)
        ]
        ci_lower, ci_upper = stratified_record_bootstrap_interval(
            records,
            value_column="block_alarm_rate",
            iterations=BOOTSTRAP_ITERATIONS,
            seed=BOOTSTRAP_SEED,
        )
        rows.append(
            {
                "method": method,
                "healthy_records": 3,
                "healthy_test_blocks": healthy_trials,
                "false_alarms": false_alarms,
                "pooled_block_false_alarm_rate": false_alarms / healthy_trials,
                "descriptive_block_wilson_lower": wilson_lower,
                "descriptive_block_wilson_upper": wilson_upper,
                "wilson_independent_block_assumption_valid": False,
                "max_motor_false_alarm_rate": float(group["false_alarm_rate"].max()),
                "h1_empirical_pass": bool(
                    wilson_upper <= 0.12 and group["false_alarm_rate"].max() <= 0.15
                ),
                "fault_records": len(records),
                "fault_record_macro_detection_rate": float(
                    records["block_alarm_rate"].mean()
                ),
                "record_bootstrap_detection_ci_lower": ci_lower,
                "record_bootstrap_detection_ci_upper": ci_upper,
                "record_bootstrap_conditional_on_observed_motors": True,
                "fault_record_any_alarm_rate": float((records["alarms"] > 0).mean()),
                "mean_fold_detection_rate": float(group["detection_rate"].mean()),
                "worst_motor_detection_rate": float(group["detection_rate"].min()),
                "mean_block_auroc": float(group["block_auroc"].mean()),
            }
        )
    return pd.DataFrame(rows)


def aggregate_seed_sensitivity(
    blocks: pd.DataFrame,
    records: pd.DataFrame,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    summary_rows: list[dict[str, object]] = []
    for (method, seed), group in blocks.groupby(["method", "seed"], sort=True):
        healthy_test = group[
            group["is_healthy"].astype(bool)
            & group["block_id"].isin(protocol_partition().test)
        ]
        faults = group[~group["is_healthy"].astype(bool)]
        fault_records = records[
            records["method"].eq(method)
            & records["seed"].eq(seed)
            & ~records["is_healthy"].astype(bool)
        ]
        fold_detection = faults.groupby("target_motor", sort=True)["alarm"].mean()
        summary_rows.append(
            {
                "method": method,
                "seed": int(seed),
                "false_alarms": int(healthy_test["alarm"].sum()),
                "healthy_test_blocks": len(healthy_test),
                "pooled_block_false_alarm_rate": float(healthy_test["alarm"].mean()),
                "fault_record_macro_detection_rate": float(
                    fault_records["block_alarm_rate"].mean()
                ),
                "mean_fold_detection_rate": float(fold_detection.mean()),
                "worst_motor_detection_rate": float(fold_detection.min()),
            }
        )
    summary = pd.DataFrame(summary_rows)
    ranges = (
        summary.groupby("method", sort=True)
        .agg(
            seeds=("seed", "size"),
            far_min=("pooled_block_false_alarm_rate", "min"),
            far_max=("pooled_block_false_alarm_rate", "max"),
            detection_mean=("fault_record_macro_detection_rate", "mean"),
            detection_sd=("fault_record_macro_detection_rate", "std"),
            detection_min=("fault_record_macro_detection_rate", "min"),
            detection_max=("fault_record_macro_detection_rate", "max"),
            worst_motor_min=("worst_motor_detection_rate", "min"),
            worst_motor_max=("worst_motor_detection_rate", "max"),
        )
        .reset_index()
    )
    return summary, ranges


def main() -> None:
    args = parse_args()
    if args.isolation_trees < 100:
        raise ValueError("isolation-trees must be at least 100")
    frame = pd.read_csv(args.features)
    args.results_dir.mkdir(parents=True, exist_ok=True)

    all_summaries: list[dict[str, object]] = []
    all_sensitivity_blocks: list[pd.DataFrame] = []
    all_sensitivity_records: list[pd.DataFrame] = []
    for fold in leave_one_motor_out():
        summaries, blocks, records = evaluate_fold(
            frame,
            source_motors=fold.source_motors,
            target_motor=fold.target_motor,
            args=args,
        )
        all_summaries.extend(summaries)
        all_sensitivity_blocks.extend(blocks)
        all_sensitivity_records.extend(records)

    summary_frame = pd.DataFrame(all_summaries)
    summary_frame.to_csv(args.results_dir / "summary.csv", index=False)

    primary_blocks_parts: list[pd.DataFrame] = []
    primary_records_parts: list[pd.DataFrame] = []
    for fold in leave_one_motor_out():
        for spec in METHOD_SPECS:
            method_dir = args.results_dir / fold.fold_id / spec.name
            blocks = pd.read_csv(method_dir / "block_predictions.csv")
            records = pd.read_csv(method_dir / "record_summary.csv")
            blocks["target_motor"] = fold.target_motor
            records["target_motor"] = fold.target_motor
            primary_blocks_parts.append(blocks)
            primary_records_parts.append(records)
    primary_blocks = pd.concat(primary_blocks_parts, ignore_index=True)
    primary_records = pd.concat(primary_records_parts, ignore_index=True)
    primary_blocks.to_csv(
        args.results_dir / "block_predictions.csv.gz", index=False, compression="gzip"
    )
    primary_records.to_csv(args.results_dir / "record_summary.csv", index=False)
    aggregate_primary(summary_frame, primary_records).to_csv(
        args.results_dir / "aggregate_summary.csv", index=False
    )

    sensitivity_blocks = pd.concat(all_sensitivity_blocks, ignore_index=True)
    sensitivity_records = pd.concat(all_sensitivity_records, ignore_index=True)
    sensitivity_blocks.to_csv(
        args.results_dir / "seed_sensitivity_block_predictions.csv.gz",
        index=False,
        compression="gzip",
    )
    sensitivity_records.to_csv(
        args.results_dir / "seed_sensitivity_record_summary.csv", index=False
    )
    seed_summary, seed_ranges = aggregate_seed_sensitivity(
        sensitivity_blocks, sensitivity_records
    )
    seed_summary.to_csv(
        args.results_dir / "seed_sensitivity_summary.csv", index=False
    )
    seed_ranges.to_csv(args.results_dir / "randomness_ranges.csv", index=False)

    metadata = {
        "created_utc": datetime.now(UTC).isoformat(),
        "features": str(args.features.resolve()),
        "features_sha256": file_sha256(args.features),
        "scikit_learn": sklearn.__version__,
        "protocol": {
            "feature_arm": "scale_free",
            "window_seconds": 0.2,
            "block_seconds": 3.0,
            "block_score": "maximum",
            "adaptation_blocks": [0, 1, 2, 3],
            "guard_blocks": [4, 25],
            "calibration_blocks": list(range(5, 25)),
            "healthy_test_blocks": list(range(26, 40)),
            "alpha": args.alpha,
        },
        "hyperparameter_policy": (
            "Fixed common defaults before this run; no target-fault labels or scores "
            "were used for model selection. Calibration replaces estimator-native "
            "contamination thresholds."
        ),
        "methods": {
            "ocsvm": {"kernel": "rbf", "gamma": "scale", "nu": 0.05},
            "isolation_forest": {
                "n_estimators": args.isolation_trees,
                "max_samples": "auto (min(256, n_train))",
                "contamination": "auto (not used as alarm threshold)",
                "max_features": 1.0,
                "bootstrap": False,
            },
            "min_cov_det": {
                "assume_centered": True,
                "support_fraction": "scikit-learn default",
                "numerical_preprocessing": (
                    "Rank-revealing QR on healthy fit rows only; invariant and exact "
                    "linearly redundant columns are removed before fitting with a "
                    "sqrt(machine-epsilon) relative rank tolerance."
                ),
            },
        },
        "source_target_balance": (
            "Four complete healthy blocks per motor. Target uses adaptation blocks "
            "0-3; each source contributes four evenly spaced blocks from 0-23."
        ),
        "primary_seed": PRIMARY_SEED,
        "stochastic_sensitivity_seeds": list(SENSITIVITY_SEEDS),
        "record_bootstrap": {
            "iterations": BOOTSTRAP_ITERATIONS,
            "seed": BOOTSTRAP_SEED,
            "unit": "whole fault record",
            "stratification": "motor_id",
            "scope": "conditional on the three observed motors",
        },
        "inference_boundary": (
            "The 42 healthy test blocks come from only three healthy time series and "
            "are dependent. Their pooled Wilson interval is descriptive and must not "
            "be presented as an independent-block coverage guarantee. Fault intervals "
            "resample the 42 whole fault records within observed motor."
        ),
    }
    (args.results_dir / "run_metadata.json").write_text(
        json.dumps(metadata, indent=2), encoding="utf-8"
    )


if __name__ == "__main__":
    main()
