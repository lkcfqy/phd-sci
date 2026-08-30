"""Run the locked independent PMSG confirmation and frozen secondary comparators."""

from __future__ import annotations

import argparse
import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.metrics import average_precision_score, roc_auc_score

from pmsm_sci.faults.conditional import ContextSupportModel
from pmsm_sci.faults.conformal import conformal_p_values, conformal_threshold
from pmsm_sci.faults.paper3 import PAPER3_METHODS, PAPER3_OUTCOME_FEATURES, array_columns
from pmsm_sci.faults.paper3_modeling import paper3_detector_scores
from pmsm_sci.faults.statistics import wilson_interval

ALPHA = 0.05
SEED = 711
SELECTED_METHOD = "spline_residual"
PMSG_CONTEXT_COLUMNS = ("speed_rpm", "torque_setting_code")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--features",
        type=Path,
        default=Path("data/processed/paper3_pmsg_confirmation_features.csv.gz"),
    )
    parser.add_argument(
        "--protocol",
        type=Path,
        default=Path("docs/paper3_confirmation_protocol.md"),
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("results/paper3_pmsg_confirmation"),
    )
    return parser.parse_args()


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        while chunk := stream.read(8 * 1024 * 1024):
            digest.update(chunk)
    return digest.hexdigest()


def validate_input(frame: pd.DataFrame) -> None:
    required = {
        "record_id",
        "is_healthy_file",
        "standalone_role",
        "segment",
        "speed_rpm",
        "torque_setting_code",
        "fault_family",
        "terminal_a",
        "terminal_b",
        "fault_span_percent",
        "segment_window_id",
        *PAPER3_OUTCOME_FEATURES,
    }
    missing = required.difference(frame.columns)
    if missing:
        raise ValueError(f"PMSG feature table lacks required columns: {sorted(missing)}")
    if len(frame) != 2_493 or frame["record_id"].nunique() != 225:
        raise ValueError("Expected 2,493 rows from 225 PMSG records")
    segment_counts = frame["segment"].value_counts().to_dict()
    if segment_counts != {
        "recovery": 1_296,
        "pre_fault": 648,
        "fault_active": 432,
        "health_analysis": 117,
    }:
        raise ValueError(f"Unexpected frozen segment counts: {segment_counts}")
    health = frame[frame["segment"].eq("health_analysis")]
    role_records = health.groupby("standalone_role")["record_id"].nunique().to_dict()
    if role_records != {"calibration": 3, "fit": 4, "standalone_health_test": 2}:
        raise ValueError(f"Unexpected 4/3/2 healthy partition: {role_records}")


def add_scores(
    frame: pd.DataFrame,
    method_index: int,
) -> tuple[pd.DataFrame, float]:
    spec = PAPER3_METHODS[method_index]
    fit_mask = frame["standalone_role"].eq("fit") & frame["segment"].eq(
        "health_analysis"
    )
    calibration_mask = frame["standalone_role"].eq("calibration") & frame[
        "segment"
    ].eq("health_analysis")
    scores = paper3_detector_scores(
        spec,
        fit_context=array_columns(frame[fit_mask], PMSG_CONTEXT_COLUMNS),
        fit_outcomes=array_columns(frame[fit_mask], PAPER3_OUTCOME_FEATURES),
        fit_groups=frame.loc[fit_mask, "record_id"].to_numpy(),
        score_context=array_columns(frame, PMSG_CONTEXT_COLUMNS),
        score_outcomes=array_columns(frame, PAPER3_OUTCOME_FEATURES),
        seed=SEED + method_index,
    )
    support_model = ContextSupportModel(
        radius_multiplier=1.1,
        require_axis_bounds=True,
    ).fit(
        array_columns(frame[fit_mask], PMSG_CONTEXT_COLUMNS),
        array_columns(frame[calibration_mask], PMSG_CONTEXT_COLUMNS),
    )
    support = support_model.evaluate(array_columns(frame, PMSG_CONTEXT_COLUMNS))
    calibration_scores = scores[calibration_mask.to_numpy()]
    if len(calibration_scores) != 39:
        raise AssertionError("PMSG threshold must use 39 calibration windows")
    threshold = conformal_threshold(calibration_scores, ALPHA)
    if not np.isfinite(threshold):
        raise AssertionError("PMSG calibration must resolve alpha=.05")

    output = frame.copy()
    output["method"] = spec.name
    output["score"] = scores
    output["context_distance"] = support.distance
    output["supported"] = support.supported
    output["p_value"] = conformal_p_values(calibration_scores, scores)
    output["raw_alarm"] = output["p_value"].le(ALPHA)
    output["actionable_alarm"] = output["raw_alarm"] & output["supported"]
    output["threshold"] = threshold
    return output, threshold


