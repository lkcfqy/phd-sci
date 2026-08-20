import numpy as np
import pandas as pd
import pytest

from scripts.run_external_seed_sensitivity import (
    EXPECTED_METHODS,
    PRIMARY_SEED,
    SEEDS,
    reconcile_primary_blocks,
    sensitivity_specs,
    summarize_seed_ranges,
)


def _summary_frame() -> pd.DataFrame:
    rows = []
    for method_index, method in enumerate(EXPECTED_METHODS):
        for seed_index, seed in enumerate(SEEDS):
            rows.append(
                {
                    "method": method,
                    "seed": seed,
                    "fault_record_macro_detection_rate": 0.5
                    + method_index / 20
                    + seed_index / 100,
                    "healthy_block_false_alarm_rate": seed_index / 32,
                    "false_alarms": seed_index,
                    "h1_empirical_pass": seed_index == 0,
                    "threshold": 10 + seed_index,
                    "block_auroc": 0.8 + seed_index / 100,
                }
            )
    return pd.DataFrame(rows)


def test_specs_are_exactly_four_predeclared_stochastic_methods() -> None:
    specs = sensitivity_specs()
    assert tuple(spec.name for spec in specs) == EXPECTED_METHODS
    assert all(spec.stochastic for spec in specs)


def test_seed_summary_reports_full_range_and_primary_value() -> None:
    summary = summarize_seed_ranges(_summary_frame())
    row = summary[summary["method"].eq(EXPECTED_METHODS[0])].iloc[0]
    assert row["seeds"] == 5
    assert row["primary_detection_rate"] == pytest.approx(0.5)
    assert row["detection_min"] == pytest.approx(0.5)
    assert row["detection_max"] == pytest.approx(0.54)
    assert row["detection_range"] == pytest.approx(0.04)
    assert row["false_alarms_min"] == 0
    assert row["false_alarms_max"] == 4


def test_seed_summary_rejects_incomplete_seed_grid() -> None:
    with pytest.raises(ValueError, match="four methods by five seeds"):
        summarize_seed_ranges(_summary_frame().iloc[:-1])


def _blocks(scores: list[float], alarms: list[bool]) -> pd.DataFrame:
    return pd.DataFrame(
        {
            "record_id": ["record_a", "record_a"],
            "load_nm": [5, 5],
            "block_id": [0, 1],
            "score": scores,
            "p_value": [0.5, 0.04],
            "alarm": alarms,
        }
    )


def test_primary_reconciliation_accepts_identical_outputs() -> None:
    result = reconcile_primary_blocks(
        _blocks([1.0, 2.0], [False, True]),
        _blocks([1.0, 2.0], [False, True]),
        method="target_min_cov_det",
    )
    assert result["primary_seed"] == PRIMARY_SEED
    assert result["alarm_mismatches"] == 0
    assert result["passed"] is True


def test_primary_reconciliation_rejects_alarm_change() -> None:
    with pytest.raises(AssertionError, match="does not reproduce"):
        reconcile_primary_blocks(
            _blocks([1.0, 2.0], [False, False]),
            _blocks([1.0, 2.0], [False, True]),
            method="target_min_cov_det",
        )


def test_seed_tuple_is_frozen_in_required_order() -> None:
    assert SEEDS == (20_260_820, 1_201, 2_402, 3_603, 4_804)
    assert len(np.unique(SEEDS)) == 5
