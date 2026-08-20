"""Audit macro-block length and score aggregation for the proposed detector.

The detector itself is frozen at the primary healthy-only design: scale-free
features, the first 72 seconds of each source healthy record, the first 12
seconds of the target healthy record, a log-Euclidean motor-balanced covariance,
and ridge fraction 0.01.  This script only regroups the already-computed 0.2 s
window scores.  Target fault labels are never used to choose a block length or
aggregation rule; 3 s/max remains the predeclared primary setting.
"""

from __future__ import annotations

import argparse
import json
import math
from dataclasses import asdict, dataclass
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

WINDOW_SECONDS = 0.2
RECORD_SECONDS = 120.0
TARGET_ADAPTATION_SECONDS = 12.0
SOURCE_REFERENCE_SECONDS = 72.0
CALIBRATION_SECONDS = 60.0
PRIMARY_BLOCK_SECONDS = 3.0
PRIMARY_AGGREGATION = "max"
METHOD = "log_euclidean_entity_covariance"
FEATURE_ARM = "scale_free"


@dataclass(frozen=True)
class BlockDesign:
    """One candidate block design and its conformal feasibility audit."""

    block_seconds: float
    windows_per_block: int
    macroblocks_per_record: int
    adaptation_blocks: int
    adaptation_seconds_realized: float
    guard_blocks_each_side: int
    calibration_blocks: int
    calibration_seconds_realized: float
    healthy_test_blocks: int
    healthy_test_seconds: float
    minimum_required_calibration_blocks: int
    minimum_attainable_p_value: float
    nonoverlapping_calibration_units: bool
    independence_claimed: bool
    finite_alpha_threshold: bool
    status: str
    reason: str
    is_primary_block_length: bool


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--features",
        type=Path,
        default=Path("data/processed/kaist_current_features.csv.gz"),
    )
    parser.add_argument(
        "--results-dir", type=Path, default=Path("results/block_sensitivity")
    )
    parser.add_argument(
        "--block-seconds", nargs="+", type=float, default=[1.0, 2.0, 3.0, 5.0, 6.0]
    )
    parser.add_argument(
        "--aggregations", nargs="+", choices=["max", "q90"], default=["max", "q90"]
    )
    parser.add_argument("--alpha", type=float, default=0.05)
    parser.add_argument("--log-ridge-fraction", type=float, default=1e-2)
    return parser.parse_args()


def _integer_units(duration: float, unit: float, *, name: str) -> int:
    if duration <= 0 or unit <= 0:
        raise ValueError(f"{name} and its unit must be positive")
    quotient = duration / unit
    rounded = round(quotient)
    if not math.isclose(quotient, rounded, rel_tol=0.0, abs_tol=1e-9):
        raise ValueError(f"{name}={duration} is not an integer multiple of {unit}")
    return int(rounded)


def audit_block_design(block_seconds: float, *, alpha: float = 0.05) -> BlockDesign:
    """Create a chronological candidate design without looking at fault outcomes."""

    windows_per_block = _integer_units(
        block_seconds, WINDOW_SECONDS, name="block_seconds"
    )
    macroblocks_per_record = _integer_units(
        RECORD_SECONDS, block_seconds, name="record duration"
    )
    calibration_blocks = _integer_units(
        CALIBRATION_SECONDS, block_seconds, name="calibration duration"
    )
    # The candidate grid includes 5 s, which cannot exactly represent 12 s.
    # Nearest-block reporting keeps the audit complete, but infeasible candidates
    # are never evaluated.  All feasible candidates represent 12 s exactly.
    adaptation_blocks = max(1, round(TARGET_ADAPTATION_SECONDS / block_seconds))
    adaptation_seconds_realized = adaptation_blocks * block_seconds
    guard_blocks = 1
    healthy_test_blocks = (
        macroblocks_per_record
        - adaptation_blocks
        - calibration_blocks
        - 2 * guard_blocks
    )
    minimum_required = minimum_calibration_blocks(alpha)
    enough_calibration = calibration_blocks >= minimum_required
    leaves_test = healthy_test_blocks >= 1
    exact_adaptation = math.isclose(
        adaptation_seconds_realized,
        TARGET_ADAPTATION_SECONDS,
        rel_tol=0.0,
        abs_tol=1e-9,
    )
    finite = enough_calibration and leaves_test and exact_adaptation
    reasons: list[str] = []
    if not enough_calibration:
        reasons.append(
            f"{calibration_blocks} calibration macroblocks < {minimum_required} "
            f"required for alpha={alpha:g}"
        )
    if not leaves_test:
        reasons.append("chronological guards and calibration leave no healthy test block")
    if not exact_adaptation:
        reasons.append(
            f"12 s target adaptation is not exactly representable "
            f"({adaptation_seconds_realized:g} s nearest realization)"
        )
    return BlockDesign(
        block_seconds=block_seconds,
        windows_per_block=windows_per_block,
        macroblocks_per_record=macroblocks_per_record,
        adaptation_blocks=adaptation_blocks,
        adaptation_seconds_realized=adaptation_seconds_realized,
        guard_blocks_each_side=guard_blocks,
        calibration_blocks=calibration_blocks,
        calibration_seconds_realized=calibration_blocks * block_seconds,
        healthy_test_blocks=max(healthy_test_blocks, 0),
        healthy_test_seconds=max(healthy_test_blocks, 0) * block_seconds,
        minimum_required_calibration_blocks=minimum_required,
        minimum_attainable_p_value=1.0 / (calibration_blocks + 1),
        nonoverlapping_calibration_units=True,
        independence_claimed=False,
        finite_alpha_threshold=finite,
        status=(
            "evaluated_sensitivity"
            if finite
            else "skipped_infeasible_conformal_resolution"
        ),
        reason="; ".join(reasons) if reasons else "chronological design is feasible",
        is_primary_block_length=math.isclose(
            block_seconds, PRIMARY_BLOCK_SECONDS, rel_tol=0.0, abs_tol=1e-9
        ),
    )


