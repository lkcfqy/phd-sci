from __future__ import annotations

import numpy as np
import pytest

from pmsm_sci.torque.conformal import (
    KnnGeometryScaler,
    conformal_quantile,
    curvewise_max_error,
    support_p_values,
    wilson_interval,
)


def test_conformal_quantile_uses_finite_sample_higher_rank() -> None:
    scores = np.arange(1.0, 20.0)
    assert conformal_quantile(scores, alpha=0.05) == 19.0
    assert conformal_quantile(np.arange(1.0, 101.0), alpha=0.1) == 91.0


def test_curvewise_error_and_shape_guard() -> None:
    observed = np.array([[0.0, 1.0], [2.0, 4.0]])
    predicted = np.array([[0.2, 0.5], [3.0, 4.1]])
    np.testing.assert_allclose(curvewise_max_error(observed, predicted), [0.5, 1.0])
    with pytest.raises(ValueError, match="share shape"):
        curvewise_max_error(observed, predicted[:, :1])


def test_geometry_scaler_is_positive_and_detects_distant_point() -> None:
    generator = np.random.default_rng(9)
    fit = generator.normal(size=(50, 3))
    scaler = KnnGeometryScaler(neighbours=5).fit(fit)
    local = scaler.scale(fit[:3])
    distant = scaler.scale(np.array([[20.0, 20.0, 20.0]]))
    assert np.all(local > 0)
    assert distant[0] > np.max(local)


def test_support_p_values_and_wilson_interval() -> None:
    p_values = support_p_values(np.array([1.0, 2.0, 3.0]), np.array([0.5, 2.5, 4.0]))
    np.testing.assert_allclose(p_values, [1.0, 0.5, 0.25])
    lower, upper = wilson_interval(90, 100)
    assert 0.82 < lower < 0.84
    assert 0.94 < upper < 0.96
