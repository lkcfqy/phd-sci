from __future__ import annotations

import numpy as np
import pytest

from pmsm_sci.faults.conditional import (
    ConditionalResidualDetector,
    ContextSupportModel,
)


def _healthy_drift(seed: int = 17) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    rng = np.random.default_rng(seed)
    rows_per_group = 60
    groups = np.repeat(np.arange(6), rows_per_group)
    speed = np.tile(np.linspace(-1.0, 1.0, rows_per_group), 6)
    load = np.repeat(np.linspace(-1.0, 1.0, 6), rows_per_group)
    context = np.column_stack([speed, load])
    noise = rng.normal(0.0, 0.06, size=(len(context), 3))
    outcomes = np.column_stack(
        [
            2.0 * speed + 0.5 * load,
            speed**2 - 0.3 * load,
            np.sin(np.pi * speed) + 0.4 * load,
        ]
    ) + noise
    return context, outcomes, groups


@pytest.mark.parametrize("mean_model", ["constant", "linear", "quadratic", "spline"])
def test_conditional_detector_scores_are_finite(mean_model: str) -> None:
    context, outcomes, groups = _healthy_drift()
    detector = ConditionalResidualDetector(
        mean_model=mean_model,  # type: ignore[arg-type]
        local_scale=True,
        crossfit_splits=3,
    ).fit(context, outcomes, groups=groups)
    scores = detector.score(context[:20], outcomes[:20])
    assert scores.shape == (20,)
    assert np.isfinite(scores).all()
    assert (scores >= 0).all()
    assert detector.crossfit_groups_ == 6


def test_conditioning_separates_operating_drift_from_fault_offset() -> None:
    context, outcomes, groups = _healthy_drift()
    detector = ConditionalResidualDetector(
        mean_model="spline",
        local_scale=False,
        crossfit_splits=3,
    ).fit(context, outcomes, groups=groups)
    healthy_scores = detector.score(context, outcomes)
    fault = outcomes.copy()
    fault[:, 0] += 0.8
    fault[:, 2] -= 0.6
    fault_scores = detector.score(context, fault)
    assert np.median(fault_scores) > 5 * np.median(healthy_scores)


def test_cross_fitting_requires_multiple_complete_groups() -> None:
    context, outcomes, _ = _healthy_drift()
    with pytest.raises(ValueError, match="At least two complete groups"):
        ConditionalResidualDetector().fit(
            context,
            outcomes,
            groups=np.repeat("only_record", len(context)),
        )


def test_context_support_uses_only_fit_and_calibration_context() -> None:
    fit = np.asarray([[0.0, -0.2], [0.5, 0.0], [1.0, 0.2]])
    calibration = np.asarray([[0.25, 0.1], [0.75, -0.1]])
    model = ContextSupportModel().fit(fit, calibration)
    result = model.evaluate([[0.5, 0.05], [0.5, 10.0]])
    assert result.supported.tolist() == [True, False]
    assert result.distance[1] > result.distance[0]
    assert model.radius_ == pytest.approx(np.max(model.calibration_distances_))


def test_context_support_abstains_outside_fit_axis_bounds_even_inside_radius() -> None:
    fit = np.asarray([[0.0, 0.0], [1.0, 0.0], [0.0, 10.0]])
    calibration = np.asarray([[1.0, 10.0]])
    bounded = ContextSupportModel(radius_multiplier=2.0).fit(fit, calibration)
    result = bounded.evaluate([[1.1, 0.0]])
    assert result.distance[0] < bounded.radius_
    assert not result.supported[0]


def test_invalid_dimensions_and_missing_groups_are_rejected() -> None:
    context, outcomes, groups = _healthy_drift()
    detector = ConditionalResidualDetector().fit(context, outcomes, groups=groups)
    with pytest.raises(ValueError, match="Unexpected"):
        detector.score(context[:, :1], outcomes)
    missing = groups.astype(object)
    missing[0] = None
    with pytest.raises(ValueError, match="missing"):
        ConditionalResidualDetector().fit(context, outcomes, groups=missing)
