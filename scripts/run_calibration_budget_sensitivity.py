"""Evaluate target-health adaptation budgets for the proposed covariance detector.

The adaptation budget estimates target robust feature scaling and covariance.
An independent 60-second target-health sequence calibrates the block-conformal
alarm. Small durations are also audited as *calibration* budgets; combinations
that cannot resolve the requested alpha are reported as skipped rather than
evaluated with an anti-conservative threshold.
"""

from __future__ import annotations

import argparse
import json
import math
from datetime import UTC, datetime
from pathlib import Path

import numpy as np
import pandas as pd
import sklearn
from sklearn.metrics import average_precision_score, roc_auc_score

from pmsm_sci.faults.baseline import (
    block_score_table,
    feature_columns,
    healthy_relative_features,
)
from pmsm_sci.faults.budget import (
    BudgetPartition,
    assert_budget_partition,
    fixed_horizon_budget_partition,
    minimum_calibration_blocks,
    sequential_budget_partition,
)
from pmsm_sci.faults.conformal import conformal_p_values, conformal_threshold
from pmsm_sci.faults.covariance import (
    log_euclidean_entity_covariance,
    mahalanobis_scores,
    sample_covariance,
)
from pmsm_sci.faults.splits import leave_one_motor_out
from pmsm_sci.faults.statistics import wilson_interval

N_HEALTHY_BLOCKS = 40
SOURCE_REFERENCE_BLOCKS = 24
METHOD = "log_euclidean_entity_covariance"
FEATURE_ARM = "scale_free"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--features",
        type=Path,
        default=Path("data/processed/kaist_current_features.csv.gz"),
    )
    parser.add_argument(
        "--results-dir",
        type=Path,
        default=Path("results/calibration_budget_sensitivity"),
    )
    parser.add_argument(
        "--adaptation-seconds",
        nargs="+",
        type=float,
        default=[3.0, 6.0, 12.0, 24.0],
    )
    parser.add_argument("--calibration-seconds", type=float, default=60.0)
    parser.add_argument("--block-seconds", type=float, default=3.0)
    parser.add_argument(
        "--designs",
        nargs="+",
        choices=["fixed_horizon", "sequential"],
        default=["fixed_horizon", "sequential"],
    )
    parser.add_argument("--guard-blocks", type=int, default=1)
    parser.add_argument("--alpha", type=float, default=0.05)
    parser.add_argument("--log-ridge-fraction", type=float, default=1e-2)
    parser.add_argument("--block-score-quantile", type=float, default=1.0)
    return parser.parse_args()


def seconds_to_blocks(seconds: float, block_seconds: float, *, name: str) -> int:
    if seconds <= 0 or block_seconds <= 0:
        raise ValueError(f"{name} and block_seconds must be positive")
    quotient = seconds / block_seconds
    blocks = round(quotient)
    if not math.isclose(quotient, blocks, rel_tol=0.0, abs_tol=1e-9):
        raise ValueError(f"{name} must be an integer multiple of block_seconds")
    return blocks


def make_partition(
    design: str,
    *,
    adaptation_blocks: int,
    max_adaptation_blocks: int,
    calibration_blocks: int,
    guard_blocks: int,
) -> BudgetPartition:
    if design == "fixed_horizon":
        result = fixed_horizon_budget_partition(
            N_HEALTHY_BLOCKS,
            adaptation_blocks=adaptation_blocks,
            max_adaptation_blocks=max_adaptation_blocks,
            calibration_blocks=calibration_blocks,
            guard_blocks=guard_blocks,
        )
    elif design == "sequential":
        result = sequential_budget_partition(
            N_HEALTHY_BLOCKS,
            adaptation_blocks=adaptation_blocks,
            calibration_blocks=calibration_blocks,
            guard_blocks=guard_blocks,
        )
    else:
        raise ValueError(f"Unknown design: {design}")
    assert_budget_partition(result, N_HEALTHY_BLOCKS)
    return result


