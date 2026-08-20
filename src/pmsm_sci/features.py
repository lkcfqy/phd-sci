"""Causal, physics-inspired feature construction."""

from __future__ import annotations

import numpy as np
import pandas as pd

from .constants import BASE_FEATURES, PHYSICS_FEATURES


def add_physics_features(frame: pd.DataFrame) -> pd.DataFrame:
    """Add transparent proxies derived only from currently available inputs."""

    result = frame.copy()
    current_sq = result["i_d"].pow(2) + result["i_q"].pow(2)
    voltage_sq = result["u_d"].pow(2) + result["u_q"].pow(2)
    result["current_magnitude"] = np.sqrt(current_sq)
    result["voltage_magnitude"] = np.sqrt(voltage_sq)
    result["copper_loss_proxy"] = current_sq
    result["electrical_power_proxy"] = (
        result["u_d"] * result["i_d"] + result["u_q"] * result["i_q"]
    ).abs()
    result["mechanical_power_proxy"] = (result["torque"] * result["motor_speed"]).abs()
    return result


def feature_columns(use_physics_features: bool) -> list[str]:
    """Return the auditable feature list for an experiment arm."""

    return BASE_FEATURES + (PHYSICS_FEATURES if use_physics_features else [])
