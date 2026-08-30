from __future__ import annotations

import numpy as np
import pytest

from scripts.make_paper2_torque_additional_figures import (
    choose_median_error,
    select_representative_indices,
)


def test_choose_median_error_uses_first_deterministic_tie() -> None:
    selected = choose_median_error(
        np.array([False, True, True, True]),
        np.array([9.0, 1.0, 3.0, 5.0]),
    )
    assert selected == 2


def test_selection_requires_all_four_predeclared_roles() -> None:
    scale = np.arange(10, dtype=float)
    uniform_error = np.array([0.1, 0.1, 0.1, 0.1, 0.1, 0.1, 0.1, 1.5, 2.5, 2.5])
    uniform_local = np.array([1.0] * 8 + [3.0, 2.0])
    gauss_error = np.full(10, 0.5)
    gauss_local = np.full(10, 1.0)
    selected = select_representative_indices(
        uniform_error=uniform_error,
        uniform_scale=scale,
        uniform_global_width=1.0,
        uniform_scaled_width=uniform_local,
        gauss_error=gauss_error,
        gauss_scale=scale,
        gauss_global_width=1.0,
        gauss_scaled_width=gauss_local,
    )
    assert [role for _, role, _ in selected] == [
        "dense_both_covered",
        "sparse_scaled_rescue",
        "sparse_both_missed",
        "gaussian_middle_both_covered",
    ]


def test_choose_median_error_rejects_empty_role() -> None:
    with pytest.raises(ValueError, match="no candidate"):
        choose_median_error(np.zeros(3, dtype=bool), np.arange(3, dtype=float))
