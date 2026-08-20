import numpy as np
import pytest

from pmsm_sci.faults.resampling import (
    polyphase_downsample_current,
    polyphase_specification,
    resampled_window_ranges,
)


def sinusoid_amplitude(values: np.ndarray, sample_rate: float, frequency: float) -> float:
    time = np.arange(len(values), dtype=np.float64) / sample_rate
    kernel = np.exp(-2j * np.pi * frequency * time)
    return float(2 * np.abs(values @ kernel) / len(values))


def test_polyphase_downsampling_suppresses_a_deliberate_alias() -> None:
    source_rate = 100_000
    target_rate = 10_000
    duration = 1.0
    time = np.arange(round(duration * source_rate), dtype=np.float64) / source_rate
    phases = np.arange(3) * 2 * np.pi / 3
    fundamental = np.sin(2 * np.pi * 200 * time[:, None] - phases)
    aliasing_component = np.sin(2 * np.pi * 20_200 * time[:, None] - phases)
    current = fundamental + aliasing_component

    filtered = polyphase_downsample_current(
        current, source_rate_hz=source_rate, target_rate_hz=target_rate
    )
    naive = current[::10]
    interior = slice(200, -200)
    filtered_amplitude = sinusoid_amplitude(
        filtered[interior, 0], target_rate, 200
    )
    naive_amplitude = sinusoid_amplitude(naive[interior, 0], target_rate, 200)

    assert filtered.shape == (10_000, 3)
    assert filtered_amplitude == pytest.approx(1.0, abs=0.03)
    assert filtered_amplitude < 0.65 * naive_amplitude


def test_polyphase_specification_rejects_noninteger_decimation() -> None:
    specification = polyphase_specification(100_000.00000000028, 10_000)
    assert (specification.up, specification.down) == (1, 10)
    with pytest.raises(ValueError, match="exact integer decimation"):
        polyphase_specification(44_100, 10_000)


def test_resampled_ranges_preserve_frozen_time_geometry() -> None:
    ranges = resampled_window_ranges(
        60_000,
        sample_rate_hz=10_000,
        window_seconds=0.2,
        stride_seconds=0.2,
        block_seconds=3.0,
    )
    assert len(ranges) == 30
    assert {item.block_id for item in ranges} == {0, 1}
    assert ranges[0].start == 0
    assert ranges[-1].stop == 60_000


def test_polyphase_downsampling_validates_current_shape() -> None:
    with pytest.raises(ValueError, match="shape"):
        polyphase_downsample_current(
            np.ones((100, 2)), source_rate_hz=100_000, target_rate_hz=10_000
        )
