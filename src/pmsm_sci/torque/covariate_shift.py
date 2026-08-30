"""Density-ratio diagnostics and weighted conformal bands under covariate shift."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from sklearn.linear_model import LogisticRegressionCV
from sklearn.model_selection import StratifiedKFold
from sklearn.pipeline import Pipeline, make_pipeline
from sklearn.preprocessing import PolynomialFeatures, StandardScaler


def effective_sample_size(weights: np.ndarray) -> float:
    """Kish effective sample size for non-negative importance weights."""

    values = np.asarray(weights, dtype=float)
    if values.ndim != 1 or len(values) == 0:
        raise ValueError("weights must be a non-empty vector")
    if not np.isfinite(values).all() or np.any(values < 0) or not np.any(values > 0):
        raise ValueError("weights must be finite, non-negative, and not all zero")
    return float(values.sum() ** 2 / np.square(values).sum())


def weighted_conformal_quantiles(
    calibration_scores: np.ndarray,
    calibration_weights: np.ndarray,
    test_weights: np.ndarray,
    alpha: float,
) -> np.ndarray:
    """Return test-specific weighted split-conformal quantiles.

    The target test point contributes its likelihood-ratio weight at ``+infinity``.
    Consequently, a quantile is infinite when the finite calibration mass cannot reach
    ``1 - alpha``.  This is the valid, deliberately visible outcome under severe weight
    degeneracy; the implementation never clips a vacuous band to the largest observed
    calibration score.
    """

    scores = np.asarray(calibration_scores, dtype=float)
    calibration = np.asarray(calibration_weights, dtype=float)
    test = np.asarray(test_weights, dtype=float)
    if scores.ndim != 1 or calibration.ndim != 1 or test.ndim != 1:
        raise ValueError("scores and weights must be one-dimensional")
    if len(scores) == 0 or len(scores) != len(calibration):
        raise ValueError("calibration scores and weights must have equal non-zero length")
    if not np.isfinite(scores).all():
        raise ValueError("calibration scores must be finite")
    if (
        not np.isfinite(calibration).all()
        or not np.isfinite(test).all()
        or np.any(calibration < 0)
        or np.any(test < 0)
        or not np.any(calibration > 0)
    ):
        raise ValueError("weights must be finite and non-negative with positive calibration mass")
    if not 0.0 < alpha < 1.0:
        raise ValueError("alpha must lie strictly between zero and one")

    order = np.argsort(scores, kind="stable")
    ordered_scores = scores[order]
    cumulative_mass = np.cumsum(calibration[order])
    required_mass = (1.0 - alpha) * (cumulative_mass[-1] + test)
    indices = np.searchsorted(cumulative_mass, required_mass, side="left")
    finite = indices < len(ordered_scores)
    quantiles = np.full(len(test), np.inf, dtype=float)
    quantiles[finite] = ordered_scores[indices[finite]]
    return quantiles


@dataclass
class QuadraticLogisticDensityRatio:
    """Estimate a target/source density ratio from domain labels only.

    Balanced class weights make the fitted log odds an estimate of
    ``log p_target(x) - log p_source(x)``.  Quadratic terms can represent the strong
    variance contraction of the released Gaussian PMSM design distribution while the
    cross-validated regularization is selected without torque labels.
    """

    seed: int = 20260821
    cs: tuple[float, ...] = (1e-4, 1e-3, 1e-2, 1e-1, 1.0)
    log_ratio_clip: float = 30.0
    _model: Pipeline | None = None

    def fit(
        self,
        source_parameters: np.ndarray,
        target_parameters: np.ndarray,
    ) -> QuadraticLogisticDensityRatio:
        source = np.asarray(source_parameters, dtype=float)
        target = np.asarray(target_parameters, dtype=float)
        if source.ndim != 2 or target.ndim != 2 or source.shape[1] != target.shape[1]:
            raise ValueError("source and target must be matrices with the same columns")
        if len(source) < 3 or len(target) < 3:
            raise ValueError("each domain must contain at least three rows")
        if not np.isfinite(source).all() or not np.isfinite(target).all():
            raise ValueError("domain parameters must be finite")

        parameters = np.vstack((source, target))
        domain = np.concatenate((np.zeros(len(source)), np.ones(len(target))))
        classifier = LogisticRegressionCV(
            Cs=self.cs,
            cv=StratifiedKFold(n_splits=3, shuffle=True, random_state=self.seed),
            scoring="neg_log_loss",
            class_weight="balanced",
            solver="lbfgs",
            max_iter=3000,
            n_jobs=1,
            l1_ratios=(0.0,),
            use_legacy_attributes=False,
        )
        self._model = make_pipeline(
            PolynomialFeatures(degree=2, include_bias=False),
            StandardScaler(),
            classifier,
        ).fit(parameters, domain)
        return self

    def log_ratio(self, parameters: np.ndarray) -> np.ndarray:
        """Predict the balanced-prior log target/source density ratio."""

        if self._model is None:
            raise RuntimeError("fit must be called before log_ratio")
        values = np.asarray(parameters, dtype=float)
        if values.ndim != 2 or not np.isfinite(values).all():
            raise ValueError("parameters must be a finite matrix")
        return np.asarray(self._model.decision_function(values), dtype=float)

    def ratio(self, parameters: np.ndarray) -> np.ndarray:
        """Predict finite positive importance weights on a documented log scale."""

        log_values = np.clip(
            self.log_ratio(parameters),
            -self.log_ratio_clip,
            self.log_ratio_clip,
        )
        return np.exp(log_values)

    @property
    def selected_c(self) -> float:
        """Regularization value chosen using domain labels only."""

        if self._model is None:
            raise RuntimeError("fit must be called before selected_c")
        classifier = self._model.steps[-1][1]
        return float(np.asarray(classifier.C_).item())
