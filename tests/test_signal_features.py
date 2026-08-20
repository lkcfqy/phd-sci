import numpy as np
import pytest

from pmsm_sci.faults.signal_features import (
    clarke_transform,
    current_features,
    sequence_unbalance_ratio,
)


def balanced_three_phase(sample_rate: float, duration: float, frequency: float) -> np.ndarray:
    time = np.arange(int(sample_rate * duration)) / sample_rate
    return np.column_stack(
        [
            np.sin(2 * np.pi * frequency * time),
            np.sin(2 * np.pi * frequency * time - 2 * np.pi / 3),
            np.sin(2 * np.pi * frequency * time + 2 * np.pi / 3),
        ]
    )


def test_balanced_current_has_negligible_zero_sequence_and_unbalance() -> None:
    sample_rate = 10_000.0
    current = balanced_three_phase(sample_rate, 0.2, 100.0)
    transformed = clarke_transform(current)
    assert np.sqrt(np.mean(transformed[:, 2] ** 2)) < 1e-12
    assert sequence_unbalance_ratio(current, sample_rate, 100.0) < 1e-12


def test_features_recover_fundamental_and_detect_imbalance() -> None:
    sample_rate = 10_000.0
    current = balanced_three_phase(sample_rate, 0.2, 100.0)
    current[:, 1] *= 0.7
    features = current_features(current, sample_rate)
    assert features["fundamental_hz"] == pytest.approx(100.0)
    assert features["sequence_unbalance"] > 0.05
    assert features["phase_rms_cv"] > 0.05