def _aggregate_segment(
    frame: pd.DataFrame,
    segment: str,
    prefix: str,
) -> pd.DataFrame:
    subset = frame[frame["segment"].eq(segment)]
    return (
        subset.groupby("record_id", sort=True)
        .agg(
            **{
                f"{prefix}_windows": ("segment_window_id", "size"),
                f"{prefix}_max_score": ("score", "max"),
                f"{prefix}_raw_alarms": ("raw_alarm", "sum"),
                f"{prefix}_actionable_alarms": ("actionable_alarm", "sum"),
                f"{prefix}_any_raw_alarm": ("raw_alarm", "any"),
                f"{prefix}_any_actionable_alarm": ("actionable_alarm", "any"),
                f"{prefix}_full_support": ("supported", "all"),
            }
        )
        .reset_index()
    )


def build_record_table(
    scored: pd.DataFrame,
    *,
    expected_records: int = 216,
) -> pd.DataFrame:
    metadata_columns = [
        "record_id",
        "speed_rpm",
        "torque_setting_code",
        "fault_family",
        "terminal_a",
        "terminal_b",
        "fault_span_percent",
    ]
    metadata = (
        scored.loc[scored["segment"].eq("fault_active"), metadata_columns]
        .drop_duplicates()
        .reset_index(drop=True)
    )
    if len(metadata) != expected_records:
        raise AssertionError(
            f"Expected metadata for {expected_records} PMSG fault records"
        )
    pre = _aggregate_segment(scored, "pre_fault", "pre")
    fault = _aggregate_segment(scored, "fault_active", "fault")
    recovery = _aggregate_segment(scored, "recovery", "recovery")
    records = metadata.merge(pre, on="record_id", validate="one_to_one")
    records = records.merge(fault, on="record_id", validate="one_to_one")
    records = records.merge(recovery, on="record_id", validate="one_to_one")
    if not records["pre_windows"].eq(3).all() or not records["fault_windows"].eq(2).all():
        raise AssertionError("PMSG primary records must have 3 pre/2 fault windows")

    active = scored[scored["segment"].eq("fault_active")].copy()
    alarm_window = (
        active.loc[active["actionable_alarm"]]
        .groupby("record_id")["segment_window_id"]
        .min()
    )
    records["first_alarm_window"] = records["record_id"].map(alarm_window)
    records["command_to_alarm_s"] = records["first_alarm_window"].map(
        {0.0: 0.2, 1.0: 0.4}
    )
    records["delay_right_censored_beyond_0p4s"] = records[
        "command_to_alarm_s"
    ].isna()
    records["pre_session_false_alarm"] = records["pre_any_actionable_alarm"]
    records["fault_record_detection"] = records["fault_any_actionable_alarm"]
    records["fault_record_abstention"] = ~records["fault_full_support"]
    records["method"] = scored["method"].iloc[0]
    return records


