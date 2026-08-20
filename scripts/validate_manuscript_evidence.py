"""Recompute headline manuscript evidence from lower-grain frozen result tables."""

from __future__ import annotations

import argparse
import json
import math
from pathlib import Path

import pandas as pd
from sklearn.metrics import roc_auc_score

ROOT = Path(__file__).resolve().parents[1]
TARGET_MOTORS = ("1kW", "1.5kW", "3kW")
PROPOSED = "log_euclidean_entity_covariance"
PRIMARY_SEED = 20260820


def _bool(series: pd.Series) -> pd.Series:
    if pd.api.types.is_bool_dtype(series):
        return series.astype(bool)
    normalized = series.astype(str).str.strip().str.casefold()
    if not set(normalized.unique()).issubset({"true", "false"}):
        raise ValueError(f"Invalid boolean values: {sorted(normalized.unique())}")
    return normalized.eq("true")


def _assert_close(actual: float, expected: float, *, tolerance: float = 1e-12) -> None:
    if not math.isclose(actual, expected, rel_tol=0.0, abs_tol=tolerance):
        raise AssertionError(f"Expected {expected}, got {actual}")


def wilson_interval(events: int, trials: int, *, z: float = 1.959963984540054) -> tuple[float, float]:
    if not 0 <= events <= trials or trials <= 0:
        raise ValueError("Wilson interval requires 0 <= events <= trials and trials > 0")
    proportion = events / trials
    denominator = 1 + z**2 / trials
    center = (proportion + z**2 / (2 * trials)) / denominator
    half_width = z * math.sqrt(
        proportion * (1 - proportion) / trials + z**2 / (4 * trials**2)
    ) / denominator
    return max(0.0, center - half_width), min(1.0, center + half_width)


def recompute_kaist(root: Path) -> dict[str, object]:
    fold_rows: list[dict[str, object]] = []
    for target in TARGET_MOTORS:
        path = (
            root
            / "results"
            / "healthy_covariance_v0"
            / f"target_{target}"
            / "scale_free"
            / PROPOSED
            / "block_predictions.csv"
        )
        frame = pd.read_csv(path)
        healthy = _bool(frame["is_healthy"])
        block_id = frame["block_id"].astype(int)
        health_test = frame.loc[healthy & block_id.between(26, 39)].copy()
        fault = frame.loc[~healthy].copy()
        if len(health_test) != 14 or len(fault) != 560:
            raise AssertionError(f"Unexpected KAIST fold rows for {target}")
        health_alarms = int(_bool(health_test["alarm"]).sum())
        fault_alarms = int(_bool(fault["alarm"]).sum())
        labels = [0] * len(health_test) + [1] * len(fault)
        scores = pd.concat([health_test["score"], fault["score"]], ignore_index=True)
        fold_rows.append(
            {
                "target_motor": target,
                "healthy_test_blocks": len(health_test),
                "false_alarms": health_alarms,
                "fault_records": int(fault["record_id"].nunique()),
                "fault_blocks": len(fault),
                "fault_alarms": fault_alarms,
                "detection_rate": fault_alarms / len(fault),
                "block_auroc": roc_auc_score(labels, scores),
            }
        )

    folds = pd.DataFrame(fold_rows)
    proposed = {
        "healthy_records": len(folds),
        "healthy_test_blocks": int(folds["healthy_test_blocks"].sum()),
        "false_alarms": int(folds["false_alarms"].sum()),
        "fault_records": int(folds["fault_records"].sum()),
        "fault_blocks": int(folds["fault_blocks"].sum()),
        "fault_alarms": int(folds["fault_alarms"].sum()),
        "mean_detection_rate": float(folds["detection_rate"].mean()),
        "worst_motor_detection_rate": float(folds["detection_rate"].min()),
        "mean_block_auroc": float(folds["block_auroc"].mean()),
        "folds": fold_rows,
    }
    _assert_close(proposed["mean_detection_rate"], 0.9571428571428572)
    _assert_close(proposed["mean_block_auroc"], 0.9993197278911564)

    records = pd.read_csv(root / "results" / "oneclass_baselines" / "record_summary.csv")
    records["is_healthy"] = _bool(records["is_healthy"])
    primary = records.loc[
        records["method"].eq("source_target_isolation_forest")
        & records["seed"].astype(int).eq(PRIMARY_SEED)
    ].copy()
    health = primary.loc[primary["is_healthy"]]
    faults = primary.loc[~primary["is_healthy"]]
    if len(health) != 3 or len(faults) != 42:
        raise AssertionError("Unexpected primary Isolation Forest record inventory")
    isolation_forest = {
        "healthy_records": len(health),
        "healthy_test_blocks": int(health["blocks"].sum()),
        "false_alarms": int(health["alarms"].sum()),
        "fault_records": len(faults),
        "record_macro_detection_rate": float(faults["block_alarm_rate"].mean()),
        "worst_motor_detection_rate": float(
            faults.groupby("target_motor")["block_alarm_rate"].mean().min()
        ),
    }
    _assert_close(isolation_forest["record_macro_detection_rate"], 0.9607142857142857)

    comparison = pd.read_csv(
        root / "results" / "oneclass_baselines" / "comparison_to_proposed.csv"
    )
    row = comparison.loc[
        comparison["baseline"].eq("source_target_isolation_forest")
    ].iloc[0]
    paired = {
        "proposed_minus_isolation_forest": float(row["proposed_minus_baseline_detection"]),
        "ci_lower": float(row["paired_record_bootstrap_ci_lower"]),
        "ci_upper": float(row["paired_record_bootstrap_ci_upper"]),
        "fault_records": int(row["fault_records"]),
    }
    if not paired["ci_lower"] <= 0 <= paired["ci_upper"]:
        raise AssertionError("Proposed versus Isolation Forest interval no longer crosses zero")
    return {"proposed": proposed, "balanced_isolation_forest": isolation_forest, "paired": paired}


