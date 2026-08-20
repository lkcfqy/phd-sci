import numpy as np
import pandas as pd
import pytest

from scripts.analyze_external_pmsm_results import (
    EXTERNAL_MOTOR_ID,
    PROPOSED,
    block_id_score_alarm_summary,
    paired_proposed_comparisons,
    proposed_turn_load_tables,
    stratified_record_bootstrap_draws,
)


def _fault_records(method: str, offset: float = 0.0) -> pd.DataFrame:
    rows = []
    for turns in range(1, 7):
        for load in range(0, 36, 5):
            rate = (turns + load / 5) / 16 + offset
            rows.append(
                {
                    "record_id": f"{EXTERNAL_MOTOR_ID}_flt{turns}_load{load}",
                    "load_nm": load,
                    "fault_turns": turns,
                    "fault_phase": "u" if turns % 2 else "v",
                    "blocks": 8,
                    "alarms": round(8 * rate),
                    "block_alarm_rate": rate,
                    "mean_score": turns + load,
                    "max_score": turns + load + 1,
                    "external_motor_id": EXTERNAL_MOTOR_ID,
                    "method": method,
                }
            )
    return pd.DataFrame(rows)


def _health_blocks(method: str) -> pd.DataFrame:
    rows = []
    for load in (5, 15, 25, 35):
        for block in range(8):
            rows.append(
                {
                    "record_id": f"{EXTERNAL_MOTOR_ID}_healthy_{load}",
                    "load_nm": load,
                    "block_id": block,
                    "score": float(block + load),
                    "is_healthy": True,
                    "fault_turns": 0,
                    "fault_phase": "none",
                    "role": "health_test",
                    "alarm": block == 7,
                    "method": method,
                    "external_motor_id": EXTERNAL_MOTOR_ID,
                }
            )
    return pd.DataFrame(rows)


def test_stratified_bootstrap_resamples_complete_records_and_is_deterministic() -> None:
    records = _fault_records("model")
    records["constant"] = 0.25
    first = stratified_record_bootstrap_draws(
        records, value_column="constant", iterations=200, seed=711
    )
    second = stratified_record_bootstrap_draws(
        records, value_column="constant", iterations=200, seed=711
    )
    assert np.array_equal(first, second)
    assert first == pytest.approx(np.full(200, 0.25))


def test_paired_comparison_uses_all_48_records_and_proposed_minus_baseline() -> None:
    proposed = _fault_records(PROPOSED, offset=0.1)
    baseline = _fault_records("target_ledoit", offset=0.0)
    records = pd.concat([proposed, baseline], ignore_index=True)
    blocks = pd.concat(
        [_health_blocks(PROPOSED), _health_blocks("target_ledoit")], ignore_index=True
    )
    comparison = paired_proposed_comparisons(
        blocks,
        records,
        iterations=200,
        seed=711,
    )
    row = comparison[comparison["baseline"].eq("target_ledoit")].iloc[0]
    assert row["paired_fault_records"] == 48
    assert row["fault_turn_strata"] == 6
    assert row["proposed_minus_baseline_detection"] == pytest.approx(0.1)
    assert row["paired_bootstrap_ci_lower"] == pytest.approx(0.1)
    assert row["paired_bootstrap_ci_upper"] == pytest.approx(0.1)


def test_turn_load_table_requires_and_preserves_complete_grid() -> None:
    records = _fault_records(PROPOSED)
    long, matrix, by_turn, by_load = proposed_turn_load_tables(records)
    assert len(long) == 48
    assert matrix.shape == (6, 10)
    assert len(by_turn) == 6
    assert len(by_load) == 8
    assert by_turn["records"].eq(8).all()
    assert by_load["records"].eq(6).all()


def test_turn_load_table_rejects_a_missing_record() -> None:
    with pytest.raises(ValueError, match="48 fault records"):
        proposed_turn_load_tables(_fault_records(PROPOSED).iloc[:-1])


def test_block_summary_separates_all_health_from_health_test() -> None:
    health_test = _health_blocks(PROPOSED)
    calibration = health_test.iloc[:8].copy()
    calibration["record_id"] = f"{EXTERNAL_MOTOR_ID}_healthy_calibration"
    calibration["role"] = "calibration"
    calibration["alarm"] = False
    faults = health_test.iloc[:8].copy()
    faults["record_id"] = f"{EXTERNAL_MOTOR_ID}_fault"
    faults["role"] = "fault_test"
    faults["is_healthy"] = False
    faults["fault_turns"] = 1
    summary = block_id_score_alarm_summary(
        pd.concat([health_test, calibration, faults], ignore_index=True)
    )
    block_zero = summary[summary["block_id"].eq(0)]
    counts = block_zero.set_index("population")["records"].to_dict()
    assert counts == {"fault": 1, "healthy_all": 5, "healthy_test": 4}
