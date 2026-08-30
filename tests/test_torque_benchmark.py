from __future__ import annotations

import numpy as np

from scripts.run_torque_conformal_benchmark import (
    evaluate_band,
    normalize_with_development,
    prediction_metrics,
)


def test_normalization_uses_development_bounds() -> None:
    development = np.array([[1.0, 10.0], [3.0, 20.0]])
    normalized, shifted = normalize_with_development(
        development,
        development,
        np.array([[5.0, 15.0]]),
    )
    np.testing.assert_allclose(normalized, [[0.0, 0.0], [1.0, 1.0]])
    np.testing.assert_allclose(shifted, [[2.0, 0.5]])


def test_prediction_and_band_metrics_use_design_grain() -> None:
    truth = np.array([[1.0, 2.0], [2.0, 4.0]])
    prediction = np.array([[1.1, 1.8], [2.1, 3.7]])
    metrics = prediction_metrics(truth, prediction)
    assert np.isclose(metrics["waveform_mae"], 0.175)
    band, covered = evaluate_band(
        truth=truth,
        prediction=prediction,
        half_width=np.array([0.2, 0.2]),
        support_p=np.array([0.5, 0.01]),
        support_alpha=0.05,
    )
    np.testing.assert_array_equal(covered, [True, False])
    assert band["designs"] == 2
    assert band["curvewise_coverage"] == 0.5
    assert band["support_rejected_designs"] == 1