def make_partition(design: BlockDesign) -> BudgetPartition:
    """Return adaptation, guard, calibration, guard, and test in time order."""

    if not design.finite_alpha_threshold:
        raise ValueError(f"Cannot partition infeasible design: {design.reason}")
    partition = sequential_budget_partition(
        design.macroblocks_per_record,
        adaptation_blocks=design.adaptation_blocks,
        calibration_blocks=design.calibration_blocks,
        guard_blocks=design.guard_blocks_each_side,
    )
    assert_budget_partition(partition, design.macroblocks_per_record)
    if len(partition.calibration) < design.minimum_required_calibration_blocks:
        raise AssertionError("Calibration partition cannot resolve the requested alpha")
    return partition


def assign_macroblocks(frame: pd.DataFrame, design: BlockDesign) -> pd.DataFrame:
    """Regroup each record by its original 0.2 s window index."""

    result = frame.copy()
    counts = result.groupby("record_id", observed=True)["window_id"].agg(
        ["size", "nunique", "min", "max"]
    )
    expected_windows = design.macroblocks_per_record * design.windows_per_block
    valid = (
        counts["size"].eq(expected_windows)
        & counts["nunique"].eq(expected_windows)
        & counts["min"].eq(0)
        & counts["max"].eq(expected_windows - 1)
    )
    if not valid.all():
        bad = counts.index[~valid].tolist()
        raise ValueError(f"Records do not have a complete 120 s window grid: {bad}")
    result["block_id"] = (
        result["window_id"].astype(np.int64) // design.windows_per_block
    )
    observed = result.groupby("record_id", observed=True)["block_id"].nunique()
    if not observed.eq(design.macroblocks_per_record).all():
        raise AssertionError("Macroblock regrouping produced an unexpected count")
    return result


def aggregation_quantile(name: str) -> float:
    if name == "max":
        return 1.0
    if name == "q90":
        return 0.9
    raise ValueError(f"Unknown aggregation: {name}")


def aggregation_order_from_largest(windows_per_block: int, quantile: float) -> int:
    """Return the selected order from the top for NumPy/pandas ``higher`` quantiles."""

    if windows_per_block < 1 or not 0 < quantile <= 1:
        raise ValueError("windows_per_block and quantile are invalid")
    zero_based_from_bottom = math.ceil(quantile * (windows_per_block - 1))
    return windows_per_block - zero_based_from_bottom


