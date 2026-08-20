"""Frozen utilities for the secondary transient PMSM validation."""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass
from pathlib import Path
from typing import NamedTuple

import numpy as np
from matio import load_from_mat
from matio.utils import MatlabOpaque, MatlabOpaqueArray
from numpy.typing import ArrayLike, NDArray

EXPECTED_SAMPLE_RATE_HZ = 10_000.0
SCORING_VARIABLE = "ialbt_meas"
ONSET_VARIABLE = "if_meas"
QC_VARIABLE = "we"
LOAD_VARIABLES = (SCORING_VARIABLE, ONSET_VARIABLE, QC_VARIABLE)

RECORD_NAME = re.compile(
    r"^(?P<condition>load_transient|steady_state|velocity_transient)_"
    r"(?P<setpoint>1000|1200)_(?P<turns>\d+)turns?\.mat$",
    flags=re.IGNORECASE,
)


@dataclass(frozen=True)
class FaultOnset:
    """Diagnostics from the fault-current-only onset rule."""

    onset_index: int
    baseline_stop_index: int
    rms_window_samples: int
    persistence_samples: int
    baseline_median: float
    baseline_robust_sigma: float
    peak_rms: float
    threshold: float


class RecordSplit(NamedTuple):
    """Record-disjoint fit and calibration identifiers for one held-out fold."""

    fit: tuple[str, ...]
    calibration: tuple[str, ...]


@dataclass(frozen=True)
class TransientMetadata:
    """Metadata encoded in a secondary-dataset path."""

    path: Path
    motor_id: str
    motor_watts: int
    condition: str
    setpoint_rad_s: int
    fault_turns: int
    winding_turns: int
    fault_phase: str

    @property
    def nominal_severity(self) -> float:
        return self.fault_turns / self.winding_turns

    @property
    def record_id(self) -> str:
        return (
            f"{self.motor_id}_{self.condition}_{self.setpoint_rad_s}_"
            f"{self.fault_turns}turn"
        )


@dataclass(frozen=True)
class TimeseriesData:
    """Numeric data and time recovered from one MATLAB timeseries object."""

    time: NDArray[np.float64]
    data: NDArray[np.float64]
    time_property_path: str
    data_property_path: str


@dataclass(frozen=True)
class TransientRecord:
    """Whitelisted signals from one secondary PMSM record."""

    metadata: TransientMetadata
    time: NDArray[np.float64]
    alpha_beta: NDArray[np.float64]
    fault_current: NDArray[np.float64]
    electrical_speed_rad_s: NDArray[np.float64]
    sample_rate_hz: float
    property_paths: dict[str, dict[str, str]]


def parse_transient_record_path(path: str | Path) -> TransientMetadata:
    """Parse motor, condition, setpoint, and severity from one official path."""

    record_path = Path(path)
    match = RECORD_NAME.fullmatch(record_path.name)
    if match is None:
        raise ValueError(f"Unrecognized transient record filename: {record_path.name}")
    parent = record_path.parent.name.casefold()
    if parent == "200wmotor":
        motor_id, motor_watts, winding_turns, phase = "200W", 200, 25, "a"
    elif parent == "20kwmotor":
        motor_id, motor_watts, winding_turns, phase = "20kW", 20_000, 7, "b"
    else:
        raise ValueError(f"Unrecognized transient motor directory: {record_path.parent.name}")
    metadata = TransientMetadata(
        path=record_path,
        motor_id=motor_id,
        motor_watts=motor_watts,
        condition=match.group("condition").lower(),
        setpoint_rad_s=int(match.group("setpoint")),
        fault_turns=int(match.group("turns")),
        winding_turns=winding_turns,
        fault_phase=phase,
    )
    allowed = (
        metadata.setpoint_rad_s == 1000 and metadata.fault_turns == 4
        or metadata.setpoint_rad_s == 1200 and metadata.fault_turns in {2, 4, 6}
        if motor_id == "200W"
        else metadata.setpoint_rad_s == 1000
        and metadata.fault_turns in {1, 2, 3}
    )
    if not allowed:
        raise ValueError(f"Record is outside the official motor design: {record_path}")
    return metadata


