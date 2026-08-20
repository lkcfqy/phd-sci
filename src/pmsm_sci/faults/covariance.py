"""Healthy-reference covariance scores for cross-machine anomaly detection."""

from __future__ import annotations

from collections.abc import Sequence

import numpy as np
from numpy.typing import ArrayLike, NDArray


def sample_covariance(values: ArrayLike) -> NDArray[np.float64]:
    data = np.asarray(values, dtype=np.float64)
    if data.ndim != 2 or data.shape[0] < 2:
        raise ValueError("values must contain at least two rows")
    covariance = np.atleast_2d(np.cov(data, rowvar=False, ddof=1))
    return (covariance + covariance.T) / 2


def regularize_covariance(
    covariance: ArrayLike, ridge_fraction: float = 1e-3
) -> NDArray[np.float64]:
    matrix = np.asarray(covariance, dtype=np.float64)
    if matrix.ndim != 2 or matrix.shape[0] != matrix.shape[1]:
        raise ValueError("covariance must be square")
    if ridge_fraction <= 0:
        raise ValueError("ridge_fraction must be positive")
    matrix = (matrix + matrix.T) / 2
    average_variance = float(np.trace(matrix) / matrix.shape[0])
    ridge = ridge_fraction * max(average_variance, np.finfo(float).eps)
    return matrix + ridge * np.eye(matrix.shape[0])


def entity_balanced_covariance(
    covariances: Sequence[ArrayLike], ridge_fraction: float = 1e-3
) -> NDArray[np.float64]:
    """Average one covariance per motor, then add a small SPD ridge."""

    if not covariances:
        raise ValueError("At least one covariance is required")
    matrices = [np.asarray(covariance, dtype=np.float64) for covariance in covariances]
    shapes = {matrix.shape for matrix in matrices}
    if len(shapes) != 1:
        raise ValueError("All covariances must have equal shape")
    return regularize_covariance(np.mean(matrices, axis=0), ridge_fraction)


def _symmetric_matrix_function(
    matrix: NDArray[np.float64], function
) -> NDArray[np.float64]:
    eigenvalues, eigenvectors = np.linalg.eigh((matrix + matrix.T) / 2)
    if np.any(eigenvalues <= 0):
        raise ValueError("Matrix must be positive definite")
    transformed = (eigenvectors * function(eigenvalues)) @ eigenvectors.T
    return (transformed + transformed.T) / 2


def log_euclidean_entity_covariance(
    covariances: Sequence[ArrayLike], ridge_fraction: float = 1e-2
) -> NDArray[np.float64]:
    """Compute an equal-motor log-Euclidean mean on the SPD covariance manifold."""

    if not covariances:
        raise ValueError("At least one covariance is required")
    regularized = [
        regularize_covariance(covariance, ridge_fraction) for covariance in covariances
    ]
    shapes = {matrix.shape for matrix in regularized}
    if len(shapes) != 1:
        raise ValueError("All covariances must have equal shape")
    mean_log = np.mean(
        [_symmetric_matrix_function(matrix, np.log) for matrix in regularized], axis=0
    )
    eigenvalues, eigenvectors = np.linalg.eigh((mean_log + mean_log.T) / 2)
    result = (eigenvectors * np.exp(eigenvalues)) @ eigenvectors.T
    return (result + result.T) / 2


def mahalanobis_scores(
    values: ArrayLike, covariance: ArrayLike, location: ArrayLike
) -> NDArray[np.float64]:
    data = np.asarray(values, dtype=np.float64)
    matrix = np.asarray(covariance, dtype=np.float64)
    center = np.asarray(location, dtype=np.float64).reshape(-1)
    if data.ndim != 2 or matrix.shape != (data.shape[1], data.shape[1]):
        raise ValueError("data and covariance dimensions are inconsistent")
    if center.size != data.shape[1]:
        raise ValueError("location dimension is inconsistent")
    centered = data - center
    precision = np.linalg.pinv(matrix, hermitian=True)
    return np.einsum("ij,jk,ik->i", centered, precision, centered)
