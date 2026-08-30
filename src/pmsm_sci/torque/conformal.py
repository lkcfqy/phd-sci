"""Curvewise split-conformal bands and geometry-only support diagnostics."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from scipy.stats import norm
from sklearn.neighbors import NearestNeighbors


def curvewise_max_error(observed: np.ndarray, predicted: np.ndarray) -> np.ndarray:
    """Maximum absolute error over the full angle grid for every design."""

    truth = np.asarray(observed, dtype=float)
    estimate = np.asarray(predicted, dtype=float)
    if truth.shape != estimate.shape or truth.ndim != 2:
        raise ValueError("observed and predicted must share shape (designs, angles)")
    return np.max(np.abs(truth - estimate), axis=1)


def conformal_quantile(scores: np.ndarray, alpha: float) -> float:
    """Finite-sample split-conformal quantile using the higher order statistic."""

    values = np.asarray(scores, dtype=float)
    if values.ndim != 1 or len(values) == 0 or not np.isfinite(values).all():
        raise ValueError("scores must be a non-empty finite vector")
    if not 0.0 < alpha < 1.0:
        raise ValueError("alpha must lie strictly between zero and one")
    rank = int(np.ceil((len(values) + 1) * (1.0 - alpha)))
    return float(np.sort(values)[min(rank, len(values)) - 1])


@dataclass
class KnnGeometryScaler:
    """A label-free local difficulty scale based on design-space neighbour distance."""

    neighbours: int = 5
    floor: float = 0.25
    _model: NearestNeighbors | None = None
    _reference_distance: float | None = None

    def fit(self, parameters: np.ndarray) -> KnnGeometryScaler:
        x = np.asarray(parameters, dtype=float)
        if x.ndim != 2 or len(x) <= self.neighbours:
            raise ValueError("parameters must contain more rows than neighbours")
        self._model = NearestNeighbors(n_neighbors=self.neighbours + 1).fit(x)
        distances = self._model.kneighbors(x, return_distance=True)[0][:, self.neighbours]
        reference = float(np.median(distances))
        if not np.isfinite(reference) or reference <= 0:
            raise ValueError("reference neighbour distance must be positive")
        self._reference_distance = reference
        return self

    def distance(self, parameters: np.ndarray) -> np.ndarray:
        if self._model is None:
            raise RuntimeError("fit must be called before distance")
        x = np.asarray(parameters, dtype=float)
        return self._model.kneighbors(
            x,
            n_neighbors=self.neighbours,
            return_distance=True,
        )[0][:, -1]

    def scale(self, parameters: np.ndarray) -> np.ndarray:
        if self._reference_distance is None:
            raise RuntimeError("fit must be called before scale")
        return np.maximum(self.distance(parameters) / self._reference_distance, self.floor)


def support_p_values(calibration_distances: np.ndarray, test_distances: np.ndarray) -> np.ndarray:
    """Upper-tail conformal p-values for label-free geometric support."""

    calibration = np.asarray(calibration_distances, dtype=float)
    test = np.asarray(test_distances, dtype=float)
    if calibration.ndim != 1 or test.ndim != 1 or len(calibration) == 0:
        raise ValueError("distances must be one-dimensional and calibration non-empty")
    if not np.isfinite(calibration).all() or not np.isfinite(test).all():
        raise ValueError("distances must be finite")
    exceedances = (calibration[None, :] >= test[:, None]).sum(axis=1)
    return (1.0 + exceedances) / (len(calibration) + 1.0)


def wilson_interval(successes: int, total: int, confidence: float = 0.95) -> tuple[float, float]:
    """Wilson score interval for an independently sampled design proportion."""

    if total <= 0 or not 0 <= successes <= total:
        raise ValueError("require 0 <= successes <= total and total > 0")
    if not 0.0 < confidence < 1.0:
        raise ValueError("confidence must lie strictly between zero and one")
    probability = successes / total
    z_value = float(norm.ppf(0.5 + confidence / 2.0))
    denominator = 1.0 + z_value**2 / total
    centre = (probability + z_value**2 / (2.0 * total)) / denominator
    half_width = (
        z_value
        * np.sqrt(probability * (1.0 - probability) / total + z_value**2 / (4.0 * total**2))
        / denominator
    )
    return float(max(0.0, centre - half_width)), float(min(1.0, centre + half_width))
