"""Strict parser for the external dual-three-phase PMSM MAT records.

Only time and the two sets of three phase-current variables are deserialized.
The filename parser is frozen for both the currently available healthy files
and a future one-time fault-data reveal, so label handling need not be changed
after fault files become available.
"""

from __future__ import annotations

import hashlib
import math
import re
from collections.abc import Iterator, Mapping
from dataclasses import dataclass
from pathlib import Path

import numpy as np
from numpy.typing import NDArray
from scipy.io import loadmat

from pmsm_sci.faults.signal_features import current_features
from pmsm_sci.faults.tdms_io import window_ranges

EXPECTED_SAMPLE_RATE_HZ = 10_000.0
EXPECTED_SAMPLES = 415_001
ANALYSIS_START_SECONDS = 12.0
ANALYSIS_STOP_SECONDS = 36.0
WINDOW_SECONDS = 0.2
BLOCK_SECONDS = 3.0
MOTOR_ID = "external_dual_three_phase"
SUBSYSTEM_VARIABLES: dict[str, tuple[str, str, str]] = {
    "SubSys1": (
        "Currents_SubSys1_A",
        "Currents_SubSys1_B",
        "Currents_SubSys1_C",
    ),
    "SubSys2": (
        "Currents_SubSys2_A",
        "Currents_SubSys2_B",
        "Currents_SubSys2_C",
    ),
}
REQUIRED_MAT_VARIABLES = (
    "Time",
    *SUBSYSTEM_VARIABLES["SubSys1"],
    *SUBSYSTEM_VARIABLES["SubSys2"],
)

_FILENAME_PATTERN = re.compile(
    r"^spd10-5000rpm_flt(?:(?P<healthy>0)z|"
    r"(?P<fault_turns>[1-6])z(?P<fault_phase>[uv]))_"
    r"(?P<load_nm>\d+(?:\.\d+)?)NM\.mat$"
)


@dataclass(frozen=True)
class ExternalPmsmLabel:
    """Labels encoded in one accepted MAT filename."""

    load_nm: float
    fault_turns: int
    fault_phase: str | None
    is_healthy: bool

    @property
    def condition_token(self) -> str:
        if self.is_healthy:
            return "flt0z"
        return f"flt{self.fault_turns}z{self.fault_phase}"


@dataclass(frozen=True)
class ExternalPmsmMat:
    """Validated time and current arrays from one MAT file."""

    path: Path
    label: ExternalPmsmLabel
    time: NDArray[np.float64]
    currents: Mapping[str, NDArray[np.float32]]
    sample_rate_hz: float

    @property
    def samples(self) -> int:
        return int(self.time.size)


@dataclass(frozen=True)
class ExternalWindowIndex:
    """Absolute sample/time provenance with block IDs rebased to 12 s.

    Processed block IDs 0--7 correspond to full-record three-second blocks
    4--11. The absolute sample and time fields preserve the raw provenance.
    """

    block_id: int
    window_id: int
    start_sample: int
    stop_sample: int
    start_time_s: float
    stop_time_s: float


def parse_external_pmsm_filename(path: str | Path) -> ExternalPmsmLabel:
    """Parse only a frozen healthy or six-turn/phase fault filename pattern."""

    name = Path(path).name
    match = _FILENAME_PATTERN.fullmatch(name)
    if match is None:
        raise ValueError(f"Unsupported external PMSM filename: {name}")
    is_healthy = match.group("healthy") is not None
    fault_turns = 0 if is_healthy else int(match.group("fault_turns"))
    fault_phase = None if is_healthy else match.group("fault_phase")
    return ExternalPmsmLabel(
        load_nm=float(match.group("load_nm")),
        fault_turns=fault_turns,
        fault_phase=fault_phase,
        is_healthy=is_healthy,
    )


def discover_external_pmsm_files(input_dir: Path) -> list[Path]:
    """Return all and only MAT files matching the frozen filename grammar."""

    if not input_dir.is_dir():
        raise FileNotFoundError(f"External PMSM input directory not found: {input_dir}")
    accepted: list[tuple[Path, ExternalPmsmLabel]] = []
    for path in input_dir.iterdir():
        if not path.is_file() or path.suffix != ".mat":
            continue
        try:
            label = parse_external_pmsm_filename(path)
        except ValueError:
            continue
        accepted.append((path, label))
    if not accepted:
        raise FileNotFoundError(f"No filename-matched external PMSM MAT files in {input_dir}")

    keys = [
        (label.fault_turns, label.fault_phase, label.load_nm)
        for _, label in accepted
    ]
    if len(keys) != len(set(keys)):
        raise ValueError("Duplicate condition/load external PMSM MAT files")
    accepted.sort(
        key=lambda item: (
            item[1].fault_turns,
            item[1].fault_phase or "",
            item[1].load_nm,
        )
    )
    return [path for path, _ in accepted]