def frozen_window_scores(
    frame: pd.DataFrame,
    *,
    source_motors: tuple[str, ...],
    target_motor: str,
    log_ridge_fraction: float,
) -> tuple[pd.DataFrame, np.ndarray]:
    """Fit the frozen healthy-only detector and return target window scores."""

    columns = feature_columns(frame, FEATURE_ARM)
    # The existing 3 s identifiers are used only to reproduce the predeclared
    # 72 s source and 12 s target healthy reference intervals.  The resulting
    # window scores are identical for every block-length sensitivity setting.
    reference_blocks = {motor: list(range(24)) for motor in source_motors} | {
        target_motor: list(range(4))
    }
    transformed, _ = healthy_relative_features(frame, columns, reference_blocks)
    source_covariances: list[np.ndarray] = []
    for motor in source_motors:
        source_reference = (
            frame["motor_id"].eq(motor)
            & frame["is_healthy"].astype(bool)
            & frame["block_id"].isin(range(24))
        ).to_numpy()
        source_covariances.append(sample_covariance(transformed[source_reference]))

    target_mask = frame["motor_id"].eq(target_motor).to_numpy()
    target_frame = frame.loc[target_mask].reset_index(drop=True)
    target_values = transformed[target_mask]
    target_reference = (
        target_frame["is_healthy"].astype(bool)
        & target_frame["block_id"].isin(range(4))
    ).to_numpy()
    target_covariance = sample_covariance(target_values[target_reference])
    covariance = log_euclidean_entity_covariance(
        [*source_covariances, target_covariance], log_ridge_fraction
    )
    location = np.zeros(target_values.shape[1], dtype=np.float64)
    return target_frame, mahalanobis_scores(target_values, covariance, location)


def add_evaluation_roles(
    blocks: pd.DataFrame, partition: BudgetPartition
) -> pd.DataFrame:
    result = blocks.copy()
    result["evaluation_role"] = "fault_test"
    healthy = result["is_healthy"].astype(bool)
    for block_ids, role in (
        (partition.adaptation, "adaptation"),
        (partition.guard, "guard"),
        (partition.calibration, "calibration"),
        (partition.test, "healthy_test"),
    ):
        result.loc[healthy & result["block_id"].isin(block_ids), "evaluation_role"] = role
    return result


def evaluate_setting(
    target_frame: pd.DataFrame,
    window_scores: np.ndarray,
    *,
    target_motor: str,
    design: BlockDesign,
    aggregation: str,
    alpha: float,
    output_dir: Path,
) -> tuple[dict[str, object], pd.DataFrame]:
    """Evaluate one prelisted sensitivity setting after healthy-only calibration."""

    partition = make_partition(design)
    regrouped = assign_macroblocks(target_frame, design)
    quantile = aggregation_quantile(aggregation)
    blocks = block_score_table(regrouped, window_scores, quantile=quantile)
    blocks = add_evaluation_roles(blocks, partition)
    calibration = blocks[blocks["evaluation_role"].eq("calibration")]
    if len(calibration) < minimum_calibration_blocks(alpha):
        raise AssertionError("Too few conformal calibration macroblocks")
    threshold = conformal_threshold(calibration["score"], alpha)
    if not math.isfinite(threshold):
        raise AssertionError("Feasible design unexpectedly produced an infinite threshold")
    blocks["p_value"] = conformal_p_values(calibration["score"], blocks["score"])
    blocks["alarm"] = blocks["p_value"] <= alpha

    healthy_test = blocks[blocks["evaluation_role"].eq("healthy_test")]
    faults = blocks[blocks["evaluation_role"].eq("fault_test")]
    evaluation = pd.concat([healthy_test, faults], ignore_index=True)
    labels = evaluation["evaluation_role"].eq("fault_test").astype(int)
    per_record = (
        faults.groupby(
            ["motor_id", "record_id", "fault_family", "severity_percent"],
            observed=True,
            sort=True,
        )
        .agg(
            macroblocks=("alarm", "size"),
            detected_macroblocks=("alarm", "sum"),
            block_detection_rate=("alarm", "mean"),
            any_alarm=("alarm", "any"),
            mean_score=("score", "mean"),
        )
        .reset_index()
    )
    if per_record["record_id"].nunique() != 14:
        raise AssertionError("Expected fourteen fault records per target motor")

    output_dir.mkdir(parents=True, exist_ok=True)
    blocks.to_csv(output_dir / "block_predictions.csv", index=False)
    per_record.to_csv(output_dir / "fault_record_summary.csv", index=False)
    summary: dict[str, object] = {
        "target_motor": target_motor,
        "method": METHOD,
        "feature_arm": FEATURE_ARM,
        "block_seconds": design.block_seconds,
        "windows_per_block": design.windows_per_block,
        "aggregation": aggregation,
        "aggregation_quantile": quantile,
        "aggregation_order_from_largest": aggregation_order_from_largest(
            design.windows_per_block, quantile
        ),
        "is_predeclared_primary": bool(
            design.is_primary_block_length and aggregation == PRIMARY_AGGREGATION
        ),
        "alpha": alpha,
        "adaptation_blocks": len(partition.adaptation),
        "calibration_blocks": len(calibration),
        "guard_blocks": len(partition.guard),
        "healthy_test_blocks": len(healthy_test),
        "threshold": threshold,
        "false_alarms": int(healthy_test["alarm"].sum()),
        "false_alarm_rate": float(healthy_test["alarm"].mean()),
        "fault_test_blocks": len(faults),
        "detected_fault_blocks": int(faults["alarm"].sum()),
        "block_detection_rate": float(faults["alarm"].mean()),
        "fault_record_mean_block_detection_rate": float(
            per_record["block_detection_rate"].mean()
        ),
        "fault_records_with_any_alarm": int(per_record["any_alarm"].sum()),
        "fault_records": len(per_record),
        "block_auroc": float(roc_auc_score(labels, evaluation["score"])),
        "block_auprc": float(average_precision_score(labels, evaluation["score"])),
        "block_counts_are_independent_repetitions": False,
    }
    return summary, per_record.assign(
        block_seconds=design.block_seconds,
        aggregation=aggregation,
        target_motor=target_motor,
    )


