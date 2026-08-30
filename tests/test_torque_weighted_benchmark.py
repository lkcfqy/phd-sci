from __future__ import annotations

import numpy as np
import pytest

from scripts.run_torque_weighted_conformal import (
    normalize_from_development,
    split_unlabeled_target,
    summarize_band,
)


def test_target_partition_is_disjoint_complete_and_deterministic() -> None:
    fit_a, evaluate_a = split_unlabeled_target(11, seed=7)
    fit_b, evaluate_b = split_unlabeled_target(11, seed=7)
    assert np.array_equal(fit_a, fit_b)
    assert np.array_equal(evaluate_a, evaluate_b)
    assert len(fit_a) == 5
    assert len(np.union1d(fit_a, evaluate_a)) == 11
    assert len(np.intersect1d(fit_a, evaluate_a)) == 0


def test_summary_keeps_vacuous_bands_visible() -> None:
    summary = summarize_band(
        np.array([1.0, 2.0, 3.0]),
        np.array([1.5, np.inf, np.inf]),
    )
    assert summary["finite_bands"] == 1
    assert summary["vacuous_band_rate"] == pytest.approx(2 / 3)
    assert summary["curvewise_coverage_including_vacuous"] == pytest.approx(1.0)
    assert summary["finite_band_curvewise_coverage"] == pytest.approx(1.0)


def test_development_normalization_uses_only_development_range() -> None:
    development = np.array([[0.0, 10.0], [2.0, 14.0]])
    normalized, shifted = normalize_from_development(
        development,
        development,
        np.array([[3.0, 8.0]]),
    )
    assert np.array_equal(normalized, np.array([[0.0, 0.0], [1.0, 1.0]]))
    assert np.array_equal(shifted, np.array([[1.5, -0.5]]))