def _external_method(root: Path, method: str) -> pd.DataFrame:
    path = (
        root
        / "results"
        / "external_pmsm_validation"
        / method
        / "system_block_predictions.csv"
    )
    frame = pd.read_csv(path)
    frame["alarm"] = _bool(frame["alarm"])
    frame["is_healthy"] = _bool(frame["is_healthy"])
    return frame


def _summarize_external(frame: pd.DataFrame) -> dict[str, object]:
    health = frame.loc[frame["role"].eq("health_test")].copy()
    fault = frame.loc[frame["role"].eq("fault_test")].copy()
    if len(health) != 32 or len(fault) != 384:
        raise AssertionError("Unexpected external health/fault block inventory")
    record_rates = fault.groupby("record_id", sort=True)["alarm"].mean()
    false_alarms = int(health["alarm"].sum())
    wilson_lower, wilson_upper = wilson_interval(false_alarms, len(health))
    max_load_far = float(health.groupby("load_nm")["alarm"].mean().max())
    labels = [0] * len(health) + [1] * len(fault)
    scores = pd.concat([health["score"], fault["score"]], ignore_index=True)
    return {
        "health_test_records": int(health["record_id"].nunique()),
        "health_test_blocks": len(health),
        "false_alarms": false_alarms,
        "wilson_lower": wilson_lower,
        "wilson_upper": wilson_upper,
        "max_load_false_alarm_rate": max_load_far,
        "h1_empirical_pass": wilson_upper <= 0.12 and max_load_far <= 0.15,
        "fault_records": int(fault["record_id"].nunique()),
        "fault_blocks": len(fault),
        "fault_alarms": int(fault["alarm"].sum()),
        "record_macro_detection_rate": float(record_rates.mean()),
        "record_any_alarm_rate": float((record_rates > 0).mean()),
        "block_auroc": float(roc_auc_score(labels, scores)),
    }


