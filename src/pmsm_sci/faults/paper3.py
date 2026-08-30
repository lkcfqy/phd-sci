"""Frozen feature and context definitions for Paper 3."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

import numpy as np
import pandas as pd
from numpy.typing import ArrayLike, NDArray

PAPER3_CONTEXT_FEATURES = ("commanded_speed_rpm", "load_nm")

# Absolute current scale is deliberately excluded so the same outcome arm can
# transfer from the development PMSM to a differently rated confirmation PMSG.
# ``fundamental_hz`` is also excluded: speed is supplied separately as exogenous
# context rather than allowing the response vector to be dominated by the ramp.
PAPER3_OUTCOME_FEATURES = (
    "sequence_unbalance",
    "fundamental_amplitude_cv",
    "phase_rms_cv",
    "clarke_radius_cv",
    "zero_sequence_ratio",
    "spectral_entropy",
    "sideband_lower_ratio",
    "sideband_upper_ratio",
    "harmonic_2_ratio_mean",
    "harmonic_2_ratio_max",
    "harmonic_3_ratio_mean",
    "harmonic_3_ratio_max",
    "harmonic_4_ratio_mean",
    "harmonic_4_ratio_max",
    "harmonic_5_ratio_mean",
    "harmonic_5_ratio_max",
    "thd_2_to_5_mean",
    "rms_ratio_a",
    "crest_a",
    "kurtosis_a",
    "rms_ratio_b",
    "crest_b",
    "kurtosis_b",
    "rms_ratio_c",
    "crest_c",
    "kurtosis_c",
)

PAPER3_LOADS_NM = (0.0, 5.0, 10.0, 15.0, 20.0, 25.0, 30.0, 35.0)
PAPER3_FIT_LOADS_NM = {
    0.0: (5.0, 15.0, 25.0, 35.0),
    5.0: (0.0, 10.0, 20.0, 35.0),
    10.0: (0.0, 5.0, 15.0, 35.0),
    15.0: (0.0, 10.0, 20.0, 35.0),
    20.0: (0.0, 15.0, 25.0, 35.0),
    25.0: (0.0, 20.0, 30.0, 35.0),
    30.0: (0.0, 15.0, 25.0, 35.0),
    35.0: (0.0, 10.0, 20.0, 30.0),
}

MethodFamily = Literal["conditional", "isolation_forest", "min_cov_det"]


@dataclass(frozen=True)
class Paper3MethodSpec:
    """Development candidate fixed before the independent-bench reveal."""

    name: str
    family: MethodFamily
    mean_model: str | None = None
    local_scale: bool = False


PAPER3_METHODS = (
    Paper3MethodSpec("unconditioned_residual", "conditional", "constant", False),
    Paper3MethodSpec("linear_residual", "conditional", "linear", False),
    Paper3MethodSpec("quadratic_residual", "conditional", "quadratic", False),
    Paper3MethodSpec("spline_residual", "conditional", "spline", False),
    Paper3MethodSpec("spline_local_scale", "conditional", "spline", True),
    Paper3MethodSpec("isolation_forest", "isolation_forest"),
    Paper3MethodSpec("min_cov_det", "min_cov_det"),
)


def paper3_load_roles(test_load_nm: float) -> dict[float, str]:
    """Return geometry-valid fit/calibration/test roles independent of faults."""

    if test_load_nm not in PAPER3_LOADS_NM:
        raise ValueError(f"Unknown Paper 3 load: {test_load_nm:g} Nm")
    fit = set(PAPER3_FIT_LOADS_NM[test_load_nm])
    roles = {
        load: (
            "test"
            if load == test_load_nm
            else "fit"
            if load in fit
            else "calibration"
        )
        for load in PAPER3_LOADS_NM
    }
    if list(roles.values()).count("fit") != 4 or list(roles.values()).count(
        "calibration"
    ) != 3:
        raise AssertionError("Each Paper 3 fold must have 4 fit, 3 calibration, 1 test load")
    fit_values = np.asarray(sorted(fit), dtype=np.float64)
    calibration_values = np.asarray(
        [load for load, role in roles.items() if role == "calibration"], dtype=np.float64
    )
    if np.any(calibration_values < fit_values.min()) or np.any(
        calibration_values > fit_values.max()
    ):
        raise AssertionError("Every calibration load must be inside the fit load range")
    if 0.0 < test_load_nm < 35.0 and not (
        np.any(fit_values < test_load_nm) and np.any(fit_values > test_load_nm)
    ):
        raise AssertionError("Every primary test load must be bracketed by fit loads")
    return roles


def aggregate_paper3_system_blocks(
    frame: pd.DataFrame,
    scores: ArrayLike,
    supported: ArrayLike,
) -> pd.DataFrame:
    """Max windows then subsystems; require all window contexts to be supported."""

    required = {
        "record_id",
        "load_nm",
        "fault_turns",
        "fault_phase",
        "is_healthy",
        "subsystem",
        "block_id",
    }
    missing = required.difference(frame.columns)
    if missing:
        raise ValueError(f"frame is missing required columns: {sorted(missing)}")
    score_values = np.asarray(scores, dtype=np.float64).reshape(-1)
    support_values = np.asarray(supported, dtype=bool).reshape(-1)
    if len(frame) != score_values.size or len(frame) != support_values.size:
        raise ValueError("frame, scores, and supported must have equal lengths")
    if not np.isfinite(score_values).all():
        raise ValueError("scores must be finite")
    working = frame[list(required)].copy()
    working["window_score"] = score_values
    working["window_supported"] = support_values
    subsystem = (
        working.groupby(
            [
                "record_id",
                "load_nm",
                "fault_turns",
                "fault_phase",
                "is_healthy",
                "subsystem",
                "block_id",
            ],
            observed=True,
            dropna=False,
            sort=True,
        )
        .agg(
            window_count=("window_score", "size"),
            subsystem_score=("window_score", "max"),
            subsystem_supported=("window_supported", "all"),
        )
        .reset_index()
    )
    if not subsystem["window_count"].eq(15).all():
        raise ValueError("Each record/subsystem block must contain exactly 15 windows")
    system = (
        subsystem.groupby(
            [
                "record_id",
                "load_nm",
                "fault_turns",
                "fault_phase",
                "is_healthy",
                "block_id",
            ],
            observed=True,
            dropna=False,
            sort=True,
        )
        .agg(
            subsystem_count=("subsystem", "size"),
            score=("subsystem_score", "max"),
            supported=("subsystem_supported", "all"),
        )
        .reset_index()
    )
    if not system["subsystem_count"].eq(2).all():
        raise ValueError("Each system block must contain exactly two subsystems")
    return system


def array_columns(
    frame: pd.DataFrame, columns: tuple[str, ...]
) -> NDArray[np.float64]:
    """Extract a finite frozen feature matrix with an exact ordered schema."""

    missing = set(columns).difference(frame.columns)
    if missing:
        raise ValueError(f"frame lacks frozen columns: {sorted(missing)}")
    values = frame.loc[:, list(columns)].to_numpy(dtype=np.float64)
    if not np.isfinite(values).all():
        raise ValueError("Frozen Paper 3 features must be finite")
    return values
