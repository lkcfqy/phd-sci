"""Healthy-only operating-conditioned residual anomaly detection.

The detector separates expected current-feature drift with exogenous operating
context from residual feature geometry.  Every residual used to estimate the
healthy covariance is generated out of fold with whole records kept together.
Fault labels are neither accepted nor used by this module.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

import numpy as np
from numpy.typing import ArrayLike, NDArray
from sklearn.base import RegressorMixin
from sklearn.covariance import LedoitWolf
from sklearn.linear_model import Ridge
from sklearn.model_selection import GroupKFold
from sklearn.neighbors import NearestNeighbors
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import PolynomialFeatures, SplineTransformer, StandardScaler

MeanModelKind = Literal["constant", "linear", "quadratic", "spline"]


def _matrix(values: ArrayLike, name: str) -> NDArray[np.float64]:
    result = np.asarray(values, dtype=np.float64)
    if result.ndim != 2 or result.shape[0] == 0 or result.shape[1] == 0:
        raise ValueError(f"{name} must be a non-empty two-dimensional array")
    if not np.isfinite(result).all():
        raise ValueError(f"{name} must contain only finite values")
    return result


def _robust_scale(values: NDArray[np.float64]) -> NDArray[np.float64]:
    center = np.median(values, axis=0)
    mad = 1.4826 * np.median(np.abs(values - center), axis=0)
    standard = np.std(values, axis=0)
    magnitude = np.maximum(np.max(np.abs(values), axis=0), 1.0)
    floor = np.sqrt(np.finfo(np.float64).eps) * magnitude
    scale = np.where(mad > floor, mad, standard)
    return np.where(scale > floor, scale, 1.0)


class _MeanRegressor:
    """Small multi-output regressor that safely drops constant context axes."""

    def __init__(
        self,
        kind: MeanModelKind,
        *,
        ridge_alpha: float,
        spline_knots: int,
        spline_degree: int,
    ) -> None:
        self.kind = kind
        self.ridge_alpha = ridge_alpha
        self.spline_knots = spline_knots
        self.spline_degree = spline_degree

    def fit(self, context: ArrayLike, outcomes: ArrayLike) -> _MeanRegressor:
        x = _matrix(context, "context")
        y = _matrix(outcomes, "outcomes")
        if x.shape[0] != y.shape[0]:
            raise ValueError("context and outcomes must have equal row counts")
        self.output_center_ = np.median(y, axis=0)
        context_range = np.ptp(x, axis=0)
        tolerance = np.sqrt(np.finfo(np.float64).eps) * np.maximum(
            np.max(np.abs(x), axis=0), 1.0
        )
        self.varying_columns_ = np.flatnonzero(context_range > tolerance)
        self.estimator_: RegressorMixin | None = None
        if self.kind == "constant" or self.varying_columns_.size == 0:
            return self

        if self.kind == "linear":
            estimator = make_pipeline(
                StandardScaler(),
                Ridge(alpha=self.ridge_alpha),
            )
        elif self.kind == "quadratic":
            estimator = make_pipeline(
                StandardScaler(),
                PolynomialFeatures(degree=2, include_bias=False),
                Ridge(alpha=self.ridge_alpha),
            )
        elif self.kind == "spline":
            estimator = make_pipeline(
                StandardScaler(),
                SplineTransformer(
                    n_knots=self.spline_knots,
                    degree=self.spline_degree,
                    knots="uniform",
                    extrapolation="linear",
                    include_bias=False,
                ),
                Ridge(alpha=self.ridge_alpha),
            )
        else:
            raise ValueError(f"Unknown mean model: {self.kind}")
        estimator.fit(x[:, self.varying_columns_], y)
        self.estimator_ = estimator
        return self

    def predict(self, context: ArrayLike) -> NDArray[np.float64]:
        x = _matrix(context, "context")
        if not hasattr(self, "output_center_"):
            raise RuntimeError("Mean regressor has not been fitted")
        if self.estimator_ is None:
            return np.broadcast_to(self.output_center_, (x.shape[0], len(self.output_center_))).copy()
        prediction = np.asarray(
            self.estimator_.predict(x[:, self.varying_columns_]), dtype=np.float64
        )
        if prediction.ndim == 1:
            prediction = prediction[:, None]
        return prediction


@dataclass(frozen=True)
class ContextSupportResult:
    """Nearest-reference distances and the frozen supported/abstain decision."""

    distance: NDArray[np.float64]
    supported: NDArray[np.bool_]


class ContextSupportModel:
    """Healthy-context support rule calibrated without fault observations.

    Context is robustly normalized using fit rows.  The support radius is the
    largest nearest-fit distance among disjoint healthy calibration rows.  It
    is an operational abstention rule, not a conformal coverage guarantee.
    """

    def __init__(
        self,
        *,
        radius_multiplier: float = 1.0,
        require_axis_bounds: bool = True,
    ) -> None:
        if radius_multiplier <= 0:
            raise ValueError("radius_multiplier must be positive")
        self.radius_multiplier = float(radius_multiplier)
        self.require_axis_bounds = bool(require_axis_bounds)

    def fit(
        self,
        fit_context: ArrayLike,
        calibration_context: ArrayLike,
    ) -> ContextSupportModel:
        fit = _matrix(fit_context, "fit_context")
        calibration = _matrix(calibration_context, "calibration_context")
        if fit.shape[1] != calibration.shape[1]:
            raise ValueError("fit and calibration context dimensions differ")
        self.center_ = np.median(fit, axis=0)
        self.scale_ = _robust_scale(fit)
        self.minimum_ = np.min(fit, axis=0)
        self.maximum_ = np.max(fit, axis=0)
        normalized_fit = (fit - self.center_) / self.scale_
        self.neighbors_ = NearestNeighbors(n_neighbors=1, metric="euclidean")
        self.neighbors_.fit(normalized_fit)
        calibration_distance = self._distance(calibration)
        self.calibration_distances_ = calibration_distance
        self.radius_ = float(
            max(np.max(calibration_distance) * self.radius_multiplier, 1e-12)
        )
        return self

    def _distance(self, context: ArrayLike) -> NDArray[np.float64]:
        x = _matrix(context, "context")
        if not hasattr(self, "neighbors_"):
            raise RuntimeError("Context support model has not been fitted")
        if x.shape[1] != len(self.center_):
            raise ValueError("Unexpected context dimension")
        normalized = (x - self.center_) / self.scale_
        distances, _ = self.neighbors_.kneighbors(normalized)
        return np.asarray(distances[:, 0], dtype=np.float64)

    def evaluate(self, context: ArrayLike) -> ContextSupportResult:
        x = _matrix(context, "context")
        distance = self._distance(x)
        tolerance = 32 * np.finfo(np.float64).eps * max(self.radius_, 1.0)
        supported = distance <= self.radius_ + tolerance
        if self.require_axis_bounds:
            axis_tolerance = 32 * np.finfo(np.float64).eps * np.maximum(
                np.maximum(np.abs(self.minimum_), np.abs(self.maximum_)), 1.0
            )
            supported &= np.all(
                (x >= self.minimum_ - axis_tolerance)
                & (x <= self.maximum_ + axis_tolerance),
                axis=1,
            )
        return ContextSupportResult(
            distance=distance,
            supported=supported,
        )


class ConditionalResidualDetector:
    """Record-cross-fitted, healthy-only residual Mahalanobis detector."""

    def __init__(
        self,
        *,
        mean_model: MeanModelKind = "spline",
        local_scale: bool = True,
        crossfit_splits: int = 5,
        ridge_alpha: float = 1.0,
        spline_knots: int = 4,
        spline_degree: int = 2,
        scale_clip: tuple[float, float] = (0.25, 4.0),
    ) -> None:
        if mean_model not in {"constant", "linear", "quadratic", "spline"}:
            raise ValueError(f"Unknown mean model: {mean_model}")
        if crossfit_splits < 2:
            raise ValueError("crossfit_splits must be at least two")
        if ridge_alpha <= 0:
            raise ValueError("ridge_alpha must be positive")
        if spline_knots < 3:
            raise ValueError("spline_knots must be at least three")
        if spline_degree < 1:
            raise ValueError("spline_degree must be positive")
        if not 0 < scale_clip[0] <= 1 <= scale_clip[1]:
            raise ValueError("scale_clip must bracket one with positive values")
        self.mean_model = mean_model
        self.local_scale = bool(local_scale)
        self.crossfit_splits = int(crossfit_splits)
        self.ridge_alpha = float(ridge_alpha)
        self.spline_knots = int(spline_knots)
        self.spline_degree = int(spline_degree)
        self.scale_clip = (float(scale_clip[0]), float(scale_clip[1]))

    def _new_regressor(self, kind: MeanModelKind | None = None) -> _MeanRegressor:
        return _MeanRegressor(
            self.mean_model if kind is None else kind,
            ridge_alpha=self.ridge_alpha,
            spline_knots=self.spline_knots,
            spline_degree=self.spline_degree,
        )

    def fit(
        self,
        context: ArrayLike,
        outcomes: ArrayLike,
        *,
        groups: ArrayLike,
    ) -> ConditionalResidualDetector:
        """Fit exclusively on healthy rows, cross-fitting by complete record."""

        x = _matrix(context, "context")
        y = _matrix(outcomes, "outcomes")
        group_values = np.asarray(groups).reshape(-1)
        if x.shape[0] != y.shape[0] or x.shape[0] != group_values.size:
            raise ValueError("context, outcomes, and groups must have equal row counts")
        if pd_is_missing(group_values):
            raise ValueError("groups must not contain missing values")
        unique_groups = np.unique(group_values)
        if unique_groups.size < 2:
            raise ValueError("At least two complete groups are required for cross-fitting")

        splits = min(self.crossfit_splits, unique_groups.size)
        out_of_fold_prediction = np.full_like(y, np.nan, dtype=np.float64)
        splitter = GroupKFold(n_splits=splits)
        for train_index, validation_index in splitter.split(x, y, group_values):
            regressor = self._new_regressor().fit(x[train_index], y[train_index])
            out_of_fold_prediction[validation_index] = regressor.predict(x[validation_index])
        if not np.isfinite(out_of_fold_prediction).all():
            raise AssertionError("Cross-fitting did not produce one finite prediction per row")

        residual = y - out_of_fold_prediction
        self.residual_center_ = np.median(residual, axis=0)
        centered_residual = residual - self.residual_center_
        self.global_residual_scale_ = _robust_scale(centered_residual)
        self.scale_model_: _MeanRegressor | None = None
        if self.local_scale:
            stabilized_absolute = np.abs(centered_residual) + 0.05 * self.global_residual_scale_
            log_absolute = np.log(stabilized_absolute)
            self.scale_model_ = self._new_regressor("spline").fit(x, log_absolute)

        training_scale = self._residual_scale(x)
        standardized_residual = centered_residual / training_scale
        self.covariance_ = LedoitWolf(assume_centered=False, store_precision=True)
        self.covariance_.fit(standardized_residual)
        self.mean_regressor_ = self._new_regressor().fit(x, y)
        self.context_features_ = x.shape[1]
        self.outcome_features_ = y.shape[1]
        self.crossfit_groups_ = int(unique_groups.size)
        self.crossfit_residuals_ = residual
        self.training_scores_ = self._mahalanobis(standardized_residual)
        if not np.isfinite(self.training_scores_).all():
            raise FloatingPointError("Detector produced non-finite training scores")
        return self

    def _residual_scale(self, context: ArrayLike) -> NDArray[np.float64]:
        x = _matrix(context, "context")
        if not hasattr(self, "global_residual_scale_"):
            raise RuntimeError("Detector has not been fitted")
        global_scale = np.broadcast_to(
            self.global_residual_scale_, (x.shape[0], len(self.global_residual_scale_))
        )
        if self.scale_model_ is None:
            return global_scale.copy()
        predicted = np.exp(self.scale_model_.predict(x))
        lower = self.scale_clip[0] * global_scale
        upper = self.scale_clip[1] * global_scale
        return np.clip(predicted, lower, upper)

    def _mahalanobis(self, standardized_residual: NDArray[np.float64]) -> NDArray[np.float64]:
        centered = standardized_residual - self.covariance_.location_
        scores = np.einsum(
            "ij,jk,ik->i", centered, self.covariance_.precision_, centered, optimize=True
        )
        return np.maximum(np.asarray(scores, dtype=np.float64), 0.0)

    def score(self, context: ArrayLike, outcomes: ArrayLike) -> NDArray[np.float64]:
        """Return squared residual Mahalanobis scores; larger is more anomalous."""

        x = _matrix(context, "context")
        y = _matrix(outcomes, "outcomes")
        if not hasattr(self, "mean_regressor_"):
            raise RuntimeError("Detector has not been fitted")
        if x.shape[0] != y.shape[0]:
            raise ValueError("context and outcomes must have equal row counts")
        if x.shape[1] != self.context_features_ or y.shape[1] != self.outcome_features_:
            raise ValueError("Unexpected context or outcome dimension")
        residual = y - self.mean_regressor_.predict(x) - self.residual_center_
        standardized = residual / self._residual_scale(x)
        scores = self._mahalanobis(standardized)
        if not np.isfinite(scores).all():
            raise FloatingPointError("Detector produced non-finite scores")
        return scores


def pd_is_missing(values: NDArray[np.object_]) -> bool:
    """Avoid a pandas dependency while rejecting None and floating NaNs."""

    for value in values:
        if value is None:
            return True
        try:
            if bool(np.isnan(value)):
                return True
        except (TypeError, ValueError):
            continue
    return False