def summarize_method(
    scored: pd.DataFrame,
    records: pd.DataFrame,
    threshold: float,
) -> dict[str, object]:
    pre = scored[scored["segment"].eq("pre_fault")]
    fault = scored[scored["segment"].eq("fault_active")]
    standalone = scored[
        scored["standalone_role"].eq("standalone_health_test")
        & scored["segment"].eq("health_analysis")
    ]
    pre_false = int(records["pre_session_false_alarm"].sum())
    detected = int(records["fault_record_detection"].sum())
    abstained = int(records["fault_record_abstention"].sum())
    far_lower, far_upper = wilson_interval(pre_false, len(records))
    detection_lower, detection_upper = wilson_interval(detected, len(records))
    labels = np.concatenate([np.zeros(len(records)), np.ones(len(records))])
    record_scores = np.concatenate(
        [records["pre_max_score"].to_numpy(), records["fault_max_score"].to_numpy()]
    )
    method = str(scored["method"].iloc[0])
    selected = method == SELECTED_METHOD
    far_point_gate = pre_false / len(records) <= 0.05
    far_upper_gate = far_upper <= 0.10
    detection_point_gate = detected / len(records) >= 0.75
    detection_lower_gate = detection_lower >= 0.65
    abstention_gate = abstained / len(records) <= 0.10
    return {
        "method": method,
        "confirmatory_selected_method": selected,
        "threshold": threshold,
        "calibration_windows": 39,
        "standalone_health_test_windows": len(standalone),
        "standalone_health_window_alarms": int(standalone["actionable_alarm"].sum()),
        "standalone_health_window_far": float(standalone["actionable_alarm"].mean()),
        "standalone_health_records_any_alarm": int(
            standalone.groupby("record_id")["actionable_alarm"].any().sum()
        ),
        "pre_fault_windows": len(pre),
        "pre_fault_window_alarms": int(pre["actionable_alarm"].sum()),
        "pre_fault_window_far": float(pre["actionable_alarm"].mean()),
        "pre_fault_records": len(records),
        "pre_fault_sessions_with_alarm": pre_false,
        "pre_fault_session_far": pre_false / len(records),
        "pre_fault_session_far_wilson_lower": far_lower,
        "pre_fault_session_far_wilson_upper": far_upper,
        "fault_windows": len(fault),
        "fault_window_alarms": int(fault["actionable_alarm"].sum()),
        "fault_window_actionable_detection": float(fault["actionable_alarm"].mean()),
        "fault_records": len(records),
        "fault_records_detected": detected,
        "fault_record_detection": detected / len(records),
        "fault_record_detection_wilson_lower": detection_lower,
        "fault_record_detection_wilson_upper": detection_upper,
        "fault_records_abstained": abstained,
        "fault_record_abstention": abstained / len(records),
        "detected_by_first_window": int(
            records["command_to_alarm_s"].eq(0.2).sum()
        ),
        "detected_by_second_window_only": int(
            records["command_to_alarm_s"].eq(0.4).sum()
        ),
        "censored_beyond_0p4s": int(
            records["delay_right_censored_beyond_0p4s"].sum()
        ),
        "record_score_auroc": float(roc_auc_score(labels, record_scores)),
        "record_score_auprc": float(average_precision_score(labels, record_scores)),
        "gate_far_point_le_0p05": far_point_gate,
        "gate_far_wilson_upper_le_0p10": far_upper_gate,
        "gate_detection_point_ge_0p75": detection_point_gate,
        "gate_detection_wilson_lower_ge_0p65": detection_lower_gate,
        "gate_abstention_le_0p10": abstention_gate,
        "confirmatory_gates_all_pass": bool(
            selected
            and far_point_gate
            and far_upper_gate
            and detection_point_gate
            and detection_lower_gate
            and abstention_gate
        ),
    }


