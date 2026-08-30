"""Frozen data roles for the PMSM torque-curve benchmark."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np


@dataclass(frozen=True)
class TorqueSplit:
    """Disjoint fit, calibration, and internal-test row indices."""

    fit: np.ndarray
    calibration: np.ndarray
    internal_test: np.ndarray


def make_primary_split(
    *,
    total_rows: int = 2000,
    development_rows: int = 1800,
    fit_rows: int = 1200,
    seed: int = 20260821,
) -> TorqueSplit:
    """Preserve the published final 200 rows and split the 1800-row development pool."""

    if not 0 < fit_rows < development_rows < total_rows:
        raise ValueError("require 0 < fit_rows < development_rows < total_rows")
    generator = np.random.default_rng(seed)
    shuffled = generator.permutation(development_rows)
    fit = np.sort(shuffled[:fit_rows])
    calibration = np.sort(shuffled[fit_rows:])
    internal_test = np.arange(development_rows, total_rows, dtype=int)
    return TorqueSplit(fit=fit, calibration=calibration, internal_test=internal_test)