def _strict_column(
    variables: Mapping[str, object],
    name: str,
    *,
    dtype: np.dtype,
) -> NDArray[np.float64] | NDArray[np.float32]:
    if name not in variables:
        raise ValueError(f"Missing required MAT variable: {name}")
    value = np.asarray(variables[name])
    if value.ndim != 2 or value.shape[1] != 1:
        raise ValueError(f"{name} must be a MATLAB column vector, got {value.shape}")
    if value.dtype != dtype:
        raise ValueError(f"{name} must have dtype {dtype}, got {value.dtype}")
    column = value[:, 0]
    if not np.isfinite(column).all():
        raise ValueError(f"{name} contains non-finite values")
    return column


def _validate_time(
    time: NDArray[np.float64], *, expected_sample_rate_hz: float
) -> float:
    if time.size < 2:
        raise ValueError("Time must contain at least two samples")
    increments = np.diff(time)
    expected_increment = 1.0 / expected_sample_rate_hz
    if np.any(increments <= 0):
        raise ValueError("Time must be strictly increasing")
    if not np.allclose(
        increments,
        expected_increment,
        rtol=0.0,
        atol=expected_increment * 1e-6,
    ):
        raise ValueError("Time is not uniformly sampled at 10 kHz")
    sample_rate = float(1.0 / np.median(increments))
    if not math.isclose(
        sample_rate,
        expected_sample_rate_hz,
        rel_tol=1e-9,
        abs_tol=1e-6,
    ):
        raise ValueError(
            f"Expected {expected_sample_rate_hz:g} Hz, observed {sample_rate:g} Hz"
        )
    return sample_rate


def load_external_pmsm_mat(
    path: Path,
    *,
    expected_samples: int = EXPECTED_SAMPLES,
    expected_sample_rate_hz: float = EXPECTED_SAMPLE_RATE_HZ,
) -> ExternalPmsmMat:
    """Load a validated MAT record without deserializing voltage or dq arrays."""

    # Filename validation happens before opening the file. This prevents an
    # unrecognized condition from being read and then accidentally mislabeled.
    label = parse_external_pmsm_filename(path)
    variables = loadmat(
        path,
        variable_names=list(REQUIRED_MAT_VARIABLES),
        squeeze_me=False,
        struct_as_record=False,
        mat_dtype=True,
    )
    time = _strict_column(variables, "Time", dtype=np.dtype(np.float64))
    if time.size != expected_samples:
        raise ValueError(f"Expected {expected_samples} samples, found {time.size}")
    sample_rate_hz = _validate_time(
        time, expected_sample_rate_hz=expected_sample_rate_hz
    )

    currents: dict[str, NDArray[np.float32]] = {}
    observed_lengths = {time.size}
    for subsystem, names in SUBSYSTEM_VARIABLES.items():
        phases = [
            _strict_column(variables, name, dtype=np.dtype(np.float32))
            for name in names
        ]
        phase_lengths = {phase.size for phase in phases}
        observed_lengths.update(phase_lengths)
        if phase_lengths != {time.size}:
            raise ValueError(
                "Time and all SubSys1/2 A/B/C currents must have equal length"
            )
        currents[subsystem] = np.column_stack(phases).astype(np.float32, copy=False)
    if observed_lengths != {time.size}:
        raise ValueError("Time and all SubSys1/2 A/B/C currents must have equal length")

    record = ExternalPmsmMat(
        path=path,
        label=label,
        time=time,
        currents=currents,
        sample_rate_hz=sample_rate_hz,
    )
    analysis_sample_bounds(record)
    return record


