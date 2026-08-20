import numpy as np
import pytest

from pmsm_sci.faults.covariance import (
    entity_balanced_covariance,
    log_euclidean_entity_covariance,
    mahalanobis_scores,
    sample_covariance,
)


def test_entity_balanced_covariance_gives_each_motor_equal_weight() -> None:
    covariance = entity_balanced_covariance([np.eye(2), 3 * np.eye(2)], 1e-6)
    assert np.diag(covariance) == pytest.approx([2.000002, 2.000002])


def test_mahalanobis_score_increases_with_distance() -> None:
    scores = mahalanobis_scores([[0.0, 0.0], [2.0, 0.0]], np.eye(2), [0.0, 0.0])
    assert scores.tolist() == [0.0, 4.0]


def test_log_euclidean_covariance_is_geometric_for_diagonal_case() -> None:
    covariance = log_euclidean_entity_covariance(
        [np.eye(2), 4 * np.eye(2)], ridge_fraction=1e-6
    )
    assert np.diag(covariance) == pytest.approx([2.000002, 2.000002])


def test_sample_covariance_is_symmetric() -> None:
    covariance = sample_covariance([[0.0, 0.0], [1.0, 2.0], [2.0, 1.0]])
    assert np.allclose(covariance, covariance.T)