def validate_transient_inventory(records: list[TransientMetadata]) -> None:
    """Require the exact official 12-record/9-record factorial inventory."""

    if len(records) != 21 or len({record.record_id for record in records}) != 21:
        raise ValueError("Transient inventory must contain 21 unique records")
    counts = {motor: sum(record.motor_id == motor for record in records) for motor in ("200W", "20kW")}
    if counts != {"200W": 12, "20kW": 9}:
        raise ValueError(f"Unexpected motor record counts: {counts}")
    conditions = {"load_transient", "steady_state", "velocity_transient"}
    for motor, expected_per_condition in (("200W", 4), ("20kW", 3)):
        motor_records = [record for record in records if record.motor_id == motor]
        actual = {
            condition: sum(record.condition == condition for record in motor_records)
            for condition in conditions
        }
        if actual != dict.fromkeys(conditions, expected_per_condition):
            raise ValueError(f"Unexpected {motor} condition inventory: {actual}")


def _unwrap_scalar_opaque(value: object) -> MatlabOpaque:
    if isinstance(value, MatlabOpaque):
        return value
    if isinstance(value, MatlabOpaqueArray) and value.size == 1:
        item = value.reshape(-1)[0]
        if isinstance(item, MatlabOpaque):
            return item
    raise TypeError("Expected one scalar MATLAB opaque object")


def _numeric_leaves(
    value: object,
    *,
    path: tuple[str, ...] = (),
    seen: set[int] | None = None,
) -> list[tuple[tuple[str, ...], NDArray[np.generic]]]:
    """Recursively enumerate finite numeric arrays inside one opaque object."""

    if seen is None:
        seen = set()
    identity = id(value)
    if identity in seen:
        return []
    seen.add(identity)
    if isinstance(value, MatlabOpaque):
        return _numeric_leaves(value.properties, path=path, seen=seen)
    if isinstance(value, dict):
        leaves: list[tuple[tuple[str, ...], NDArray[np.generic]]] = []
        for key in sorted(value, key=str):
            leaves.extend(
                _numeric_leaves(value[key], path=(*path, str(key)), seen=seen)
            )
        return leaves
    if isinstance(value, np.ndarray):
        if np.issubdtype(value.dtype, np.number) or np.issubdtype(
            value.dtype, np.bool_
        ):
            return [(path, value)] if value.size else []
        if value.dtype == object:
            leaves = []
            for index, item in enumerate(value.reshape(-1)):
                leaves.extend(
                    _numeric_leaves(item, path=(*path, f"[{index}]"), seen=seen)
                )
            return leaves
        return []
    if isinstance(value, (list, tuple)):
        leaves = []
        for index, item in enumerate(value):
            leaves.extend(
                _numeric_leaves(item, path=(*path, f"[{index}]"), seen=seen)
            )
        return leaves
    return []


def _path_score(path: tuple[str, ...], role: str) -> int:
    components = [component.casefold() for component in path]
    score = 0
    for component in components:
        alphanumeric = re.sub(r"[^a-z0-9]", "", component)
        if alphanumeric == role:
            score = max(score, 100)
        elif role in alphanumeric:
            score = max(score, 60)
    opposite = "data" if role == "time" else "time"
    if any(opposite in re.sub(r"[^a-z0-9]", "", item) for item in components):
        score -= 50
    return score


def _as_time_candidate(
    values: NDArray[np.generic], sample_rate_hz: float
) -> NDArray[np.float64] | None:
    vector = np.asarray(values, dtype=np.float64).squeeze()
    if vector.ndim != 1 or vector.size < 3 or not np.isfinite(vector).all():
        return None
    differences = np.diff(vector)
    if np.any(differences <= 0):
        return None
    rate = 1.0 / float(np.median(differences))
    if not np.isclose(rate, sample_rate_hz, rtol=1e-3, atol=1e-6):
        return None
    return vector


