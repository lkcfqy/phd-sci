"""Session-anchored healthy residual scoring for calibration-transport repair."""

from __future__ import annotations

import numpy as np
from numpy.typing import ArrayLike, NDArray
from sklearn.covariance import LedoitWolf


def _matrix(values: ArrayLike, name: str) -> NDArray[np.float64]:
    result = np.asarray(values, dtype=np.float64)
    if result.ndim != 2 or result.shape[0] == 0 or result.shape[1] == 0:
        raise ValueError(f"{name} must be a non-empty two-dimensional array")
    if not np.isfinite(result).all():
        raise ValueError(f"{name} must contain only finite values")
    return result


def session_residuals(
    anchor_values: ArrayLike,
    score_values: ArrayLike,
) -> NDArray[np.float64]:
    """Subtract the coordinate-wise median of at least two healthy anchor windows."""

    anchor = _matrix(anchor_values, "anchor_values")
    score = _matrix(score_values, "score_values")
    if anchor.shape[0] < 2:
        raise ValueError("At least two healthy anchor windows are required")
    if anchor.shape[1] != score.shape[1]:
        raise ValueError("Anchor and score feature dimensions differ")
    return score - np.median(anchor, axis=0)


class SessionAnchoredDetector:
    """Shrinkage Mahalanobis geometry learned from healthy within-session changes."""

    def fit(self, healthy_residuals: ArrayLike) -> SessionAnchoredDetector:
        residual = _matrix(healthy_residuals, "healthy_residuals")
        if residual.shape[0] <= residual.shape[1]:
            raise ValueError("Healthy residual rows must exceed the feature dimension")
        self.center_ = np.median(residual, axis=0)
        centered = residual - self.center_
        mad = 1.4826 * np.median(np.abs(centered), axis=0)
        standard = np.std(centered, axis=0)
        floor = np.sqrt(np.finfo(np.float64).eps) * np.maximum(
            np.max(np.abs(residual), axis=0), 1.0
        )
        self.scale_ = np.where(mad > floor, mad, standard)
        self.scale_ = np.where(self.scale_ > floor, self.scale_, 1.0)
        standardized = centered / self.scale_
        self.covariance_ = LedoitWolf(assume_centered=False, store_precision=True)
        self.covariance_.fit(standardized)
        return self

    def score(self, residuals: ArrayLike) -> NDArray[np.float64]:
        values = _matrix(residuals, "residuals")
        if not hasattr(self, "covariance_"):
            raise RuntimeError("Session-anchored detector has not been fitted")
        if values.shape[1] != len(self.center_):
            raise ValueError("Unexpected residual feature dimension")
        standardized = (values - self.center_) / self.scale_
        centered = standardized - self.covariance_.location_
        scores = np.einsum(
            "ij,jk,ik->i",
            centered,
            self.covariance_.precision_,
            centered,
            optimize=True,
        )
        scores = np.maximum(np.asarray(scores, dtype=np.float64), 0.0)
        if not np.isfinite(scores).all():
            raise FloatingPointError("Session-anchored detector produced non-finite scores")
        return scores
