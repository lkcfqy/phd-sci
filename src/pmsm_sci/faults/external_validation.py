"""Frozen health-only helpers for the independent dual-three-phase PMSM test."""

from __future__ import annotations

from collections.abc import Sequence

import numpy as np
import pandas as pd
from numpy.typing import ArrayLike, NDArray

ADAPTATION_LOAD_NM = 0
ADAPTATION_BLOCKS = (0, 1, 2, 3)
CALIBRATION_LOADS_NM = (10, 20, 30)
HEALTH_TEST_LOADS_NM = (5, 15, 25, 35)
ANALYSIS_BLOCKS = tuple(range(8))


def robust_reference_parameters(
    values: ArrayLike,
) -> tuple[NDArray[np.float64], NDArray[np.float64]]:
    """Return the median and guarded MAD scale used by the KAIST pipeline."""

    data = np.asarray(values, dtype=np.float64)
    if data.ndim != 2 or data.shape[0] < 2:
        raise ValueError("values must contain at least two rows")
    if not np.isfinite(data).all():
        raise ValueError("values must contain only finite values")
    center = np.median(data, axis=0)
    mad_scale = 1.4826 * np.median(np.abs(data - center), axis=0)
    standard_scale = np.std(data, axis=0)
    floor = 1e-8 * np.maximum(np.abs(center), 1.0)
    scale = np.where(mad_scale > floor, mad_scale, standard_scale)
    scale = np.where(scale > floor, scale, 1.0)
    return center, scale


def robust_transform(
    values: ArrayLike, center: ArrayLike, scale: ArrayLike
) -> NDArray[np.float64]:
    """Apply a previously fitted coordinate-wise robust transformation."""

    data = np.asarray(values, dtype=np.float64)
    location = np.asarray(center, dtype=np.float64).reshape(-1)
    divisor = np.asarray(scale, dtype=np.float64).reshape(-1)
    if data.ndim != 2 or data.shape[1] != location.size:
        raise ValueError("values and center dimensions are inconsistent")
    if divisor.size != location.size or np.any(divisor <= 0):
        raise ValueError("scale must be positive and dimensionally consistent")
    result = (data - location) / divisor
    if not np.isfinite(result).all():
        raise FloatingPointError("robust transformation produced non-finite values")
    return result


def external_health_role(frame: pd.DataFrame) -> pd.Series:
    """Assign the predeclared role of each external healthy feature window."""

    required = {"load_nm", "block_id", "is_healthy"}
    missing = required.difference(frame.columns)
    if missing:
        raise ValueError(f"frame is missing required columns: {sorted(missing)}")
    if not frame["is_healthy"].astype(bool).all():
        raise ValueError("Health-role assignment must not receive fault rows")
    load = frame["load_nm"].astype(int)
    block = frame["block_id"].astype(int)
    role = pd.Series("unused", index=frame.index, dtype="object")
    role.loc[
        load.eq(ADAPTATION_LOAD_NM) & block.isin(ADAPTATION_BLOCKS)
    ] = "adaptation"
    role.loc[
        load.isin(CALIBRATION_LOADS_NM) & block.isin(ANALYSIS_BLOCKS)
    ] = "calibration"
    role.loc[
        load.isin(HEALTH_TEST_LOADS_NM) & block.isin(ANALYSIS_BLOCKS)
    ] = "health_test"
    return role


def system_block_scores(
    frame: pd.DataFrame,
    scores: ArrayLike,
    *,
    expected_subsystems: Sequence[object] = ("SubSys1", "SubSys2"),
    expected_windows_per_block: int = 15,
) -> pd.DataFrame:
    """Aggregate window scores to subsystem maxima and then a system maximum."""

    required = {"record_id", "load_nm", "subsystem", "block_id"}
    missing = required.difference(frame.columns)
    if missing:
        raise ValueError(f"frame is missing required columns: {sorted(missing)}")
    values = np.asarray(scores, dtype=np.float64).reshape(-1)
    if len(frame) != values.size or not np.isfinite(values).all():
        raise ValueError("scores must be finite and aligned with frame")
    working = frame[list(required)].copy()
    working["score"] = values
    subsystem = (
        working.groupby(
            ["record_id", "load_nm", "subsystem", "block_id"],
            observed=True,
            sort=True,
        )
        .agg(window_count=("score", "size"), subsystem_score=("score", "max"))
        .reset_index()
    )
    if not subsystem["window_count"].eq(expected_windows_per_block).all():
        raise ValueError("A subsystem block has an unexpected number of windows")
    expected = tuple(sorted(str(item) for item in expected_subsystems))
    observed = (
        subsystem.groupby(["record_id", "load_nm", "block_id"], sort=True)[
            "subsystem"
        ]
        .agg(lambda items: tuple(sorted(str(item) for item in items)))
    )
    if not observed.map(lambda items: items == expected).all():
        raise ValueError("Each system block must contain every expected subsystem")
    component_scores = subsystem.pivot(
        index=["record_id", "load_nm", "block_id"],
        columns="subsystem",
        values="subsystem_score",
    ).reset_index()
    component_scores.columns.name = None
    component_scores = component_scores.rename(
        columns={item: f"subsystem_score_{item}" for item in expected}
    )
    system = (
        subsystem.groupby(
            ["record_id", "load_nm", "block_id"], observed=True, sort=True
        )
        .agg(
            subsystem_count=("subsystem", "size"),
            score=("subsystem_score", "max"),
        )
        .reset_index()
    )
    return system.merge(
        component_scores,
        on=["record_id", "load_nm", "block_id"],
        validate="one_to_one",
    )