def _as_data_candidate(
    values: NDArray[np.generic], expected_columns: int, expected_rows: int
) -> NDArray[np.float64] | None:
    array = np.asarray(values, dtype=np.float64).squeeze()
    if not np.isfinite(array).all():
        return None
    if expected_columns == 1:
        if array.ndim != 1 or array.size != expected_rows:
            return None
        return array.reshape(-1, 1)
    if array.ndim != 2:
        return None
    if array.shape == (expected_rows, expected_columns):
        return array
    if array.shape == (expected_columns, expected_rows):
        return array.T
    return None


def _scalar_property(properties: dict[object, object], name: str) -> object:
    if name not in properties:
        raise ValueError(f"uniform time metadata is missing {name}")
    value = np.asarray(properties[name]).squeeze()
    if value.ndim != 0:
        raise ValueError(f"uniform time metadata {name} is not scalar")
    return value.item()


def _implicit_uniform_time(
    opaque: MatlabOpaque, sample_rate_hz: float
) -> tuple[str, NDArray[np.float64]]:
    """Reconstruct a time vector from frozen MATLAB uniform-time metadata."""

    if not isinstance(opaque.properties, dict) or "TimeInfo" not in opaque.properties:
        raise ValueError("timeseries has no TimeInfo object")
    time_info = _unwrap_scalar_opaque(opaque.properties["TimeInfo"])
    if str(time_info.classname).casefold() != "tsdata.timemetadata":
        raise TypeError(f"Unexpected time metadata class: {time_info.classname!r}")
    if not isinstance(time_info.properties, dict):
        raise TypeError("TimeInfo properties are not a mapping")
    properties = time_info.properties
    units = str(_scalar_property(properties, "Units"))
    if units.casefold() != "seconds":
        raise ValueError(f"uniform time units must be seconds, found {units!r}")
    if not bool(_scalar_property(properties, "Initialized")):
        raise ValueError("uniform time metadata is not initialized")
    start = float(_scalar_property(properties, "Start_"))
    increment = float(_scalar_property(properties, "Increment_"))
    length_float = float(_scalar_property(properties, "Length"))
    length = round(length_float)
    if length < 3 or not np.isclose(length_float, length):
        raise ValueError(f"uniform time Length is invalid: {length_float}")
    if not np.isfinite(start) or not np.isfinite(increment) or increment <= 0:
        raise ValueError("uniform time start/increment is invalid")
    rate = 1.0 / increment
    if not np.isclose(rate, sample_rate_hz, rtol=1e-3, atol=1e-6):
        raise ValueError(f"uniform time metadata has unexpected sample rate: {rate}")
    explicit = np.asarray(properties.get("Time_", np.empty(0)))
    outer_explicit = np.asarray(opaque.properties.get("Time_", np.empty(0)))
    if explicit.size or outer_explicit.size:
        raise ValueError("implicit-time repair refuses non-empty Time_ storage")
    time = start + np.arange(length, dtype=np.float64) * increment
    return "TimeInfo/Start_+Increment_+Length", time


