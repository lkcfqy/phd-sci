"""Run the final post-reveal conditioned session-anchor PMSG analysis."""

from __future__ import annotations

import argparse
import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path

import pandas as pd

from pmsm_sci.faults.conditional import ConditionalResidualDetector, ContextSupportModel
from pmsm_sci.faults.conformal import conformal_p_values, conformal_threshold
from pmsm_sci.faults.paper3 import PAPER3_OUTCOME_FEATURES
from pmsm_sci.faults.pmsg_session import (
    pmsg_session_residual_table,
    pmsg_topology_assignments,
)
from pmsm_sci.faults.statistics import wilson_interval

ALPHA = 0.05
CONTEXT_COLUMNS = ("speed_rpm", "torque_setting_code")


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
        default=Path("docs/paper3_post_reveal_conditioned_anchor_protocol.md"),
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("results/paper3_pmsg_conditioned_anchor"),
    )
    return parser.parse_args()


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        while chunk := stream.read(8 * 1024 * 1024):
            digest.update(chunk)
    return digest.hexdigest()


def main() -> None:
    args = parse_args()
    frame = pd.read_csv(args.features)
    residuals = pmsg_session_residual_table(frame)
    cases = pmsg_topology_assignments(residuals)
    rows = residuals[~residuals["is_healthy_file"].astype(bool)].merge(
        cases[
            [
                "fault_family",
                "terminal_a",
                "terminal_b",
                "topology_bucket",
                "topology_id",
            ]
        ],
        on=["fault_family", "terminal_a", "terminal_b"],
        validate="many_to_one",
    )
    outcome_columns = [f"residual__{column}" for column in PAPER3_OUTCOME_FEATURES]
    fold_tables: list[pd.DataFrame] = []
    fold_summaries: list[dict[str, object]] = []
    for fold in range(3):
        test_bucket = fold
        calibration_bucket = (fold + 1) % 3
        fit_bucket = (fold + 2) % 3
        fit = rows[
            rows["topology_bucket"].eq(fit_bucket)
            & rows["evaluation_role"].eq("pre_fault_test")
        ]
        calibration = rows[
            rows["topology_bucket"].eq(calibration_bucket)
            & rows["evaluation_role"].eq("pre_fault_test")
        ]
        test = rows[
            rows["topology_bucket"].eq(test_bucket)
            & rows["evaluation_role"].isin(["pre_fault_test", "fault_test"])
        ].copy()
        if len(fit) != 72 or len(calibration) != 72 or len(test) != 216:
            raise AssertionError("Each fold requires 72 fit/72 calibration/216 test windows")
        detector = ConditionalResidualDetector(
            mean_model="spline",
            local_scale=False,
            crossfit_splits=4,
            ridge_alpha=1.0,
            spline_knots=4,
            spline_degree=2,
            scale_clip=(0.25, 4.0),
        ).fit(
            fit[list(CONTEXT_COLUMNS)],
            fit[outcome_columns],
            groups=fit["topology_id"].to_numpy(),
        )
        calibration_scores = detector.score(
            calibration[list(CONTEXT_COLUMNS)], calibration[outcome_columns]
        )
        threshold = conformal_threshold(calibration_scores, ALPHA)
        test["score"] = detector.score(
            test[list(CONTEXT_COLUMNS)], test[outcome_columns]
        )
        test["p_value"] = conformal_p_values(calibration_scores, test["score"])
        test["raw_alarm"] = test["p_value"].le(ALPHA)
        support_model = ContextSupportModel(
            radius_multiplier=1.1, require_axis_bounds=True
        ).fit(fit[list(CONTEXT_COLUMNS)], calibration[list(CONTEXT_COLUMNS)])
        support = support_model.evaluate(test[list(CONTEXT_COLUMNS)])
        test["supported"] = support.supported
        test["actionable_alarm"] = test["raw_alarm"] & test["supported"]
        test["outer_fold"] = fold
        test["fit_bucket"] = fit_bucket
        test["calibration_bucket"] = calibration_bucket
        test["threshold"] = threshold
        fold_tables.append(test)
        pre = test[test["evaluation_role"].eq("pre_fault_test")]
        active = test[test["evaluation_role"].eq("fault_test")]
        detection = active.groupby("record_id")["actionable_alarm"].any()
        abstention = ~active.groupby("record_id")["supported"].all()
        fold_summaries.append(
            {
                "outer_fold": fold,
                "fit_bucket": fit_bucket,
                "calibration_bucket": calibration_bucket,
                "test_bucket": test_bucket,
                "threshold": threshold,
                "pre_false_alarms": int(pre["actionable_alarm"].sum()),
                "pre_session_far": float(pre["actionable_alarm"].mean()),
                "fault_records_detected": int(detection.sum()),
                "fault_record_detection": float(detection.mean()),
                "fault_records_abstained": int(abstention.sum()),
            }
        )
    windows = pd.concat(fold_tables, ignore_index=True)
    metadata_columns = [
        "record_id",
        "fault_family",
        "speed_rpm",
        "torque_setting_code",
        "terminal_a",
        "terminal_b",
        "fault_span_percent",
        "topology_id",
        "topology_bucket",
        "outer_fold",
        "threshold",
    ]
    records = windows[metadata_columns].drop_duplicates().reset_index(drop=True)
    pre = windows[windows["evaluation_role"].eq("pre_fault_test")]
    active = windows[windows["evaluation_role"].eq("fault_test")]
    records = records.merge(
        pre.groupby("record_id").agg(
            pre_score=("score", "max"),
            pre_session_false_alarm=("actionable_alarm", "any"),
        ),
        on="record_id",
        validate="one_to_one",
    )
    records = records.merge(
        active.groupby("record_id").agg(
            fault_score=("score", "max"),
            fault_record_detection=("actionable_alarm", "any"),
            fault_full_support=("supported", "all"),
        ),
        on="record_id",
        validate="one_to_one",
    )
    first_alarm = (
        active.loc[active["actionable_alarm"]]
        .groupby("record_id")["segment_window_id"]
        .min()
    )
    records["first_alarm_window"] = records["record_id"].map(first_alarm)
    records["command_to_alarm_s"] = records["first_alarm_window"].map(
        {0.0: 0.2, 1.0: 0.4}
    )
    false_alarms = int(records["pre_session_false_alarm"].sum())
    detected = int(records["fault_record_detection"].sum())
    abstained = int((~records["fault_full_support"]).sum())
    far_ci = wilson_interval(false_alarms, len(records))
    detection_ci = wilson_interval(detected, len(records))
    summary = {
        "analysis_status": "final post-reveal topology-disjoint internal validation",
        "method": "conditioned_matched_session_anchor",
        "folds": 3,
        "records": len(records),
        "pre_false_alarms": false_alarms,
        "pre_session_far": false_alarms / len(records),
        "pre_session_far_wilson_lower": far_ci[0],
        "pre_session_far_wilson_upper": far_ci[1],
        "fault_records_detected": detected,
        "fault_record_detection": detected / len(records),
        "fault_record_detection_wilson_lower": detection_ci[0],
        "fault_record_detection_wilson_upper": detection_ci[1],
        "fault_records_abstained": abstained,
        "fault_record_abstention": abstained / len(records),
        "detected_first_window": int(records["command_to_alarm_s"].eq(0.2).sum()),
        "detected_second_window_only": int(records["command_to_alarm_s"].eq(0.4).sum()),
        "censored_beyond_0p4s": int(records["command_to_alarm_s"].isna().sum()),
        "original_gates_for_context": {
            "far_point_le_0p05": false_alarms / len(records) <= 0.05,
            "far_wilson_upper_le_0p10": far_ci[1] <= 0.10,
            "detection_point_ge_0p75": detected / len(records) >= 0.75,
            "detection_wilson_lower_ge_0p65": detection_ci[0] >= 0.65,
            "abstention_le_0p10": abstained / len(records) <= 0.10,
        },
    }
    args.output_dir.mkdir(parents=True, exist_ok=True)
    windows.to_csv(args.output_dir / "per_window_results.csv", index=False)
    records.to_csv(args.output_dir / "per_record_results.csv", index=False)
    pd.DataFrame(fold_summaries).to_csv(
        args.output_dir / "per_fold_summary.csv", index=False
    )
    cases.to_csv(args.output_dir / "topology_assignments.csv", index=False)
    payload = {
        "created_utc": datetime.now(UTC).isoformat(),
        "protocol": str(args.protocol.resolve()),
        "protocol_sha256": sha256(args.protocol),
        "input_features": str(args.features.resolve()),
        "input_features_sha256": sha256(args.features),
        "summary": summary,
    }
    (args.output_dir / "summary.json").write_text(
        json.dumps(payload, indent=2), encoding="utf-8"
    )
    print(pd.DataFrame(fold_summaries).to_string(index=False))
    print(json.dumps(summary, indent=2))
    print(f"wrote results to {args.output_dir.resolve()}")


if __name__ == "__main__":
    main()