def calibration_feasibility_table(
    requested_seconds: list[float],
    *,
    primary_calibration_seconds: float,
    block_seconds: float,
    alpha: float,
) -> pd.DataFrame:
    minimum_blocks = minimum_calibration_blocks(alpha)
    minimum_seconds = minimum_blocks * block_seconds
    durations = sorted(
        {
            *requested_seconds,
            minimum_seconds,
            primary_calibration_seconds,
        }
    )
    rows: list[dict[str, object]] = []
    for seconds in durations:
        blocks = seconds_to_blocks(
            seconds, block_seconds, name="calibration diagnostic duration"
        )
        finite = blocks >= minimum_blocks
        rows.append(
            {
                "calibration_seconds": seconds,
                "calibration_blocks": blocks,
                "alpha": alpha,
                "minimum_attainable_p_value": 1.0 / (blocks + 1),
                "minimum_required_blocks": minimum_blocks,
                "minimum_required_seconds": minimum_seconds,
                "finite_threshold": finite,
                "status": (
                    "primary_evaluated"
                    if math.isclose(seconds, primary_calibration_seconds)
                    else "feasible_not_evaluated"
                    if finite
                    else "skipped_insufficient_calibration_units"
                ),
            }
        )
    return pd.DataFrame(rows)


def add_evaluation_roles(blocks: pd.DataFrame, partition: BudgetPartition) -> pd.DataFrame:
    result = blocks.copy()
    result["evaluation_role"] = "fault_test"
    healthy = result["is_healthy"].astype(bool)
    roles = (
        (partition.adaptation, "adaptation"),
        (partition.calibration, "calibration"),
        (partition.guard, "guard"),
        (partition.unused, "unused"),
        (partition.test, "healthy_test"),
    )
    for block_ids, role in roles:
        result.loc[healthy & result["block_id"].isin(block_ids), "evaluation_role"] = role
    return result


def evaluate_budget(
    frame: pd.DataFrame,
    *,
    source_motors: tuple[str, ...],
    target_motor: str,
    design: str,
    adaptation_seconds: float,
    block_seconds: float,
    partition: BudgetPartition,
    alpha: float,
    log_ridge_fraction: float,
    block_score_quantile: float,
    output_dir: Path,
) -> dict[str, object]:
    columns = feature_columns(frame, FEATURE_ARM)
    reference_blocks = {motor: list(range(SOURCE_REFERENCE_BLOCKS)) for motor in source_motors}
    reference_blocks[target_motor] = partition.adaptation.tolist()
    transformed, reference_parameters = healthy_relative_features(
        frame, columns, reference_blocks
    )

    target_mask = frame["motor_id"].eq(target_motor).to_numpy()
    target_frame = frame.loc[target_mask].reset_index(drop=True)
    target_values = transformed[target_mask]
    target_reference_mask = (
        target_frame["is_healthy"].astype(bool)
        & target_frame["block_id"].isin(partition.adaptation)
    ).to_numpy()
    target_reference_values = target_values[target_reference_mask]

    source_covariances: list[np.ndarray] = []
    for motor in source_motors:
        source_reference_mask = (
            frame["motor_id"].eq(motor)
            & frame["is_healthy"].astype(bool)
            & frame["block_id"].isin(range(SOURCE_REFERENCE_BLOCKS))
        ).to_numpy()
        source_covariances.append(sample_covariance(transformed[source_reference_mask]))
    target_covariance = sample_covariance(target_reference_values)
    covariance = log_euclidean_entity_covariance(
        [*source_covariances, target_covariance], log_ridge_fraction
    )
    location = np.zeros(target_values.shape[1], dtype=np.float64)
    scores = mahalanobis_scores(target_values, covariance, location)

    blocks = block_score_table(
        target_frame, scores, quantile=block_score_quantile
    )
    blocks = add_evaluation_roles(blocks, partition)
    calibration = blocks[blocks["evaluation_role"].eq("calibration")]
    threshold = conformal_threshold(calibration["score"], alpha)
    if not math.isfinite(threshold):
        raise RuntimeError(
            "Primary calibration threshold is infinite; increase calibration_seconds"
        )
    blocks["p_value"] = conformal_p_values(calibration["score"], blocks["score"])
    blocks["alarm"] = blocks["p_value"] <= alpha

    healthy_test = blocks[blocks["evaluation_role"].eq("healthy_test")]
    faults = blocks[blocks["evaluation_role"].eq("fault_test")]
    evaluation = pd.concat([healthy_test, faults], ignore_index=True)
    labels = evaluation["evaluation_role"].eq("fault_test").astype(int)
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

    output_dir.mkdir(parents=True, exist_ok=True)
    blocks.to_csv(output_dir / "block_predictions.csv", index=False)
    severity.to_csv(output_dir / "severity_detection.csv", index=False)
    np.savez_compressed(
        output_dir / "covariance.npz", covariance=covariance, location=location
    )
    (output_dir / "healthy_reference.json").write_text(
        json.dumps(
            {"columns": columns, "parameters": reference_parameters}, indent=2
        ),
        encoding="utf-8",
    )

    return {
        "design": design,
        "target_motor": target_motor,
        "method": METHOD,
        "feature_arm": FEATURE_ARM,
        "adaptation_seconds": adaptation_seconds,
        "adaptation_blocks": len(partition.adaptation),
        "adaptation_windows": int(target_reference_mask.sum()),
        "calibration_seconds": len(partition.calibration) * block_seconds,
        "calibration_blocks": len(calibration),
        "healthy_test_seconds": len(partition.test) * block_seconds,
        "healthy_test_blocks": len(healthy_test),
        "alpha": alpha,
        "threshold": threshold,
        "false_alarms": int(healthy_test["alarm"].sum()),
        "false_alarm_rate": float(healthy_test["alarm"].mean()),
        "fault_test_blocks": len(faults),
        "detected_fault_blocks": int(faults["alarm"].sum()),
        "detection_rate": float(faults["alarm"].mean()),
        "lowest_two_severity_detection_rate": float(lowest_two["detection_rate"].mean()),
        "block_auroc": float(roc_auc_score(labels, evaluation["score"])),
        "block_auprc": float(average_precision_score(labels, evaluation["score"])),
    }