def extract_timeseries(
    value: object,
    *,
    expected_columns: int,
    sample_rate_hz: float = EXPECTED_SAMPLE_RATE_HZ,
    allow_implicit_uniform_time: bool = False,
) -> TimeseriesData:
    """Recover time/data arrays by a frozen semantic and shape-based rule."""

    opaque = _unwrap_scalar_opaque(value)
    if str(opaque.classname).casefold() != "timeseries":
        raise TypeError(f"Expected timeseries, found {opaque.classname!r}")
    leaves = _numeric_leaves(opaque)
    time_candidates: list[tuple[int, tuple[str, ...], NDArray[np.float64]]] = []
    for path, values in leaves:
        candidate = _as_time_candidate(values, sample_rate_hz)
        if candidate is not None:
            time_candidates.append((_path_score(path, "time"), path, candidate))
    if time_candidates:
        best_time_score = max(item[0] for item in time_candidates)
        best_times = [item for item in time_candidates if item[0] == best_time_score]
        if len(best_times) != 1:
            raise ValueError("timeseries time candidate is ambiguous")
        _, time_path, time = best_times[0]
        time_property_path = "/".join(time_path)
    elif allow_implicit_uniform_time:
        time_property_path, time = _implicit_uniform_time(opaque, sample_rate_hz)
        time_path = ()
    else:
        raise ValueError("timeseries has no 10 kHz monotonic time candidate")

    data_candidates: list[tuple[int, tuple[str, ...], NDArray[np.float64]]] = []
    for path, values in leaves:
        if time_path and path == time_path:
            continue
        candidate = _as_data_candidate(values, expected_columns, len(time))
        if candidate is not None:
            data_candidates.append((_path_score(path, "data"), path, candidate))
    if not data_candidates:
        raise ValueError("timeseries has no shape-compatible numeric data candidate")
    best_data_score = max(item[0] for item in data_candidates)
    best_data = [item for item in data_candidates if item[0] == best_data_score]
    if len(best_data) != 1:
        raise ValueError("timeseries data candidate is ambiguous")
    _, data_path, data = best_data[0]
    return TimeseriesData(
        time=time,
        data=data,
        time_property_path=time_property_path,
        data_property_path="/".join(data_path),
    )


def parse_loaded_transient_record(
    metadata: TransientMetadata,
    loaded: dict[str, object],
    *,
    allow_implicit_uniform_time: bool = False,
) -> TransientRecord:
    """Validate and join the three whitelisted loaded timeseries variables."""

    missing = sorted(set(LOAD_VARIABLES).difference(loaded))
    if missing:
        raise ValueError(f"MAT file is missing whitelisted variables: {missing}")
    scoring = extract_timeseries(
        loaded[SCORING_VARIABLE],
        expected_columns=2,
        allow_implicit_uniform_time=allow_implicit_uniform_time,
    )
    onset = extract_timeseries(
        loaded[ONSET_VARIABLE],
        expected_columns=1,
        allow_implicit_uniform_time=allow_implicit_uniform_time,
    )
    speed = extract_timeseries(
        loaded[QC_VARIABLE],
        expected_columns=1,
        allow_implicit_uniform_time=allow_implicit_uniform_time,
    )
    if not (
        np.array_equal(scoring.time, onset.time)
        and np.array_equal(scoring.time, speed.time)
    ):
        raise ValueError("whitelisted timeseries do not share an identical time vector")
    differences = np.diff(scoring.time)
    sample_rate = 1.0 / float(np.median(differences))
    relative_deviation = float(
        np.max(np.abs(differences - np.median(differences)))
        / np.median(differences)
    )
    if not np.isclose(sample_rate, EXPECTED_SAMPLE_RATE_HZ, rtol=1e-3, atol=1e-6):
        raise ValueError(f"Unexpected sample rate: {sample_rate}")
    if relative_deviation > 1e-3:
        raise ValueError(f"Time-step deviation exceeds 0.1%: {relative_deviation}")
    paths = {
        SCORING_VARIABLE: {
            "time": scoring.time_property_path,
            "data": scoring.data_property_path,
        },
        ONSET_VARIABLE: {
            "time": onset.time_property_path,
            "data": onset.data_property_path,
        },
        QC_VARIABLE: {
            "time": speed.time_property_path,
            "data": speed.data_property_path,
        },
    }
    return TransientRecord(
        metadata=metadata,
        time=scoring.time,
        alpha_beta=scoring.data,
        fault_current=onset.data[:, 0],
        electrical_speed_rad_s=speed.data[:, 0],
        sample_rate_hz=sample_rate,
        property_paths=paths,
    )


def load_transient_record(
    path: str | Path, *, allow_implicit_uniform_time: bool = False
) -> TransientRecord:
    """Load exactly the frozen scoring, onset-label, and QC variables."""

    metadata = parse_transient_record_path(path)
    loaded = load_from_mat(
        metadata.path,
        variable_names=list(LOAD_VARIABLES),
        raw_data=True,
    )
    return parse_loaded_transient_record(
        metadata,
        loaded,
        allow_implicit_uniform_time=allow_implicit_uniform_time,
    )


