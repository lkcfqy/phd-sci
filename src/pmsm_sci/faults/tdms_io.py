"""Memory-bounded readers for the KAIST three-phase current TDMS files."""

from __future__ import annotations

from collections.abc import Iterator
from dataclasses import dataclass
from pathlib import Path

import numpy as np
from nptdms import TdmsFile
from numpy.typing import NDArray


@dataclass(frozen=True)
class CurrentFileMetadata:
    path: Path
    channel_names: tuple[str, str, str]
    samples: int
    sample_rate_hz: float
    duration_seconds: float


@dataclass(frozen=True)
class WindowIndex:
    block_id: int
    window_id: int
    start: int
    stop: int


def window_ranges(
    n_samples: int, *, window_samples: int, stride_samples: int, block_samples: int
) -> tuple[WindowIndex, ...]:
    """Build windows that are entirely contained within non-overlapping blocks."""

    if min(n_samples, window_samples, stride_samples, block_samples) <= 0:
        raise ValueError("sample counts must be positive")
    if window_samples > block_samples:
        raise ValueError("window_samples cannot exceed block_samples")
    ranges: list[WindowIndex] = []
    window_id = 0
    n_complete_blocks = n_samples // block_samples
    for block_id in range(n_complete_blocks):
        block_start = block_id * block_samples
        block_stop = block_start + block_samples
        for start in range(block_start, block_stop - window_samples + 1, stride_samples):
            ranges.append(
                WindowIndex(
                    block_id=block_id,
                    window_id=window_id,
                    start=start,
                    stop=start + window_samples,
                )
            )
            window_id += 1
    return tuple(ranges)


def _current_channels(tdms: TdmsFile):
    candidates = [
        channel
        for group in tdms.groups()
        for channel in group.channels()
        if str(channel.properties.get("unit_string", "")).lower() == "a"
    ]
    if len(candidates) != 3:
        raise ValueError(f"Expected three current channels, found {len(candidates)}")
    return sorted(candidates, key=lambda channel: channel.name)


def inspect_current_tdms(path: Path) -> CurrentFileMetadata:
    """Read channel structure and waveform timing without loading signal arrays."""

    tdms = TdmsFile.open(path)
    try:
        channels = _current_channels(tdms)
        lengths = {len(channel) for channel in channels}
        increments = {float(channel.properties["wf_increment"]) for channel in channels}
        if len(lengths) != 1 or len(increments) != 1:
            raise ValueError("Current channels do not share length and sample interval")
        samples = lengths.pop()
        increment = increments.pop()
        sample_rate = 1.0 / increment
        return CurrentFileMetadata(
            path=path,
            channel_names=tuple(channel.name for channel in channels),
            samples=samples,
            sample_rate_hz=sample_rate,
            duration_seconds=samples / sample_rate,
        )
    finally:
        tdms.close()


def iter_current_windows(
    path: Path,
    *,
    window_seconds: float,
    stride_seconds: float,
    block_seconds: float,
    max_duration_seconds: float | None = None,
) -> Iterator[tuple[WindowIndex, NDArray[np.float64]]]:
    """Yield three-phase windows from one fully materialized TDMS record.

    The public files use many TDMS segments, including a few irregular segment
    lengths. Loading the record through ``TdmsFile.read`` avoids an upstream lazy
    slice edge case while keeping peak signal memory below roughly 300 MB.
    """

    metadata = inspect_current_tdms(path)
    window_samples = round(window_seconds * metadata.sample_rate_hz)
    stride_samples = round(stride_seconds * metadata.sample_rate_hz)
    block_samples = round(block_seconds * metadata.sample_rate_hz)
    used_samples = metadata.samples
    if max_duration_seconds is not None:
        if max_duration_seconds <= 0:
            raise ValueError("max_duration_seconds must be positive")
        used_samples = min(
            used_samples, round(max_duration_seconds * metadata.sample_rate_hz)
        )
    ranges = window_ranges(
        used_samples,
        window_samples=window_samples,
        stride_samples=stride_samples,
        block_samples=block_samples,
    )

    tdms = TdmsFile.read(path)
    try:
        channels = _current_channels(tdms)
        data = np.column_stack([channel[:] for channel in channels]).astype(
            np.float64, copy=False
        )
        for index in ranges:
            yield index, data[index.start:index.stop]
    finally:
        tdms.close()
