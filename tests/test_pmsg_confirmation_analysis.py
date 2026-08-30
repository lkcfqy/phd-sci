from __future__ import annotations

import pandas as pd

from scripts.run_pmsg_confirmation_analysis import build_record_table


def test_record_table_uses_three_pre_and_two_fault_windows() -> None:
    rows = []
    for segment, windows in (("pre_fault", 3), ("fault_active", 2), ("recovery", 6)):
        for window in range(windows):
            rows.append(
                {
                    "record_id": "fault_1",
                    "speed_rpm": 1200,
                    "torque_setting_code": 52,
                    "fault_family": "turns",
                    "terminal_a": "D01",
                    "terminal_b": "D04",
                    "fault_span_percent": 12.04,
                    "segment": segment,
                    "segment_window_id": window,
                    "score": float(window),
                    "raw_alarm": segment == "fault_active" and window == 1,
                    "actionable_alarm": segment == "fault_active" and window == 1,
                    "supported": True,
                    "method": "spline_residual",
                }
            )
    records = build_record_table(pd.DataFrame(rows), expected_records=1)
    assert len(records) == 1
    assert records.loc[0, "pre_windows"] == 3
    assert records.loc[0, "fault_windows"] == 2
    assert not bool(records.loc[0, "pre_session_false_alarm"])
    assert bool(records.loc[0, "fault_record_detection"])
    assert records.loc[0, "command_to_alarm_s"] == 0.4