def aggregate_summaries(summaries: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, object]] = []
    for (design, adaptation_seconds), group in summaries.groupby(
        ["design", "adaptation_seconds"], sort=True
    ):
        healthy_trials = int(group["healthy_test_blocks"].sum())
        false_alarms = int(group["false_alarms"].sum())
        lower, upper = wilson_interval(false_alarms, healthy_trials)
        rows.append(
            {
                "design": design,
                "adaptation_seconds": adaptation_seconds,
                "adaptation_blocks": int(group["adaptation_blocks"].iloc[0]),
                "calibration_seconds": float(group["calibration_seconds"].iloc[0]),
                "calibration_blocks_per_motor": int(group["calibration_blocks"].iloc[0]),
                "healthy_test_blocks": healthy_trials,
                "false_alarms": false_alarms,
                "pooled_false_alarm_rate": false_alarms / healthy_trials,
                "pooled_far_wilson_lower": lower,
                "pooled_far_wilson_upper": upper,
                "max_motor_false_alarm_rate": float(group["false_alarm_rate"].max()),
                "mean_detection_rate": float(group["detection_rate"].mean()),
                "pooled_detection_rate": float(
                    group["detected_fault_blocks"].sum() / group["fault_test_blocks"].sum()
                ),
                "worst_motor_detection_rate": float(group["detection_rate"].min()),
                "mean_lowest_two_detection_rate": float(
                    group["lowest_two_severity_detection_rate"].mean()
                ),
                "mean_block_auroc": float(group["block_auroc"].mean()),
            }
        )
    return pd.DataFrame(rows)


