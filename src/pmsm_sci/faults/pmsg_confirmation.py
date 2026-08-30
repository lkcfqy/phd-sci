"""Frozen parser and current-feature protocol for the independent PMSG bench."""

from __future__ import annotations

import math
import re
from collections.abc import Iterator, Mapping
from dataclasses import dataclass
from pathlib import Path

import numpy as np
from numpy.typing import NDArray
from scipy.io import loadmat

from pmsm_sci.faults.signal_features import current_features

EXPECTED_SAMPLE_RATE_HZ = 20_000.0
ACCEPTED_SAMPLE_COUNTS = (60_000, 60_001)
WINDOW_SECONDS = 0.2
REQUIRED_MAT_VARIABLES = ("t", "Ia", "Ib", "Ic")

HEALTH_ANALYSIS_INTERVAL = (0.2, 2.8)
PRE_FAULT_INTERVAL = (0.2, 0.8)
FAULT_ACTIVE_INTERVAL = (1.0, 1.4)
RECOVERY_INTERVAL = (1.6, 2.8)
SEGMENT_INTERVALS = {
    "health_analysis": HEALTH_ANALYSIS_INTERVAL,
    "pre_fault": PRE_FAULT_INTERVAL,
    "fault_active": FAULT_ACTIVE_INTERVAL,
    "recovery": RECOVERY_INTERVAL,
}

HEALTH_FIT_CONDITIONS = (
    (1200, 52),
    (1200, 80),
    (1800, 52),
    (1800, 80),
)
HEALTH_CALIBRATION_CONDITIONS = ((1200, 64), (1500, 64), (1800, 64))
HEALTH_TEST_CONDITIONS = ((1500, 52), (1500, 80))

TERMINAL_POSITION_PERCENT = {
    "D01": 0.460,
    "D02": 2.310,
    "D03": 10.000,
    "D04": 12.500,
    "D05": 12.900,
    "D06": 14.800,
    "D07": 22.200,
    "D08": 25.000,
    "D09": 29.600,
    "D10": 32.400,
    "D11": 42.200,
    "D12": 44.900,
    "D13": 50.000,
    "D14": 52.300,
    "D15": 59.700,
    "D16": 61.600,
    "D17": 62.500,
    "D18": 64.800,
    "D19": 72.200,
    "D20": 74.100,
    "D21": 78.600,
    "D22": 82.400,
    "D23": 92.100,
    "D24": 94.900,
}

_HEALTH_PATTERN = re.compile(
    r"^HEALTHY_S(?P<speed>1200|1500|1800)_T(?P<torque>52|64|80)\.mat$"
)
_FAULT_PATTERN = re.compile(
    r"^FAULT_(?P<family>TURNS|WINDINGS)_"
    r"(?P<terminal_a>D(?:0[1-9]|1[0-9]|2[0-4]))_"
    r"(?P<terminal_b>D(?:0[1-9]|1[0-9]|2[0-4]))_"
    r"R(?P<resistance_code>\d{3})_"
    r"S(?P<speed>1200|1500|1800)_T(?P<torque>52|64|80)\.mat$"
)


@dataclass(frozen=True)
class PmsgLabel:
    """Labels and nominal operating context encoded in one frozen filename."""

    is_healthy: bool
    speed_rpm: int
    torque_setting_code: int
    fault_family: str | None
    terminal_a: str | None
    terminal_b: str | None
    resistance_code: str | None

    @property
    def condition(self) -> tuple[int, int]:
        return self.speed_rpm, self.torque_setting_code

    @property
    def fault_span_percent(self) -> float | None:
        if self.is_healthy:
            return None
        if self.terminal_a is None or self.terminal_b is None:
            raise AssertionError("Fault terminals are missing")
        return abs(
            TERMINAL_POSITION_PERCENT[self.terminal_a]
            - TERMINAL_POSITION_PERCENT[self.terminal_b]
        )


@dataclass(frozen=True)
class PmsgMat:
    """Validated time and three phase-current arrays from one PMSG record."""

    path: Path
    label: PmsgLabel
    time: NDArray[np.float64]
    currents: NDArray[np.float64]
    sample_rate_hz: float


@dataclass(frozen=True)
class PmsgWindow:
    segment: str
    segment_window_id: int
    start_sample: int
    stop_sample: int
    start_time_s: float
    stop_time_s: float


