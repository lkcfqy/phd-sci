"""Finite-sample split-conformal utilities for high-valued anomaly scores."""

from __future__ import annotations

import math

import numpy as np
from numpy.typing import ArrayLike, NDArray


def _scores(values: ArrayLike, name: str) -> NDArray[np.float64]:
    result = np.asarray(values, dtype=np.float64).reshape(-1)
    if result.size == 0:
        raise ValueError(f"{name} must not be empty")
    if not np.isfinite(result).all():
        raise ValueError(f"{name} must contain only finite values")
    return result


def conformal_threshold(calibration_scores: ArrayLike, alpha: float) -> float:
    """Return the conservative split-conformal upper threshold.

    The order statistic is ``ceil((n + 1) * (1 - alpha))``. If the requested
    risk level cannot be resolved with ``n`` calibration units, the valid
    finite-sample threshold is infinite rather than an anti-conservative value.
    """

    calibration = _scores(calibration_scores, "calibration_scores")
    if not 0 < alpha < 1:
        raise ValueError("alpha must lie strictly between zero and one")
    rank = math.ceil((calibration.size + 1) * (1 - alpha))
    if rank > calibration.size:
        return math.inf
    return float(np.partition(calibration, rank - 1)[rank - 1])


def conformal_p_values(
    calibration_scores: ArrayLike, test_scores: ArrayLike
) -> NDArray[np.float64]:
    """Compute upper-tail conformal p-values, treating larger scores as anomalous."""

    calibration = _scores(calibration_scores, "calibration_scores")
    test = _scores(test_scores, "test_scores")
    exceedances = (calibration[:, None] >= test[None, :]).sum(axis=0)
    return (1.0 + exceedances) / (calibration.size + 1.0)


def aggregate_window_scores(
    scores: ArrayLike, block_ids: ArrayLike, *, quantile: float = 1.0
) -> tuple[NDArray[np.int64], NDArray[np.float64]]:
    """Aggregate dependent window scores into non-overlapping block scores."""

    window_scores = _scores(scores, "scores")
    blocks = np.asarray(block_ids).reshape(-1)
    if blocks.size != window_scores.size:
        raise ValueError("scores and block_ids must have equal length")
    if not 0 < quantile <= 1:
        raise ValueError("quantile must lie in (0, 1]")
    unique = np.unique(blocks)
    aggregated = np.asarray(
        [
            np.quantile(window_scores[blocks == block], quantile, method="higher")
            for block in unique
        ],
        dtype=np.float64,
    )
    return unique.astype(np.int64), aggregated