def recompute_external(root: Path) -> dict[str, object]:
    proposed_frame = _external_method(root, PROPOSED)
    target_mcd_frame = _external_method(root, "target_min_cov_det")
    proposed = _summarize_external(proposed_frame)
    target_mcd = _summarize_external(target_mcd_frame)
    _assert_close(proposed["record_macro_detection_rate"], 0.25)
    _assert_close(proposed["block_auroc"], 0.6354166666666666)
    _assert_close(proposed["wilson_upper"], 0.1574426382001255)
    _assert_close(target_mcd["record_macro_detection_rate"], 0.7005208333333334)
    _assert_close(target_mcd["block_auroc"], 0.9267578125)

    proposed_fault = proposed_frame.loc[proposed_frame["role"].eq("fault_test")].copy()
    target_mcd_fault = target_mcd_frame.loc[target_mcd_frame["role"].eq("fault_test")].copy()
    proposed_records = proposed_fault.groupby("record_id", sort=True)["alarm"].mean()
    target_mcd_records = target_mcd_fault.groupby("record_id", sort=True)["alarm"].mean()
    paired_difference = float((target_mcd_records - proposed_records).mean())
    _assert_close(paired_difference, 0.4505208333333334)

    block_alarm_counts = {
        str(int(block)): int(group["alarm"].sum())
        for block, group in proposed_fault.groupby("block_id", sort=True)
    }
    if [block_alarm_counts[str(block)] for block in range(3)] != [0, 0, 0]:
        raise AssertionError("First three proposed external blocks no longer have zero alarms")
    if block_alarm_counts["7"] != 48:
        raise AssertionError("Final proposed external block no longer alarms on all records")

    load_detection = {
        f"{float(load):g}": float(group["alarm"].mean())
        for load, group in proposed_fault.groupby("load_nm", sort=True)
    }
    _assert_close(load_detection["0"], 0.5625)
    _assert_close(load_detection["35"], 0.125)

    fault_conditions = proposed_fault[["fault_turns", "fault_phase"]].drop_duplicates()
    phase_sets = {
        str(int(turns)): tuple(sorted(group["fault_phase"].astype(str).unique()))
        for turns, group in fault_conditions.groupby("fault_turns", sort=True)
    }
    expected_phase_sets = {
        "1": ("u",),
        "2": ("v",),
        "3": ("u",),
        "4": ("v",),
        "5": ("u",),
        "6": ("u",),
    }
    if phase_sets != expected_phase_sets:
        raise AssertionError(f"Unexpected fault-turn/phase mapping: {phase_sets}")

    seed_ranges = pd.read_csv(
        root / "results" / "external_seed_sensitivity" / "aggregate_seed_ranges.csv"
    )
    seed_row = seed_ranges.loc[seed_ranges["method"].eq("target_min_cov_det")].iloc[0]
    seed_sensitivity = {
        "seeds": int(seed_row["seeds"]),
        "detection_min": float(seed_row["detection_min"]),
        "detection_max": float(seed_row["detection_max"]),
        "false_alarms_min": int(seed_row["false_alarms_min"]),
        "false_alarms_max": int(seed_row["false_alarms_max"]),
        "h1_pass_seeds": int(seed_row["h1_pass_seeds"]),
    }

    sampling = pd.read_csv(
        root / "results" / "sampling_rate_sensitivity" / "external_method_comparison.csv"
    )
    sampling_row = sampling.loc[sampling["method"].eq(PROPOSED)].iloc[0]
    sampling_sensitivity = {
        "detection_100khz": float(sampling_row["fault_block_detection_rate_source_100khz"]),
        "detection_10khz": float(sampling_row["fault_block_detection_rate_source_10khz"]),
        "auroc_100khz": float(sampling_row["block_auroc_source_100khz"]),
        "auroc_10khz": float(sampling_row["block_auroc_source_10khz"]),
        "false_alarms_100khz": int(sampling_row["false_alarms_source_100khz"]),
        "false_alarms_10khz": int(sampling_row["false_alarms_source_10khz"]),
    }
    return {
        "proposed": proposed,
        "target_min_cov_det": target_mcd,
        "paired_target_mcd_minus_proposed": paired_difference,
        "proposed_alarm_counts_by_block": block_alarm_counts,
        "proposed_detection_by_load_nm": load_detection,
        "fault_turn_phase_mapping": phase_sets,
        "fault_turn_phase_fully_crossed": False,
        "target_min_cov_det_seed_sensitivity": seed_sensitivity,
        "sampling_rate_sensitivity": sampling_sensitivity,
    }