def aggregate_summaries(summaries: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, object]] = []
    for (block_seconds, aggregation), group in summaries.groupby(
        ["block_seconds", "aggregation"], sort=True
    ):
        healthy_blocks = int(group["healthy_test_blocks"].sum())
        false_alarms = int(group["false_alarms"].sum())
        wilson_lower, wilson_upper = wilson_interval(false_alarms, healthy_blocks)
        rows.append(
            {
                "block_seconds": block_seconds,
                "aggregation": aggregation,
                "is_predeclared_primary": bool(
                    group["is_predeclared_primary"].all()
                ),
                "calibration_blocks_per_motor": int(group["calibration_blocks"].iloc[0]),
                "healthy_test_blocks_pooled": healthy_blocks,
                "false_alarms_pooled": false_alarms,
                "pooled_false_alarm_rate": false_alarms / healthy_blocks,
                "pooled_far_wilson_lower_descriptive": wilson_lower,
                "pooled_far_wilson_upper_descriptive": wilson_upper,
                "mean_motor_false_alarm_rate": float(group["false_alarm_rate"].mean()),
                "max_motor_false_alarm_rate": float(group["false_alarm_rate"].max()),
                "mean_motor_block_detection_rate": float(
                    group["block_detection_rate"].mean()
                ),
                "worst_motor_block_detection_rate": float(
                    group["block_detection_rate"].min()
                ),
                "mean_motor_record_balanced_detection_rate": float(
                    group["fault_record_mean_block_detection_rate"].mean()
                ),
                "fault_records_with_any_alarm": int(
                    group["fault_records_with_any_alarm"].sum()
                ),
                "fault_records": int(group["fault_records"].sum()),
                "mean_motor_block_auroc": float(group["block_auroc"].mean()),
                "block_counts_are_independent_repetitions": False,
                "wilson_interval_is_descriptive_only": True,
            }
        )
    return pd.DataFrame(rows)


def write_interpretation(
    results_dir: Path, designs: list[BlockDesign], aggregates: pd.DataFrame
) -> None:
    feasible = [f"{design.block_seconds:g} s" for design in designs if design.finite_alpha_threshold]
    skipped = [
        f"- {design.block_seconds:g} s: {design.reason}"
        for design in designs
        if not design.finite_alpha_threshold
    ]
    primary = aggregates[
        aggregates["is_predeclared_primary"].astype(bool)
    ].iloc[0]
    text = f"""# Block-length and aggregation sensitivity

This is a **post-freeze sensitivity analysis**, not model selection. The primary
setting remains 3 s/max because the 3 s nuisance cycle was identified from
healthy autocorrelation before inspecting target-fault performance. All window
scores use the same scale-free Log-Euclidean detector, source/target healthy
reference intervals, and ridge fraction 0.01.

Feasible candidates at alpha=0.05 were {", ".join(feasible)}. They contain at
least 19 non-overlapping, time-ordered calibration macroblocks and one full
candidate macroblock on each side as a guard. Non-overlap does **not** prove
independence or exchangeability.

Skipped candidates:
{chr(10).join(skipped)}

The frozen 3 s/max setting produced pooled descriptive FAR
{primary['pooled_false_alarm_rate']:.4f}, mean motor block detection
{primary['mean_motor_block_detection_rate']:.4f}, worst-motor detection
{primary['worst_motor_block_detection_rate']:.4f}, and mean motor block AUROC
{primary['mean_motor_block_auroc']:.4f}.

Important inference limitation: changing macroblock length changes the number
of rows derived from the same underlying 120 s record. These rows are not new
biological/physical repetitions and must not be pooled across block lengths or
treated as independent sample-size gains. The Wilson intervals in the aggregate
CSV are descriptive diagnostics only; the three motors (and ultimately new
recording sessions) are the meaningful replication level. Also, q90 with the
`higher` order-statistic rule equals max for 1 s (5 windows) and 2 s (10 windows),
so those pairs are expected to be numerically identical.
"""
    (results_dir / "INTERPRETATION.md").write_text(text, encoding="utf-8")