def parse_pmsg_filename(path: str | Path) -> PmsgLabel:
    """Parse only the 225-file health/fault filename grammar in the frozen tag."""

    name = Path(path).name
    health = _HEALTH_PATTERN.fullmatch(name)
    if health is not None:
        return PmsgLabel(
            is_healthy=True,
            speed_rpm=int(health.group("speed")),
            torque_setting_code=int(health.group("torque")),
            fault_family=None,
            terminal_a=None,
            terminal_b=None,
            resistance_code=None,
        )
    fault = _FAULT_PATTERN.fullmatch(name)
    if fault is None:
        raise ValueError(f"Unsupported PMSG filename: {name}")
    terminal_a = fault.group("terminal_a")
    terminal_b = fault.group("terminal_b")
    if terminal_a == terminal_b:
        raise ValueError("PMSG fault terminals must differ")
    return PmsgLabel(
        is_healthy=False,
        speed_rpm=int(fault.group("speed")),
        torque_setting_code=int(fault.group("torque")),
        fault_family=fault.group("family").lower(),
        terminal_a=terminal_a,
        terminal_b=terminal_b,
        resistance_code=fault.group("resistance_code"),
    )


def discover_pmsg_files(input_dir: Path) -> list[Path]:
    """Discover exactly 9 healthy and 216 fault MAT records."""

    if not input_dir.is_dir():
        raise FileNotFoundError(f"PMSG input directory not found: {input_dir}")
    parsed: list[tuple[Path, PmsgLabel]] = []
    for path in input_dir.iterdir():
        if not path.is_file() or path.suffix.lower() != ".mat":
            continue
        try:
            label = parse_pmsg_filename(path)
        except ValueError:
            continue
        parsed.append((path, label))
    health_count = sum(label.is_healthy for _, label in parsed)
    fault_count = sum(not label.is_healthy for _, label in parsed)
    if health_count != 9 or fault_count != 216:
        raise ValueError(
            f"Expected 9 healthy and 216 fault MAT files, found {health_count}/{fault_count}"
        )
    parsed.sort(
        key=lambda item: (
            not item[1].is_healthy,
            item[1].fault_family or "",
            item[1].terminal_a or "",
            item[1].terminal_b or "",
            item[1].speed_rpm,
            item[1].torque_setting_code,
        )
    )
    return [path for path, _ in parsed]


def _numeric_vector(variables: Mapping[str, object], name: str) -> NDArray[np.float64]:
    if name not in variables:
        raise ValueError(f"Missing required MAT variable: {name}")
    value = np.asarray(variables[name])
    if value.ndim == 2 and 1 in value.shape:
        value = value.reshape(-1)
    elif value.ndim != 1:
        raise ValueError(f"{name} must be a vector, got {value.shape}")
    if not np.issubdtype(value.dtype, np.number):
        raise ValueError(f"{name} must be numeric")
    result = np.asarray(value, dtype=np.float64)
    if not np.isfinite(result).all():
        raise ValueError(f"{name} contains non-finite values")
    return result


def load_pmsg_mat(path: Path) -> PmsgMat:
    """Load only time and phase currents; relay/fault/control variables stay unread."""

    label = parse_pmsg_filename(path)
    variables = loadmat(
        path,
        variable_names=list(REQUIRED_MAT_VARIABLES),
        squeeze_me=False,
        struct_as_record=False,
        mat_dtype=True,
    )
    time = _numeric_vector(variables, "t")
    phases = [_numeric_vector(variables, name) for name in ("Ia", "Ib", "Ic")]
    lengths = {time.size, *(phase.size for phase in phases)}
    if len(lengths) != 1:
        raise ValueError("PMSG time and three phase currents must have equal lengths")
    if time.size not in ACCEPTED_SAMPLE_COUNTS:
        raise ValueError(
            f"Expected one of {ACCEPTED_SAMPLE_COUNTS} samples, found {time.size}"
        )
    increments = np.diff(time)
    expected_increment = 1.0 / EXPECTED_SAMPLE_RATE_HZ
    if np.any(increments <= 0) or not np.allclose(
        increments,
        expected_increment,
        rtol=0.0,
        atol=expected_increment * 2e-5,
    ):
        raise ValueError("PMSG time is not uniformly sampled at 20 kHz")
    sample_rate_hz = float(1.0 / np.median(increments))
    if not math.isclose(
        sample_rate_hz,
        EXPECTED_SAMPLE_RATE_HZ,
        rel_tol=2e-5,
        abs_tol=0.05,
    ):
        raise ValueError(f"Expected 20 kHz, observed {sample_rate_hz:g} Hz")
    if float(time[0]) > 1e-6 or float(time[-1]) < 2.9999:
        raise ValueError("PMSG record does not cover the frozen three-second schedule")
    return PmsgMat(
        path=path,
        label=label,
        time=time,
        currents=np.column_stack(phases),
        sample_rate_hz=sample_rate_hz,
    )


