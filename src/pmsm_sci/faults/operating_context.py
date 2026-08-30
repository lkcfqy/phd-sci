"""Exogenous operating-context extraction for the Paper 3 development bench."""

from __future__ import annotations

import math
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pandas as pd
from numpy.typing import NDArray
from scipy.io import loadmat

from pmsm_sci.faults.external_pmsm import (
    EXPECTED_SAMPLE_RATE_HZ,
    EXPECTED_SAMPLES,
    file_sha256,
    parse_external_pmsm_filename,
)

OPERATING_CONTEXT_VARIABLES = ("Time", "Speed_requred_rpm")


@dataclass(frozen=True)
class ExternalOperatingContext:
    """Time-aligned commanded speed from one accepted development MAT file."""

    path: Path
    time: NDArray[np.float64]
    commanded_speed_rpm: NDArray[np.float32]
    sample_rate_hz: float


def _strict_column(
    variables: dict[str, object], name: str, dtype: np.dtype
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


def load_external_operating_context(
    path: Path,
    *,
    expected_samples: int = EXPECTED_SAMPLES,
    expected_sample_rate_hz: float = EXPECTED_SAMPLE_RATE_HZ,
) -> ExternalOperatingContext:
    """Deserialize only time and fault-independent commanded speed."""

    parse_external_pmsm_filename(path)
    variables = loadmat(
        path,
        variable_names=list(OPERATING_CONTEXT_VARIABLES),
        squeeze_me=False,
        struct_as_record=False,
        mat_dtype=True,
    )
    time = _strict_column(variables, "Time", np.dtype(np.float64))
    speed = _strict_column(variables, "Speed_requred_rpm", np.dtype(np.float32))
    if time.size != expected_samples or speed.size != expected_samples:
        raise ValueError(
            f"Expected {expected_samples} aligned samples, found time={time.size}, "
            f"speed={speed.size}"
        )
    increments = np.diff(time)
    expected_increment = 1.0 / expected_sample_rate_hz
    if np.any(increments <= 0) or not np.allclose(
        increments,
        expected_increment,
        rtol=0.0,
        atol=expected_increment * 1e-6,
    ):
        raise ValueError("Time is not strictly and uniformly sampled at the expected rate")
    sample_rate_hz = float(1.0 / np.median(increments))
    if not math.isclose(
        sample_rate_hz,
        expected_sample_rate_hz,
        rel_tol=1e-9,
        abs_tol=1e-6,
    ):
        raise ValueError("Observed operating-context sample rate is unexpected")
    return ExternalOperatingContext(
        path=path,
        time=time,
        commanded_speed_rpm=speed,
        sample_rate_hz=sample_rate_hz,
    )


def attach_external_operating_context(
    frame: pd.DataFrame,
    input_dir: Path,
    *,
    verify_hashes: bool = True,
) -> pd.DataFrame:
    """Attach window-mean commanded speed with sample/time/hash alignment checks."""

    required = {
        "source_filename",
        "source_sha256",
        "load_nm",
        "start_sample",
        "stop_sample",
        "start_time_s",
        "stop_time_s",
    }
    missing = required.difference(frame.columns)
    if missing:
        raise ValueError(f"frame is missing required columns: {sorted(missing)}")
    if not input_dir.is_dir():
        raise FileNotFoundError(f"Operating-context input directory not found: {input_dir}")
    if frame.empty:
        raise ValueError("frame must not be empty")

    output = frame.copy()
    output["commanded_speed_rpm"] = np.nan
    for filename, file_rows in output.groupby("source_filename", sort=True):
        path = input_dir / str(filename)
        if not path.is_file():
            raise FileNotFoundError(f"Source MAT file not found: {path}")
        digests = file_rows["source_sha256"].astype(str).unique()
        if len(digests) != 1:
            raise ValueError(f"Feature rows disagree on source hash for {filename}")
        if verify_hashes and file_sha256(path) != digests[0]:
            raise ValueError(f"Source hash mismatch for {filename}")
        context = load_external_operating_context(path)

        unique_windows = file_rows[
            ["start_sample", "stop_sample", "start_time_s", "stop_time_s"]
        ].drop_duplicates()
        window_means: dict[tuple[int, int], float] = {}
        tolerance = 0.25 / context.sample_rate_hz
        for row in unique_windows.itertuples(index=False):
            start = int(row.start_sample)
            stop = int(row.stop_sample)
            if not (0 <= start < stop <= context.time.size):
                raise ValueError(f"Invalid window sample bounds in {filename}: {start}:{stop}")
            if not math.isclose(
                float(context.time[start]),
                float(row.start_time_s),
                rel_tol=0.0,
                abs_tol=tolerance,
            ) or not math.isclose(
                float(context.time[stop]),
                float(row.stop_time_s),
                rel_tol=0.0,
                abs_tol=tolerance,
            ):
                raise ValueError(f"Feature/context time alignment failed for {filename}")
            window_means[(start, stop)] = float(
                np.mean(context.commanded_speed_rpm[start:stop], dtype=np.float64)
            )

        indices = file_rows.index
        keys = zip(
            output.loc[indices, "start_sample"].astype(int),
            output.loc[indices, "stop_sample"].astype(int),
            strict=True,
        )
        output.loc[indices, "commanded_speed_rpm"] = [window_means[key] for key in keys]

    if not np.isfinite(output["commanded_speed_rpm"].to_numpy(dtype=np.float64)).all():
        raise AssertionError("Some development windows lack finite operating context")
    return output
