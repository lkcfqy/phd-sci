"""Run target-health covariance baselines and the entity-balanced covariance method."""

from __future__ import annotations

import argparse
import json
from datetime import UTC, datetime
from pathlib import Path

import numpy as np
import pandas as pd
import sklearn
from scipy.stats import spearmanr
from sklearn.covariance import LedoitWolf
from sklearn.metrics import average_precision_score, roc_auc_score

from pmsm_sci.faults.baseline import (
    block_score_table,
    feature_columns,
    healthy_relative_features,
)
from pmsm_sci.faults.conformal import conformal_p_values, conformal_threshold
from pmsm_sci.faults.covariance import (
    entity_balanced_covariance,
    log_euclidean_entity_covariance,
    mahalanobis_scores,
    regularize_covariance,
    sample_covariance,
)
from pmsm_sci.faults.splits import leave_one_motor_out, partition_contiguous_blocks
from pmsm_sci.faults.statistics import wilson_interval

METHODS = (
    "target_ledoit",
    "target_sample_covariance",
    "source_covariance",
    "entity_balanced_covariance",
    "log_euclidean_entity_covariance",
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--features", type=Path, default=Path("data/processed/kaist_current_features.csv.gz")
    )
    parser.add_argument(
        "--results-dir", type=Path, default=Path("results/healthy_covariance_v0")
    )
    parser.add_argument(
        "--feature-arms",
        nargs="+",
        choices=["all_features", "scale_free"],
        default=["scale_free", "all_features"],
    )
    parser.add_argument("--alpha", type=float, default=0.05)
    parser.add_argument("--ridge-fraction", type=float, default=1e-3)
    parser.add_argument("--log-ridge-fraction", type=float, default=1e-2)
    parser.add_argument("--block-score-quantile", type=float, default=1.0)
    return parser.parse_args()


def partition():
    return partition_contiguous_blocks(
        40,
        adaptation_fraction=0.12,
        calibration_fraction=0.55,
        guard_blocks=1,
    )


def evaluate_scores(
    target_frame: pd.DataFrame,
    scores: np.ndarray,
    *,
    alpha: float,
    quantile: float,
    method: str,
    feature_arm: str,
    output_dir: Path,
) -> dict[str, object]:
    split = partition()
    blocks = block_score_table(target_frame, scores, quantile=quantile)
    healthy = blocks[blocks["is_healthy"].astype(bool)]
    calibration = healthy[healthy["block_id"].isin(split.calibration)]
    healthy_test = healthy[healthy["block_id"].isin(split.test)]
    faults = blocks[~blocks["is_healthy"].astype(bool)].copy()
    threshold = conformal_threshold(calibration["score"], alpha)
    blocks["p_value"] = conformal_p_values(calibration["score"], blocks["score"])
    blocks["alarm"] = blocks["p_value"] <= alpha
    healthy_test = blocks[
        blocks["is_healthy"].astype(bool) & blocks["block_id"].isin(split.test)
    ]
    faults = blocks[~blocks["is_healthy"].astype(bool)].copy()

    evaluation = pd.concat([healthy_test, faults], ignore_index=True)
    labels = (~evaluation["is_healthy"].astype(bool)).astype(int)
    severity = (
        faults.groupby(["fault_family", "severity_percent"], observed=True)
        .agg(
            blocks=("score", "size"),
            score_mean=("score", "mean"),
            detection_rate=("alarm", "mean"),
        )
        .reset_index()
        .sort_values(["fault_family", "severity_percent"])
    )
    lowest_two = severity.groupby("fault_family", observed=True).head(2)
    correlations: dict[str, float] = {}
    for family, family_frame in severity.groupby("fault_family", observed=True):
        correlations[str(family)] = float(
            spearmanr(family_frame["severity_percent"], family_frame["score_mean"]).statistic
        )

    output_dir.mkdir(parents=True, exist_ok=True)
    blocks.to_csv(output_dir / "block_predictions.csv", index=False)
    severity.to_csv(output_dir / "severity_detection.csv", index=False)
    summary: dict[str, object] = {
        "target_motor": str(target_frame["motor_id"].iloc[0]),
        "method": method,
        "feature_arm": feature_arm,
        "alpha": alpha,
        "threshold": threshold,
        "adaptation_blocks": len(split.adaptation),
        "calibration_blocks": len(calibration),
        "healthy_test_blocks": len(healthy_test),
        "fault_test_blocks": len(faults),
        "false_alarms": int(healthy_test["alarm"].sum()),
        "false_alarm_rate": float(healthy_test["alarm"].mean()),
        "detected_fault_blocks": int(faults["alarm"].sum()),
        "detection_rate": float(faults["alarm"].mean()),
        "lowest_two_severity_detection_rate": float(lowest_two["detection_rate"].mean()),
        "block_auroc": float(roc_auc_score(labels, evaluation["score"])),
        "block_auprc": float(average_precision_score(labels, evaluation["score"])),
        "severity_spearman": correlations,
    }
    (output_dir / "summary.json").write_text(
        json.dumps(summary, indent=2), encoding="utf-8"
    )
    return summary


