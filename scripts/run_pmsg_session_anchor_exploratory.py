"""Run the frozen post-reveal session-anchor repair on the PMSG feature table."""

from __future__ import annotations

import argparse
import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.metrics import average_precision_score, roc_auc_score

from pmsm_sci.faults.conformal import conformal_p_values, conformal_threshold
from pmsm_sci.faults.paper3 import PAPER3_OUTCOME_FEATURES
from pmsm_sci.faults.pmsg_session import pmsg_session_residual_table
from pmsm_sci.faults.session_anchor import SessionAnchoredDetector
from pmsm_sci.faults.statistics import wilson_interval

ALPHA = 0.05


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
        default=Path("docs/paper3_post_reveal_session_anchor_protocol.md"),
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("results/paper3_pmsg_session_anchor"),
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
    residual_columns = [f"residual__{column}" for column in PAPER3_OUTCOME_FEATURES]
    fit = residuals[residuals["evaluation_role"].eq("fit")]
    calibration = residuals[residuals["evaluation_role"].eq("calibration")]
    detector = SessionAnchoredDetector().fit(fit[residual_columns])
    residuals["score"] = detector.score(residuals[residual_columns])
    calibration_scores = residuals.loc[
        residuals["evaluation_role"].eq("calibration"), "score"
    ]
    threshold = conformal_threshold(calibration_scores, ALPHA)
    residuals["p_value"] = conformal_p_values(calibration_scores, residuals["score"])
    residuals["alarm"] = residuals["p_value"].le(ALPHA)
    pre = residuals[residuals["evaluation_role"].eq("pre_fault_test")]
    fault = residuals[residuals["evaluation_role"].eq("fault_test")]
    standalone = residuals[
        residuals["evaluation_role"].eq("standalone_health_test")
    ]
    record_metadata = [
        "record_id",
        "fault_family",
        "speed_rpm",
        "torque_setting_code",
        "terminal_a",
        "terminal_b",
        "fault_span_percent",
    ]
    records = fault[record_metadata].drop_duplicates().reset_index(drop=True)
    pre_summary = pre.groupby("record_id").agg(
        pre_max_score=("score", "max"), pre_session_false_alarm=("alarm", "any")
    )
    fault_summary = fault.groupby("record_id").agg(
        fault_max_score=("score", "max"), fault_record_detection=("alarm", "any")
    )
    records = records.merge(pre_summary, on="record_id", validate="one_to_one")
    records = records.merge(fault_summary, on="record_id", validate="one_to_one")
    first_alarm = (
        fault.loc[fault["alarm"]]
        .groupby("record_id")["segment_window_id"]
        .min()
    )
    records["first_alarm_window"] = records["record_id"].map(first_alarm)
    records["command_to_alarm_s"] = records["first_alarm_window"].map(
        {0.0: 0.2, 1.0: 0.4}
    )
    false_alarms = int(records["pre_session_false_alarm"].sum())
    detected = int(records["fault_record_detection"].sum())
    far_ci = wilson_interval(false_alarms, len(records))
    detection_ci = wilson_interval(detected, len(records))
    labels = np.concatenate([np.zeros(len(records)), np.ones(len(records))])
    scores = np.concatenate(
        [records["pre_max_score"].to_numpy(), records["fault_max_score"].to_numpy()]
    )
    summary = {
        "analysis_status": "post-reveal exploratory repair",
        "method": "session_anchor_ledoit_wolf",
        "threshold": threshold,
        "fit_residuals": len(fit),
        "calibration_residuals": len(calibration),
        "standalone_health_windows": len(standalone),
        "standalone_health_window_alarms": int(standalone["alarm"].sum()),
        "standalone_health_window_far": float(standalone["alarm"].mean()),
        "pre_fault_records": len(records),
        "pre_fault_false_alarms": false_alarms,
        "pre_fault_session_far": false_alarms / len(records),
        "pre_fault_session_far_wilson_lower": far_ci[0],
        "pre_fault_session_far_wilson_upper": far_ci[1],
        "fault_records": len(records),
        "fault_records_detected": detected,
        "fault_record_detection": detected / len(records),
        "fault_record_detection_wilson_lower": detection_ci[0],
        "fault_record_detection_wilson_upper": detection_ci[1],
        "detected_first_window": int(records["command_to_alarm_s"].eq(0.2).sum()),
        "detected_second_window_only": int(records["command_to_alarm_s"].eq(0.4).sum()),
        "censored_beyond_0p4s": int(records["command_to_alarm_s"].isna().sum()),
        "record_score_auroc": float(roc_auc_score(labels, scores)),
        "record_score_auprc": float(average_precision_score(labels, scores)),
        "original_gates_for_context": {
            "far_point_le_0p05": false_alarms / len(records) <= 0.05,
            "far_wilson_upper_le_0p10": far_ci[1] <= 0.10,
            "detection_point_ge_0p75": detected / len(records) >= 0.75,
            "detection_wilson_lower_ge_0p65": detection_ci[0] >= 0.65,
        },
    }
    args.output_dir.mkdir(parents=True, exist_ok=True)
    residuals.to_csv(args.output_dir / "per_window_results.csv", index=False)
    records.to_csv(args.output_dir / "per_record_results.csv", index=False)
    result = {
        "created_utc": datetime.now(UTC).isoformat(),
        "protocol": str(args.protocol.resolve()),
        "protocol_sha256": sha256(args.protocol),
        "input_features": str(args.features.resolve()),
        "input_features_sha256": sha256(args.features),
        "summary": summary,
    }
    (args.output_dir / "summary.json").write_text(
        json.dumps(result, indent=2), encoding="utf-8"
    )
    print(json.dumps(summary, indent=2))
    print(f"wrote results to {args.output_dir.resolve()}")


if __name__ == "__main__":
    main()