def main() -> None:
    args = parse_args()
    if not math.isclose(args.alpha, 0.05, rel_tol=0.0, abs_tol=1e-12):
        raise ValueError("This frozen sensitivity protocol requires alpha=0.05")
    if not math.isclose(args.log_ridge_fraction, 0.01, rel_tol=0.0, abs_tol=1e-12):
        raise ValueError("This frozen sensitivity protocol requires log ridge fraction 0.01")
    designs = [
        audit_block_design(block_seconds, alpha=args.alpha)
        for block_seconds in args.block_seconds
    ]
    args.results_dir.mkdir(parents=True, exist_ok=True)
    pd.DataFrame([asdict(design) for design in designs]).to_csv(
        args.results_dir / "partition_feasibility.csv", index=False
    )

    frame = pd.read_csv(args.features)
    summaries: list[dict[str, object]] = []
    record_rows: list[pd.DataFrame] = []
    for fold in leave_one_motor_out():
        target_frame, scores = frozen_window_scores(
            frame,
            source_motors=fold.source_motors,
            target_motor=fold.target_motor,
            log_ridge_fraction=args.log_ridge_fraction,
        )
        for design in designs:
            if not design.finite_alpha_threshold:
                continue
            for aggregation in args.aggregations:
                output_dir = (
                    args.results_dir
                    / f"block_{design.block_seconds:g}s"
                    / aggregation
                    / f"target_{fold.target_motor}"
                )
                summary, records = evaluate_setting(
                    target_frame,
                    scores,
                    target_motor=fold.target_motor,
                    design=design,
                    aggregation=aggregation,
                    alpha=args.alpha,
                    output_dir=output_dir,
                )
                summaries.append(summary)
                record_rows.append(records)
                print(
                    f"{design.block_seconds:g}s/{aggregation} target={fold.target_motor}: "
                    f"FAR={summary['false_alarm_rate']:.3f}, "
                    f"detection={summary['block_detection_rate']:.3f}, "
                    f"AUROC={summary['block_auroc']:.3f}"
                )

    summary_frame = pd.DataFrame(summaries)
    summary_frame.to_csv(args.results_dir / "per_fold_summary.csv", index=False)
    pd.concat(record_rows, ignore_index=True).to_csv(
        args.results_dir / "per_fault_record_summary.csv", index=False
    )
    aggregates = aggregate_summaries(summary_frame)
    aggregates.to_csv(args.results_dir / "aggregate_summary.csv", index=False)
    write_interpretation(args.results_dir, designs, aggregates)
    (args.results_dir / "run_metadata.json").write_text(
        json.dumps(
            {
                "created_utc": datetime.now(UTC).isoformat(),
                "features": str(args.features.resolve()),
                "scikit_learn": sklearn.__version__,
                "method": METHOD,
                "feature_arm": FEATURE_ARM,
                "alpha": args.alpha,
                "window_seconds": WINDOW_SECONDS,
                "record_seconds": RECORD_SECONDS,
                "target_adaptation_seconds": TARGET_ADAPTATION_SECONDS,
                "source_reference_seconds": SOURCE_REFERENCE_SECONDS,
                "calibration_seconds": CALIBRATION_SECONDS,
                "log_ridge_fraction": args.log_ridge_fraction,
                "primary_setting": "3 s/max (frozen from healthy ACF)",
                "selection_uses_target_faults": False,
                "candidate_block_seconds": args.block_seconds,
                "candidate_aggregations": args.aggregations,
                "replication_caveat": (
                    "Macroblocks from one 120 s record are dependent derived units, not "
                    "independent recording repetitions; do not compare raw block counts as n."
                ),
            },
            indent=2,
        ),
        encoding="utf-8",
    )


if __name__ == "__main__":
    main()
