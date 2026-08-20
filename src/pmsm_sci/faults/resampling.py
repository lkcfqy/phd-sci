"""Frozen anti-alias resampling helpers for current sensitivity analyses."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from numpy.typing import ArrayLike, NDArray
from scipy.signal import resample_poly

from .tdms_io import WindowIndex, window_ranges


@dataclass(frozen=True)
class PolyphaseSpecification:
    """Fully explicit mechanical resampling specification."""

    source_rate_hz: int
    target_rate_hz: int
    up: int
    down: int
    window: tuple[str, float] = ("kaiser", 5.0)
    padtype: str = "line"


def polyphase_specification(
    source_rate_hz: float, target_rate_hz: float
) -> PolyphaseSpecification:
    """Return an exact integer-decimation specification.

    This sensitivity arm deliberately supports only mechanical integer
    decimation.  The TDMS metadata represents 100 kHz as a nearly exact float,
    so rates are accepted when they are numerically indistinguishable from an
    integer before the ratio is checked.
    """

    if not np.isfinite(source_rate_hz) or not np.isfinite(target_rate_hz):
        raise ValueError("sample rates must be finite")
    if source_rate_hz <= 0 or target_rate_hz <= 0:
        raise ValueError("sample rates must be positive")
    source_integer = round(source_rate_hz)
    target_integer = round(target_rate_hz)
    if not np.isclose(source_rate_hz, source_integer, rtol=0.0, atol=1e-6):
        raise ValueError("source sample rate must be integer-valued")
    if not np.isclose(target_rate_hz, target_integer, rtol=0.0, atol=1e-6):
        raise ValueError("target sample rate must be integer-valued")
    if source_integer <= target_integer:
        raise ValueError("target sample rate must be below source sample rate")
    if source_integer % target_integer:
        raise ValueError("sample rates must define an exact integer decimation")
    return PolyphaseSpecification(
        source_rate_hz=source_integer,
        target_rate_hz=target_integer,
        up=1,
        down=source_integer // target_integer,
    )


def polyphase_downsample_current(
    values: ArrayLike,
    *,
    source_rate_hz: float,
    target_rate_hz: float,
) -> NDArray[np.float64]:
    """Anti-alias and decimate one complete three-phase current record.

    Filtering the complete record before windowing prevents each 0.2 s window
    from acquiring its own artificial filter boundary.  The Kaiser filter and
    line extension are frozen engineering choices, not selected on external
    fault performance.
    """

    current = np.asarray(values, dtype=np.float64)
    if current.ndim != 2 or current.shape[1] != 3:
        raise ValueError("current record must have shape (n_samples, 3)")
    if current.shape[0] < 16:
        raise ValueError("current record must contain at least 16 samples")
    if not np.isfinite(current).all():
        raise ValueError("current record contains non-finite values")
    specification = polyphase_specification(source_rate_hz, target_rate_hz)
    downsampled = resample_poly(
        current,
        specification.up,
        specification.down,
        axis=0,
        window=specification.window,
        padtype=specification.padtype,
    )
    expected = (len(current) + specification.down - 1) // specification.down
    if downsampled.shape != (expected, 3):
        raise AssertionError(
            f"Unexpected polyphase output shape {downsampled.shape}; expected {(expected, 3)}"
        )
    return np.asarray(downsampled, dtype=np.float64)


def resampled_window_ranges(
    n_samples: int,
    *,
    sample_rate_hz: float,
    window_seconds: float,
    stride_seconds: float,
    block_seconds: float,
) -> tuple[WindowIndex, ...]:
    """Build the frozen physical-time windows on a resampled record."""

    if sample_rate_hz <= 0:
        raise ValueError("sample_rate_hz must be positive")
    durations = (window_seconds, stride_seconds, block_seconds)
    if not all(np.isfinite(value) and value > 0 for value in durations):
        raise ValueError("window, stride, and block durations must be positive")
    counts = tuple(round(value * sample_rate_hz) for value in durations)
    if any(
        not np.isclose(value * sample_rate_hz, count, rtol=0.0, atol=1e-8)
        for value, count in zip(durations, counts, strict=True)
    ):
        raise ValueError("time settings must map to whole samples")
    window_samples, stride_samples, block_samples = counts
    return window_ranges(
        n_samples,
        window_samples=window_samples,
        stride_samples=stride_samples,
        block_samples=block_samples,
    )