def evaluate_fold(
    frame: pd.DataFrame,
    *,
    source_motors: tuple[str, ...],
    target_motor: str,
    feature_arm: str,
    alpha: float,
    ridge_fraction: float,
    log_ridge_fraction: float,
    quantile: float,
    results_dir: Path,
) -> list[dict[str, object]]:
    split = partition()
    columns = feature_columns(frame, feature_arm)
    reference_blocks = {motor: list(range(24)) for motor in source_motors} | {
        target_motor: split.adaptation.tolist()
    }
    transformed, reference_parameters = healthy_relative_features(
        frame, columns, reference_blocks
    )
    target_mask = frame["motor_id"].eq(target_motor).to_numpy()
    target_frame = frame.loc[target_mask].reset_index(drop=True)
    target_values = transformed[target_mask]
    target_reference = (
        target_frame["is_healthy"].astype(bool)
        & target_frame["block_id"].isin(split.adaptation)
    ).to_numpy()
    target_reference_values = target_values[target_reference]
    # ``healthy_relative_features`` centers on the target healthy median. Keeping
    # that robust zero location avoids reintroducing a mean shift from only four
    # adaptation blocks.
    target_location = np.zeros(target_reference_values.shape[1], dtype=np.float64)

    source_covariances: list[np.ndarray] = []
    for motor in source_motors:
        reference = (
            frame["motor_id"].eq(motor)
            & frame["is_healthy"].astype(bool)
            & frame["block_id"].isin(range(24))
        ).to_numpy()
        source_covariances.append(sample_covariance(transformed[reference]))
    target_covariance = sample_covariance(target_reference_values)
    covariance_by_method = {
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
    ledoit = LedoitWolf().fit(target_reference_values)

    fold_dir = results_dir / f"target_{target_motor}" / feature_arm
    fold_dir.mkdir(parents=True, exist_ok=True)
    (fold_dir / "healthy_reference.json").write_text(
        json.dumps(
            {"columns": columns, "parameters": reference_parameters}, indent=2
        ),
        encoding="utf-8",
    )

    summaries: list[dict[str, object]] = []
    for method in METHODS:
        if method == "target_ledoit":
            covariance = ledoit.covariance_
            location = ledoit.location_
        else:
            covariance = covariance_by_method[method]
            location = target_location
        scores = mahalanobis_scores(target_values, covariance, location)
        method_dir = fold_dir / method
        method_dir.mkdir(parents=True, exist_ok=True)
        np.savez_compressed(method_dir / "covariance.npz", covariance=covariance, location=location)
        summary = evaluate_scores(
            target_frame,
            scores,
            alpha=alpha,
            quantile=quantile,
            method=method,
            feature_arm=feature_arm,
            output_dir=method_dir,
        )
        summaries.append(summary)
        print(
            f"target_{target_motor} {feature_arm} {method}: "
            f"FAR {summary['false_alarm_rate']:.3f}, "
            f"detection {summary['detection_rate']:.3f}, "
            f"AUROC {summary['block_auroc']:.3f}"
        )
    return summaries


def main() -> None:
    args = parse_args()
    frame = pd.read_csv(args.features)
    args.results_dir.mkdir(parents=True, exist_ok=True)
    summaries: list[dict[str, object]] = []
    for fold in leave_one_motor_out():
        for feature_arm in args.feature_arms:
            summaries.extend(
                evaluate_fold(
                    frame,
                    source_motors=fold.source_motors,
                    target_motor=fold.target_motor,
                    feature_arm=feature_arm,
                    alpha=args.alpha,
                    ridge_fraction=args.ridge_fraction,
                    log_ridge_fraction=args.log_ridge_fraction,
                    quantile=args.block_score_quantile,
                    results_dir=args.results_dir,
                )
            )

    summary_frame = pd.DataFrame(summaries)
    summary_frame.drop(columns="severity_spearman").to_csv(
        args.results_dir / "summary.csv", index=False
    )
    aggregate_rows: list[dict[str, object]] = []
    for (feature_arm, method), group in summary_frame.groupby(
        ["feature_arm", "method"], sort=True
    ):
        trials = int(group["healthy_test_blocks"].sum())
        false_alarms = int(group["false_alarms"].sum())
        lower, upper = wilson_interval(false_alarms, trials)
        aggregate_rows.append(
            {
                "feature_arm": feature_arm,
                "method": method,
                "healthy_test_blocks": trials,
                "false_alarms": false_alarms,
                "pooled_false_alarm_rate": false_alarms / trials,
                "pooled_far_wilson_lower": lower,
                "pooled_far_wilson_upper": upper,
                "max_motor_false_alarm_rate": float(group["false_alarm_rate"].max()),
                "h1_empirical_pass": bool(
                    upper <= 0.12 and group["false_alarm_rate"].max() <= 0.15
                ),
                "mean_detection_rate": float(group["detection_rate"].mean()),
                "worst_motor_detection_rate": float(group["detection_rate"].min()),
                "mean_lowest_two_detection_rate": float(
                    group["lowest_two_severity_detection_rate"].mean()
                ),
                "mean_block_auroc": float(group["block_auroc"].mean()),
            }
        )
    pd.DataFrame(aggregate_rows).to_csv(
        args.results_dir / "aggregate_summary.csv", index=False
    )
    (args.results_dir / "run_metadata.json").write_text(
        json.dumps(
            {
                "created_utc": datetime.now(UTC).isoformat(),
                "features": str(args.features.resolve()),
                "scikit_learn": sklearn.__version__,
                "alpha": args.alpha,
                "ridge_fraction": args.ridge_fraction,
                "log_ridge_fraction": args.log_ridge_fraction,
                "block_score_quantile": args.block_score_quantile,
                "feature_arms": args.feature_arms,
            },
            indent=2,
        ),
        encoding="utf-8",
    )


if __name__ == "__main__":
    main()
