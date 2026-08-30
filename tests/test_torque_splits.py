from __future__ import annotations

import numpy as np
import pytest

from pmsm_sci.torque.splits import make_primary_split


def test_primary_split_is_reproducible_disjoint_and_complete() -> None:
    first = make_primary_split(seed=17)
    second = make_primary_split(seed=17)
    np.testing.assert_array_equal(first.fit, second.fit)
    assert len(first.fit) == 1200
    assert len(first.calibration) == 600
    assert len(first.internal_test) == 200
    combined = np.concatenate([first.fit, first.calibration, first.internal_test])
    assert len(np.unique(combined)) == 2000
    assert np.array_equal(np.sort(combined), np.arange(2000))
    assert first.internal_test[0] == 1800


def test_primary_split_rejects_invalid_sizes() -> None:
    with pytest.raises(ValueError, match="require"):
        make_primary_split(total_rows=100, development_rows=80, fit_rows=80)
