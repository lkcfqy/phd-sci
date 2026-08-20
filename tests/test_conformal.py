import math

import numpy as np
import pytest

from pmsm_sci.faults.conformal import (
    aggregate_window_scores,
    conformal_p_values,
    conformal_threshold,
)


def test_threshold_uses_conservative_order_statistic() -> None:
    scores = np.arange(1.0, 20.0)
    assert conformal_threshold(scores, alpha=0.10) == 18.0


def test_threshold_is_infinite_when_calibration_budget_is_too_small() -> None:
    assert math.isinf(conformal_threshold([1.0, 2.0, 3.0], alpha=0.05))


def test_p_values_are_upper_tail_and_smoothed() -> None:
    p_values = conformal_p_values([1.0, 2.0, 3.0], [0.5, 2.5, 4.0])
    assert p_values == pytest.approx([1.0, 0.5, 0.25])


def test_block_aggregation_prevents_treating_windows_as_units() -> None:
    ids, values = aggregate_window_scores(
        [0.1, 0.8, 0.2, 0.3], [0, 0, 1, 1], quantile=1.0
    )
    assert ids.tolist() == [0, 1]
    assert values.tolist() == pytest.approx([0.8, 0.3])