def pseudo_three_phase(alpha_beta: ArrayLike) -> NDArray[np.float64]:
    """Reconstruct balanced pseudo-abc currents from measured alpha-beta currents.

    Alpha-beta measurements contain no zero-sequence information.  The returned
    representation therefore imposes zero sequence and must never be used with a
    zero-sequence feature.
    """

    values = np.asarray(alpha_beta, dtype=np.float64)
    if values.ndim != 2 or values.shape[1] != 2:
        raise ValueError("alpha_beta must have shape (n_samples, 2)")
    if values.shape[0] < 2 or not np.isfinite(values).all():
        raise ValueError("alpha_beta must contain finite samples")
    alpha, beta = values.T
    phase_a = alpha
    phase_b = (-alpha + np.sqrt(3.0) * beta) / 2.0
    phase_c = (-alpha - np.sqrt(3.0) * beta) / 2.0
    return np.column_stack([phase_a, phase_b, phase_c])


def _positive_sample_count(seconds: float, sample_rate: float, label: str) -> int:
    if not np.isfinite(seconds) or seconds <= 0:
        raise ValueError(f"{label} must be positive")
    samples = round(seconds * sample_rate)
    if samples < 1:
        raise ValueError(f"{label} resolves to fewer than one sample")
    return samples


def _first_sustained_true(mask: NDArray[np.bool_], length: int) -> int | None:
    run_start = 0
    run_length = 0
    for index, value in enumerate(mask):
        if value:
            if run_length == 0:
                run_start = index
            run_length += 1
            if run_length >= length:
                return run_start
        else:
            run_length = 0
    return None


def fault_current_onset(
    fault_current: ArrayLike,
    sample_rate: float,
    *,
    rms_window_seconds: float = 0.010,
    baseline_fraction: float = 0.20,
    baseline_cap_seconds: float = 0.5,
    minimum_baseline_seconds: float = 0.020,
    robust_sigma_multiplier: float = 10.0,
    peak_fraction: float = 0.02,
    persistence_seconds: float = 0.020,
) -> FaultOnset:
    """Locate measured fault-current onset without consulting detector scores.

    Each RMS value is timestamped at the end of its causal window.  The returned
    index is therefore never moved earlier merely because a window straddles the
    physical current transition.
    """

    current = np.asarray(fault_current, dtype=np.float64).squeeze()
    if current.ndim != 1 or current.size < 2 or not np.isfinite(current).all():
        raise ValueError("fault_current must be one finite vector")
    if not np.isfinite(sample_rate) or sample_rate <= 0:
        raise ValueError("sample_rate must be positive")
    if not 0 < baseline_fraction < 1:
        raise ValueError("baseline_fraction must lie in (0, 1)")
    if robust_sigma_multiplier <= 0 or not 0 < peak_fraction < 1:
        raise ValueError("onset threshold parameters are invalid")

    rms_samples = _positive_sample_count(
        rms_window_seconds, sample_rate, "rms_window_seconds"
    )
    persistence_samples = _positive_sample_count(
        persistence_seconds, sample_rate, "persistence_seconds"
    )
    minimum_baseline_samples = _positive_sample_count(
        minimum_baseline_seconds, sample_rate, "minimum_baseline_seconds"
    )
    baseline_stop = min(
        int(np.floor(baseline_fraction * current.size)),
        _positive_sample_count(
            baseline_cap_seconds, sample_rate, "baseline_cap_seconds"
        ),
    )
    if baseline_stop < max(minimum_baseline_samples, rms_samples):
        raise ValueError("record does not contain the frozen minimum baseline")
    if current.size < rms_samples + persistence_samples:
        raise ValueError("record is too short for the onset rule")

    squared = np.square(current)
    cumulative = np.concatenate([[0.0], np.cumsum(squared, dtype=np.float64)])
    rms = np.sqrt(
        (cumulative[rms_samples:] - cumulative[:-rms_samples]) / rms_samples
    )
    baseline_rms = rms[: baseline_stop - rms_samples + 1]
    baseline_median = float(np.median(baseline_rms))
    baseline_sigma = float(
        1.4826 * np.median(np.abs(baseline_rms - baseline_median))
    )
    peak_rms = float(np.max(rms))
    threshold = float(
        max(
            baseline_median + robust_sigma_multiplier * baseline_sigma,
            peak_fraction * peak_rms,
        )
    )
    if not np.isfinite(threshold) or threshold <= np.finfo(np.float64).eps:
        raise ValueError("fault current contains no resolvable non-zero onset")

    first = _first_sustained_true(rms >= threshold, persistence_samples)
    if first is None:
        raise ValueError("fault-current threshold is never sustained")
    onset_index = first + rms_samples - 1
    if onset_index < baseline_stop:
        raise ValueError("detected onset overlaps the frozen baseline interval")
    return FaultOnset(
        onset_index=int(onset_index),
        baseline_stop_index=int(baseline_stop),
        rms_window_samples=rms_samples,
        persistence_samples=persistence_samples,
        baseline_median=baseline_median,
        baseline_robust_sigma=baseline_sigma,
        peak_rms=peak_rms,
        threshold=threshold,
    )