def analysis_sample_bounds(record: ExternalPmsmMat) -> tuple[int, int]:
    """Return exact indices for the frozen half-open interval [12, 36) s."""

    start = int(np.searchsorted(record.time, ANALYSIS_START_SECONDS, side="left"))
    stop = int(np.searchsorted(record.time, ANALYSIS_STOP_SECONDS, side="left"))
    if start >= record.samples or stop >= record.samples or start >= stop:
        raise ValueError("Record does not contain the frozen [12, 36) s interval")
    tolerance = 0.25 / record.sample_rate_hz
    if not math.isclose(
        float(record.time[start]),
        ANALYSIS_START_SECONDS,
        rel_tol=0.0,
        abs_tol=tolerance,
    ) or not math.isclose(
        float(record.time[stop]),
        ANALYSIS_STOP_SECONDS,
        rel_tol=0.0,
        abs_tol=tolerance,
    ):
        raise ValueError("Frozen analysis boundaries do not align to sample times")
    expected = round(
        (ANALYSIS_STOP_SECONDS - ANALYSIS_START_SECONDS) * record.sample_rate_hz
    )
    if stop - start != expected:
        raise ValueError("Frozen analysis interval has an unexpected sample count")
    return start, stop


def iter_analysis_windows(
    record: ExternalPmsmMat, subsystem: str
) -> Iterator[tuple[ExternalWindowIndex, NDArray[np.float32]]]:
    """Yield 120 non-overlapping 0.2 s windows in eight 3 s macroblocks."""

    if subsystem not in SUBSYSTEM_VARIABLES:
        raise ValueError(f"Unknown subsystem: {subsystem}")
    segment_start, segment_stop = analysis_sample_bounds(record)
    window_samples = round(WINDOW_SECONDS * record.sample_rate_hz)
    block_samples = round(BLOCK_SECONDS * record.sample_rate_hz)
    ranges = window_ranges(
        segment_stop - segment_start,
        window_samples=window_samples,
        stride_samples=window_samples,
        block_samples=block_samples,
    )
    if len(ranges) != 120 or len({item.block_id for item in ranges}) != 8:
        raise AssertionError("Frozen external protocol must produce 120 windows/8 blocks")
    current = record.currents[subsystem]
    for item in ranges:
        absolute_start = segment_start + item.start
        absolute_stop = segment_start + item.stop
        index = ExternalWindowIndex(
            block_id=item.block_id,
            window_id=item.window_id,
            start_sample=absolute_start,
            stop_sample=absolute_stop,
            start_time_s=float(record.time[absolute_start]),
            stop_time_s=float(record.time[absolute_stop]),
        )
        yield index, current[absolute_start:absolute_stop]


def file_sha256(path: Path, chunk_size: int = 8 * 1024 * 1024) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        while chunk := stream.read(chunk_size):
            digest.update(chunk)
    return digest.hexdigest()


def _number_token(value: float) -> str:
    if value.is_integer():
        return str(int(value))
    return f"{value:g}".replace(".", "p")


def record_id(record: ExternalPmsmMat) -> str:
    """Return the physical MAT-record identifier shared by both subsystems."""

    return (
        f"external_dual_three_phase_{record.label.condition_token}_"
        f"load_{_number_token(record.label.load_nm)}nm"
    )


def extract_feature_rows(
    record: ExternalPmsmMat, *, source_sha256: str
) -> list[dict[str, object]]:
    """Extract existing transparent current features for both subsystems."""

    if re.fullmatch(r"[0-9a-f]{64}", source_sha256) is None:
        raise ValueError("source_sha256 must be a lowercase SHA-256 digest")
    rows: list[dict[str, object]] = []
    physical_record_id = record_id(record)
    for subsystem in SUBSYSTEM_VARIABLES:
        for index, current in iter_analysis_windows(record, subsystem):
            rows.append(
                {
                    "source_filename": record.path.name,
                    "source_path": str(record.path.resolve()),
                    "source_sha256": source_sha256,
                    "load_nm": record.label.load_nm,
                    "fault_turns": record.label.fault_turns,
                    "fault_phase": record.label.fault_phase,
                    "subsystem": subsystem,
                    "record_id": physical_record_id,
                    "motor_id": MOTOR_ID,
                    "is_healthy": record.label.is_healthy,
                    "sample_rate_hz": record.sample_rate_hz,
                    "block_id": index.block_id,
                    "window_id": index.window_id,
                    "start_sample": index.start_sample,
                    "stop_sample": index.stop_sample,
                    "start_time_s": index.start_time_s,
                    "stop_time_s": index.stop_time_s,
                    **current_features(current, record.sample_rate_hz),
                }
            )
    return rows
