"""Shared frozen model fitting used by Paper 3 development and confirmation."""

from __future__ import annotations

import numpy as np
from numpy.typing import ArrayLike, NDArray

from pmsm_sci.faults.conditional import ConditionalResidualDetector
from pmsm_sci.faults.oneclass import (
    build_oneclass_estimator,
    independent_training_columns,
    oneclass_anomaly_scores,
)
from pmsm_sci.faults.paper3 import Paper3MethodSpec


def _matrix(values: ArrayLike, name: str) -> NDArray[np.float64]:
    result = np.asarray(values, dtype=np.float64)
    if result.ndim != 2 or result.shape[0] == 0 or result.shape[1] == 0:
        raise ValueError(f"{name} must be a non-empty two-dimensional array")
    if not np.isfinite(result).all():
        raise ValueError(f"{name} must contain only finite values")
    return result


def robust_parameters(
    values: ArrayLike,
) -> tuple[NDArray[np.float64], NDArray[np.float64]]:
    data = _matrix(values, "values")
    center = np.median(data, axis=0)
    mad = 1.4826 * np.median(np.abs(data - center), axis=0)
    standard = np.std(data, axis=0)
    floor = np.sqrt(np.finfo(np.float64).eps) * np.maximum(
        np.max(np.abs(data), axis=0), 1.0
    )
    scale = np.where(mad > floor, mad, standard)
    return center, np.where(scale > floor, scale, 1.0)


class ClassicalHealthyDetector:
    """Fixed unconditioned one-class comparator with healthy-fit scaling."""

    def __init__(self, spec: Paper3MethodSpec, *, seed: int) -> None:
        if spec.family not in {"isolation_forest", "min_cov_det"}:
            raise ValueError("Classical detector received a conditional method")
        self.spec = spec
        self.seed = seed

    def fit(self, outcomes: ArrayLike) -> ClassicalHealthyDetector:
        values = _matrix(outcomes, "outcomes")
        self.center_, self.scale_ = robust_parameters(values)
        transformed = (values - self.center_) / self.scale_
        if self.spec.family == "min_cov_det":
            self.columns_ = independent_training_columns(transformed)
        else:
            self.columns_ = np.arange(transformed.shape[1], dtype=np.int64)
        self.estimator_ = build_oneclass_estimator(
            self.spec.family,
            seed=self.seed,
            isolation_trees=300,
        )
        self.estimator_.fit(transformed[:, self.columns_])
        return self

    def score(self, outcomes: ArrayLike) -> NDArray[np.float64]:
        values = _matrix(outcomes, "outcomes")
        transformed = (values - self.center_) / self.scale_
        return oneclass_anomaly_scores(
            self.estimator_, self.spec.family, transformed[:, self.columns_]
        )


def paper3_detector_scores(
    spec: Paper3MethodSpec,
    *,
    fit_context: ArrayLike,
    fit_outcomes: ArrayLike,
    fit_groups: ArrayLike,
    score_context: ArrayLike,
    score_outcomes: ArrayLike,
    seed: int,
) -> NDArray[np.float64]:
    """Fit one frozen healthy-only method and score an aligned target matrix."""

    fit_x = _matrix(fit_context, "fit_context")
    fit_y = _matrix(fit_outcomes, "fit_outcomes")
    score_x = _matrix(score_context, "score_context")
    score_y = _matrix(score_outcomes, "score_outcomes")
    if fit_x.shape[0] != fit_y.shape[0] or score_x.shape[0] != score_y.shape[0]:
        raise ValueError("Context and outcome row counts differ")
    if spec.family == "conditional":
        detector = ConditionalResidualDetector(
            mean_model=spec.mean_model,  # type: ignore[arg-type]
            local_scale=spec.local_scale,
            crossfit_splits=4,
            ridge_alpha=1.0,
            spline_knots=4,
            spline_degree=2,
            scale_clip=(0.25, 4.0),
        ).fit(fit_x, fit_y, groups=fit_groups)
        return detector.score(score_x, score_y)
    detector = ClassicalHealthyDetector(spec, seed=seed).fit(fit_y)
    return detector.score(score_y)