def pre_fault_window_bounds(
    n_samples: int,
    onset_index: int,
    sample_rate: float,
    *,
    window_seconds: float = 0.2,
    guard_seconds: float = 0.2,
) -> list[tuple[int, int]]:
    """Return record-start-aligned windows ending before the onset guard."""

    if n_samples <= 0 or not 0 < onset_index < n_samples:
        raise ValueError("invalid record length or onset index")
    window = _positive_sample_count(window_seconds, sample_rate, "window_seconds")
    guard = _positive_sample_count(guard_seconds, sample_rate, "guard_seconds")
    usable_stop = onset_index - guard
    if usable_stop < window:
        return []
    return [
        (start, start + window)
        for start in range(0, usable_stop - window + 1, window)
    ]


def post_fault_window_bounds(
    n_samples: int,
    onset_index: int,
    sample_rate: float,
    *,
    window_seconds: float = 0.2,
    horizon_seconds: float | None = None,
) -> list[tuple[int, int]]:
    """Return onset-aligned, non-overlapping complete post-fault windows."""

    if n_samples <= 0 or not 0 <= onset_index < n_samples:
        raise ValueError("invalid record length or onset index")
    window = _positive_sample_count(window_seconds, sample_rate, "window_seconds")
    usable_stop = n_samples
    if horizon_seconds is not None:
        horizon = _positive_sample_count(
            horizon_seconds, sample_rate, "horizon_seconds"
        )
        usable_stop = min(usable_stop, onset_index + horizon)
    return [
        (start, start + window)
        for start in range(onset_index, usable_stop - window + 1, window)
    ]


def record_disjoint_split(
    heldout_record_id: str,
    candidate_record_ids: list[str] | tuple[str, ...],
    *,
    salt: str = "20260821",
) -> RecordSplit:
    """Deterministically alternate whole records into fit and calibration."""

    if not heldout_record_id or not salt:
        raise ValueError("heldout_record_id and salt must be non-empty")
    candidates = tuple(candidate_record_ids)
    if len(candidates) != len(set(candidates)):
        raise ValueError("candidate record identifiers must be unique")
    if heldout_record_id in candidates:
        raise ValueError("the held-out record cannot be a split candidate")
    if len(candidates) < 2 or any(not value for value in candidates):
        raise ValueError("at least two non-empty candidate records are required")

    ordered = sorted(
        candidates,
        key=lambda candidate: hashlib.sha256(
            f"{salt}|{heldout_record_id}|{candidate}".encode()
        ).hexdigest(),
    )
    fit = tuple(ordered[::2])
    calibration = tuple(ordered[1::2])
    if len(fit) < len(calibration):
        raise AssertionError("the deterministic fit split must be the larger split")
    if set(fit) & set(calibration) or set(fit) | set(calibration) != set(candidates):
        raise AssertionError("record split is not a disjoint partition")
    return RecordSplit(fit=fit, calibration=calibration)