def recompute_transient(root: Path) -> dict[str, object]:
    primary = pd.read_csv(
        root / "results" / "transient_feature_build" / "record_compatibility.csv"
    )
    repaired = pd.read_csv(
        root
        / "results"
        / "transient_feature_build_post_reveal_implicit_time"
        / "record_compatibility.csv"
    )
    primary_compatible = _bool(primary["main_endpoint_compatible"])
    repaired_compatible = _bool(repaired["main_endpoint_compatible"])
    repaired_counts = {
        motor: {
            "compatible": int(repaired_compatible.loc[repaired["motor_id"].eq(motor)].sum()),
            "official": int(repaired["motor_id"].eq(motor).sum()),
        }
        for motor in ("200W", "20kW")
    }
    if int(primary_compatible.sum()) != 0 or len(primary) != 21:
        raise AssertionError("Frozen transient compatibility result changed")
    if repaired_counts != {
        "200W": {"compatible": 12, "official": 12},
        "20kW": {"compatible": 4, "official": 9},
    }:
        raise AssertionError(f"Unexpected repaired transient counts: {repaired_counts}")

    aggregate = pd.read_csv(
        root
        / "results"
        / "transient_pmsm_validation_post_reveal_200w"
        / "aggregate_summary.csv"
    )
    selected = aggregate.loc[
        aggregate["method"].isin([PROPOSED, "target_min_cov_det"])
        & aggregate["seed"].astype(int).eq(PRIMARY_SEED)
    ].set_index("method")
    methods = {
        method: {
            "false_alarms": int(row["false_alarms"]),
            "healthy_windows": int(row["healthy_windows"]),
            "record_macro_detection_rate": float(row["record_macro_detection_rate"]),
            "mean_record_auroc": float(row["mean_record_auroc"]),
        }
        for method, row in selected.iterrows()
    }
    return {
        "primary_parser_compatible": int(primary_compatible.sum()),
        "primary_official_records": len(primary),
        "repaired_by_motor": repaired_counts,
        "post_reveal_200w": methods,
    }


def validate_manuscript_text(root: Path, evidence: dict[str, object]) -> list[str]:
    text = (root / "paper" / "manuscript.md").read_text(encoding="utf-8")
    required = (
        "95.71% fault-block detection",
        "96.07% record-macro detection",
        "1/32 = 3.125%",
        "25.00% of the 384 ordered fault blocks",
        "70.05% detection",
        "AUROC 0.9268",
        "40.62--49.48%",
        "fault-turn count and fault phase are not fully crossed",
        "primary two-dataset analysis",
    )
    missing = [phrase for phrase in required if phrase not in text]
    if missing:
        raise AssertionError(f"Required manuscript evidence text missing: {missing}")
    if evidence["external"]["fault_turn_phase_fully_crossed"]:
        raise AssertionError("Fault-turn/phase confounding expectation changed")
    return list(required)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=ROOT)
    parser.add_argument(
        "--output",
        type=Path,
        default=ROOT / "results" / "manuscript_evidence_validation" / "evidence.json",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    evidence: dict[str, object] = {
        "kaist": recompute_kaist(args.root),
        "external": recompute_external(args.root),
        "transient": recompute_transient(args.root),
    }
    evidence["manuscript_text_checks"] = validate_manuscript_text(args.root, evidence)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(evidence, indent=2, sort_keys=True), encoding="utf-8")
    print(json.dumps({"status": "pass", "output": str(args.output), "sections": 3}))


if __name__ == "__main__":
    main()