def main() -> None:
    args = parse_args()
    adaptation_blocks = {
        seconds: seconds_to_blocks(
            seconds, args.block_seconds, name="adaptation_seconds"
        )
        for seconds in args.adaptation_seconds
    }
    calibration_blocks = seconds_to_blocks(
        args.calibration_seconds,
        args.block_seconds,
        name="calibration_seconds",
    )
    minimum_blocks = minimum_calibration_blocks(args.alpha)
    if calibration_blocks < minimum_blocks:
        raise ValueError(
            f"calibration_seconds supplies {calibration_blocks} blocks, but alpha={args.alpha} "
            f"requires at least {minimum_blocks}; primary experiment cannot be evaluated"
        )

    frame = pd.read_csv(args.features)
    args.results_dir.mkdir(parents=True, exist_ok=True)
    feasibility = calibration_feasibility_table(
        list(adaptation_blocks),
        primary_calibration_seconds=args.calibration_seconds,
        block_seconds=args.block_seconds,
        alpha=args.alpha,
    )
    feasibility.to_csv(args.results_dir / "conformal_calibration_feasibility.csv", index=False)

    max_adaptation_blocks = max(adaptation_blocks.values())
    partition_rows: list[dict[str, object]] = []
    summaries: list[dict[str, object]] = []
    for design in args.designs:
        for seconds, n_adaptation_blocks in adaptation_blocks.items():
            partition = make_partition(
                design,
                adaptation_blocks=n_adaptation_blocks,
                max_adaptation_blocks=max_adaptation_blocks,
                calibration_blocks=calibration_blocks,
                guard_blocks=args.guard_blocks,
            )
            partition_rows.append(
                {
                    "design": design,
                    "adaptation_seconds": seconds,
                    "adaptation_block_ids": " ".join(map(str, partition.adaptation)),
                    "unused_block_ids": " ".join(map(str, partition.unused)),
                    "guard_block_ids": " ".join(map(str, partition.guard)),
                    "calibration_block_ids": " ".join(map(str, partition.calibration)),
                    "healthy_test_block_ids": " ".join(map(str, partition.test)),
                }
            )
            for fold in leave_one_motor_out():
                output_dir = (
                    args.results_dir
                    / design
                    / f"adapt_{seconds:g}s"
                    / f"target_{fold.target_motor}"
                )
                summary = evaluate_budget(
                    frame,
                    source_motors=fold.source_motors,
                    target_motor=fold.target_motor,
                    design=design,
                    adaptation_seconds=seconds,
                    block_seconds=args.block_seconds,
                    partition=partition,
                    alpha=args.alpha,
                    log_ridge_fraction=args.log_ridge_fraction,
                    block_score_quantile=args.block_score_quantile,
                    output_dir=output_dir,
                )
                summaries.append(summary)
                print(
                    f"{design} adapt={seconds:g}s target={fold.target_motor}: "
                    f"FAR={summary['false_alarm_rate']:.3f}, "
                    f"detection={summary['detection_rate']:.3f}, "
                    f"AUROC={summary['block_auroc']:.3f}",
                    flush=True,
                )

    pd.DataFrame(partition_rows).to_csv(
        args.results_dir / "partition_plan.csv", index=False
    )
    summary_frame = pd.DataFrame(summaries)
    summary_frame.to_csv(args.results_dir / "summary.csv", index=False)
    aggregate_summaries(summary_frame).to_csv(
        args.results_dir / "aggregate_summary.csv", index=False
    )
    (args.results_dir / "run_metadata.json").write_text(
        json.dumps(
            {
                "created_utc": datetime.now(UTC).isoformat(),
                "features": str(args.features.resolve()),
                "scikit_learn": sklearn.__version__,
                "method": METHOD,
                "feature_arm": FEATURE_ARM,
                "adaptation_seconds": args.adaptation_seconds,
                "primary_calibration_seconds": args.calibration_seconds,
                "block_seconds": args.block_seconds,
                "alpha": args.alpha,
                "minimum_calibration_blocks": minimum_blocks,
                "log_ridge_fraction": args.log_ridge_fraction,
                "ridge_selection": "fixed source-only nested pseudo-target validation",
                "block_score_quantile": args.block_score_quantile,
                "designs": args.designs,
                "design_descriptions": {
                    "fixed_horizon": (
                        "Nested prefixes from blocks 0-7; blocks 9-28 calibrate and "
                        "30-39 test every budget, while unused prefix blocks isolate "
                        "the statistical adaptation amount."
                    ),
                    "sequential": (
                        "Calibration immediately follows adaptation plus one guard; "
                        "the later healthy-test duration therefore changes by budget."
                    ),
                },
                "target_fault_data_used_for_selection": False,
                "interpretation": (
                    "Adaptation seconds vary target healthy scaling/covariance data; "
                    "an independent 60-second healthy sequence calibrates conformal alarms."
                ),
            },
            indent=2,
        ),
        encoding="utf-8",
    )


if __name__ == "__main__":
    main()