def selected_condition_tables(records: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    rows: list[dict[str, object]] = []
    facets = (
        ("fault_family", ["fault_family"]),
        ("speed_rpm", ["speed_rpm"]),
        ("torque_setting_code", ["torque_setting_code"]),
        ("speed_by_torque", ["speed_rpm", "torque_setting_code"]),
    )
    for facet, columns in facets:
        grouper: str | list[str] = columns[0] if len(columns) == 1 else columns
        for key, group in records.groupby(grouper, observed=True, sort=True):
            key_values = (key,) if not isinstance(key, tuple) else key
            detected = int(group["fault_record_detection"].sum())
            false_alarms = int(group["pre_session_false_alarm"].sum())
            detection_ci = wilson_interval(detected, len(group))
            far_ci = wilson_interval(false_alarms, len(group))
            rows.append(
                {
                    "facet": facet,
                    "level": " / ".join(str(item) for item in key_values),
                    "records": len(group),
                    "detected": detected,
                    "record_detection": detected / len(group),
                    "detection_wilson_lower": detection_ci[0],
                    "detection_wilson_upper": detection_ci[1],
                    "pre_false_alarms": false_alarms,
                    "pre_session_far": false_alarms / len(group),
                    "far_wilson_lower": far_ci[0],
                    "far_wilson_upper": far_ci[1],
                    "record_abstention": float(group["fault_record_abstention"].mean()),
                }
            )
    condition = pd.DataFrame(rows)
    fault_case = (
        records.groupby(
            [
                "fault_family",
                "terminal_a",
                "terminal_b",
                "fault_span_percent",
            ],
            observed=True,
            sort=True,
        )
        .agg(
            conditions=("record_id", "size"),
            detection=("fault_record_detection", "mean"),
            pre_session_far=("pre_session_false_alarm", "mean"),
            first_window_detection=("command_to_alarm_s", lambda values: values.eq(0.2).mean()),
        )
        .reset_index()
    )
    return condition, fault_case


def main() -> None:
    args = parse_args()
    frame = pd.read_csv(args.features)
    validate_input(frame)
    window_tables: list[pd.DataFrame] = []
    record_tables: list[pd.DataFrame] = []
    summaries: list[dict[str, object]] = []
    for method_index, spec in enumerate(PAPER3_METHODS):
        scored, threshold = add_scores(frame, method_index)
        records = build_record_table(scored)
        summary = summarize_method(scored, records, threshold)
        window_tables.append(scored)
        record_tables.append(records)
        summaries.append(summary)
        print(
            f"{spec.name}: pre-session FAR={summary['pre_fault_session_far']:.4f}, "
            f"record detection={summary['fault_record_detection']:.4f}, "
            f"abstention={summary['fault_record_abstention']:.4f}"
        )
    windows = pd.concat(window_tables, ignore_index=True)
    records = pd.concat(record_tables, ignore_index=True)
    aggregate = pd.DataFrame(summaries)
    selected_records = records[records["method"].eq(SELECTED_METHOD)].copy()
    condition, fault_case = selected_condition_tables(selected_records)
    selected_summary = next(
        row for row in summaries if row["method"] == SELECTED_METHOD
    )

    args.output_dir.mkdir(parents=True, exist_ok=True)
    windows.to_csv(args.output_dir / "per_window_results.csv", index=False)
    records.to_csv(args.output_dir / "per_record_results.csv", index=False)
    aggregate.to_csv(args.output_dir / "aggregate_summary.csv", index=False)
    condition.to_csv(args.output_dir / "selected_condition_summary.csv", index=False)
    fault_case.to_csv(args.output_dir / "selected_fault_case_summary.csv", index=False)
    primary = {
        "created_utc": datetime.now(UTC).isoformat(),
        "selected_method": SELECTED_METHOD,
        "confirmation_result": selected_summary,
        "interpretation": (
            "Confirmatory gates concern the pre-frozen spline_residual only. Comparator "
            "results cannot replace it. All intervals are conditional/descriptive for one PMSG."
        ),
        "input_features": str(args.features.resolve()),
        "input_features_sha256": sha256(args.features),
        "protocol": str(args.protocol.resolve()),
        "protocol_sha256": sha256(args.protocol),
    }
    (args.output_dir / "selected_method_primary.json").write_text(
        json.dumps(primary, indent=2), encoding="utf-8"
    )
    metadata = {
        "created_utc": datetime.now(UTC).isoformat(),
        "alpha": ALPHA,
        "seed": SEED,
        "methods": [spec.name for spec in PAPER3_METHODS],
        "selected_method": SELECTED_METHOD,
        "rows_per_method": len(frame),
        "fault_records_per_method": 216,
        "calibration_windows": 39,
        "support_radius_multiplier": 1.1,
        "support_requires_axis_bounds": True,
        "outcome_features": list(PAPER3_OUTCOME_FEATURES),
        "result_hashes": {
            path.name: sha256(path)
            for path in sorted(args.output_dir.glob("*.csv"))
        },
    }
    (args.output_dir / "run_metadata.json").write_text(
        json.dumps(metadata, indent=2), encoding="utf-8"
    )
    print("\nLocked selected-method confirmation:")
    print(json.dumps(selected_summary, indent=2))
    print(f"wrote results to {args.output_dir.resolve()}")


if __name__ == "__main__":
    main()