def standalone_health_role(label: PmsgLabel) -> str:
    """Assign the fixed 4/3/2 healthy-file role on the 3-by-3 condition grid."""

    if not label.is_healthy:
        return "fault_record"
    if label.condition in HEALTH_FIT_CONDITIONS:
        return "fit"
    if label.condition in HEALTH_CALIBRATION_CONDITIONS:
        return "calibration"
    if label.condition in HEALTH_TEST_CONDITIONS:
        return "standalone_health_test"
    raise AssertionError(f"Unassigned healthy PMSG condition: {label.condition}")


def _interval_bounds(record: PmsgMat, interval: tuple[float, float]) -> tuple[int, int]:
    start_seconds, stop_seconds = interval
    start = int(np.searchsorted(record.time, start_seconds, side="left"))
    stop = int(np.searchsorted(record.time, stop_seconds, side="left"))
    if start >= stop or stop > record.time.size:
        raise ValueError(f"PMSG record does not contain frozen interval {interval}")
    tolerance = 0.25 / record.sample_rate_hz
    if not math.isclose(
        float(record.time[start]), start_seconds, rel_tol=0.0, abs_tol=tolerance
    ) or not math.isclose(
        float(record.time[stop]), stop_seconds, rel_tol=0.0, abs_tol=tolerance
    ):
        raise ValueError(f"Frozen PMSG interval {interval} does not align to samples")
    return start, stop


def iter_pmsg_windows(record: PmsgMat) -> Iterator[tuple[PmsgWindow, NDArray[np.float64]]]:
    """Yield the fixed non-overlapping 0.2 s health/fault/recovery windows."""

    segments = (
        ("health_analysis", HEALTH_ANALYSIS_INTERVAL),
    ) if record.label.is_healthy else (
        ("pre_fault", PRE_FAULT_INTERVAL),
        ("fault_active", FAULT_ACTIVE_INTERVAL),
        ("recovery", RECOVERY_INTERVAL),
    )
    window_samples = round(WINDOW_SECONDS * record.sample_rate_hz)
    for segment, interval in segments:
        start, stop = _interval_bounds(record, interval)
        if (stop - start) % window_samples:
            raise ValueError(f"Frozen PMSG {segment} interval is not an integer window count")
        for window_id, window_start in enumerate(range(start, stop, window_samples)):
            window_stop = window_start + window_samples
            index = PmsgWindow(
                segment=segment,
                segment_window_id=window_id,
                start_sample=window_start,
                stop_sample=window_stop,
                start_time_s=float(record.time[window_start]),
                stop_time_s=float(record.time[window_stop]),
            )
            yield index, record.currents[window_start:window_stop]


def extract_pmsg_feature_rows(
    record: PmsgMat,
    *,
    source_sha256: str,
) -> list[dict[str, object]]:
    """Extract only the already-frozen transparent current feature schema."""

    if re.fullmatch(r"[0-9a-f]{64}", source_sha256) is None:
        raise ValueError("source_sha256 must be a lowercase SHA-256 digest")
    label = record.label
    role = standalone_health_role(label)
    rows: list[dict[str, object]] = []
    for window, values in iter_pmsg_windows(record):
        rows.append(
            {
                "source_filename": record.path.name,
                "source_path": str(record.path.resolve()),
                "source_sha256": source_sha256,
                "record_id": record.path.stem.lower(),
                "is_healthy_file": label.is_healthy,
                "standalone_role": role,
                "segment": window.segment,
                "speed_rpm": label.speed_rpm,
                "torque_setting_code": label.torque_setting_code,
                "fault_family": label.fault_family,
                "terminal_a": label.terminal_a,
                "terminal_b": label.terminal_b,
                "resistance_code": label.resistance_code,
                "fault_span_percent": label.fault_span_percent,
                "sample_rate_hz": record.sample_rate_hz,
                "segment_window_id": window.segment_window_id,
                "start_sample": window.start_sample,
                "stop_sample": window.stop_sample,
                "start_time_s": window.start_time_s,
                "stop_time_s": window.stop_time_s,
                **current_features(values, record.sample_rate_hz),
            }
        )
    return rows
