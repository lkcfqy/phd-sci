from __future__ import annotations

import numpy as np
import pytest

from pmsm_sci.torque.covariate_shift import (
    QuadraticLogisticDensityRatio,
    effective_sample_size,
    weighted_conformal_quantiles,
)


def test_effective_sample_size_matches_equal_weight_count() -> None:
    assert effective_sample_size(np.ones(7)) == pytest.approx(7.0)
    assert effective_sample_size(np.array([1.0, 0.0, 0.0])) == pytest.approx(1.0)


def test_weighted_quantile_includes_test_mass_at_infinity() -> None:
    scores = np.array([1.0, 2.0, 3.0])
    weights = np.ones(3)
    quantiles = weighted_conformal_quantiles(
        scores,
        weights,
        np.array([1.0, 10.0]),
        alpha=0.25,
    )
    assert quantiles[0] == pytest.approx(3.0)
    assert np.isinf(quantiles[1])


def test_weighted_quantile_rejects_invalid_weights() -> None:
    with pytest.raises(ValueError, match="weights"):
        weighted_conformal_quantiles(
            np.array([1.0, 2.0]),
            np.array([1.0, -1.0]),
            np.array([1.0]),
            alpha=0.1,
        )


def test_quadratic_density_ratio_separates_variance_shift() -> None:
    rng = np.random.default_rng(11)
    source = rng.uniform(-1.0, 1.0, size=(300, 2))
    target = rng.normal(0.0, 0.08, size=(300, 2))
    estimator = QuadraticLogisticDensityRatio(
        seed=11,
        cs=(0.01, 0.1),
    ).fit(source, target)
    centre_weight = estimator.ratio(np.zeros((1, 2)))[0]
    edge_weight = estimator.ratio(np.array([[0.9, 0.9]]))[0]
    assert centre_weight > edge_weight
    assert estimator.selected_c in {0.01, 0.1}
