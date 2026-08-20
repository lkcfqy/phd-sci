from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from scripts.run_transient_pmsm_validation import (
    equal_motor_mean,
    evenly_spaced_rows,
    fold_metrics,
    holm_adjust,
    paired_stratified_bootstrap,
)


def test_evenly_spaced_rows_is_deterministic_and_without_replacement() -> None:
    values = np.arange(40, dtype=float).reshape(20, 2)
    selected = evenly_spaced_rows(values, 7)
    assert selected.shape == (7, 2)
    assert len(np.unique(selected[:, 0])) == 7
    np.testing.assert_array_equal(selected, evenly_spaced_rows(values, 7))


def test_fold_metrics_uses_only_primary_post_windows() -> None:
    frame = pd.DataFrame(
        {
            "segment": ["pre_fault"] * 3 + ["post_fault"] * 7,
            "primary_post_window": [False] * 3 + [True] * 5 + [False] * 2,
            "score": [0.1, 0.2, 0.3, 1.0, 1.1, 1.2, 1.3, 1.4, 9.0, 9.0],
            "alarm": [False, True, False, True, True, False, False, False, True, True],
            "relative_start_seconds": [-0.8, -0.6, -0.4, 0.0, 0.2, 0.4, 0.6, 0.8, 1.0, 1.2],
        }
    )
    result = fold_metrics(frame)
    assert result["healthy_windows"] == 3
    assert result["false_alarms"] == 1
    assert result["detected_fault_windows"] == 2
    assert result["primary_fault_detection_rate"] == pytest.approx(0.4)
    assert result["first_alarm_delay_seconds"] == 0.0


def test_equal_motor_mean_does_not_weight_motor_with_more_records() -> None:
    frame = pd.DataFrame(
        {"motor_id": ["small", "small", "small", "large"], "value": [1, 1, 1, 0]}
    )
    assert equal_motor_mean(frame, "value") == pytest.approx(0.5)


def test_stratified_bootstrap_and_holm_are_directionally_consistent() -> None:
    paired = pd.DataFrame(
        {
            "motor_id": ["200W"] * 6 + ["20kW"] * 6,
            "nominal_severity": [1, 1, 2, 2, 3, 3] * 2,
            "difference": np.full(12, 0.2),
        }
    )
    point, lower, upper, p_value = paired_stratified_bootstrap(
        paired, iterations=200, seed=7
    )
    assert point == pytest.approx(0.2)
    assert lower == pytest.approx(0.2)
    assert upper == pytest.approx(0.2)
    assert p_value < 0.02
    adjusted = holm_adjust(np.array([0.01, 0.04, 0.03]))
    np.testing.assert_allclose(adjusted, [0.03, 0.06, 0.06])
