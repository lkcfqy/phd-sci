"""Transparent first-pass regression baselines."""

from __future__ import annotations

from sklearn.dummy import DummyRegressor
from sklearn.ensemble import HistGradientBoostingRegressor
from sklearn.linear_model import Ridge
from sklearn.multioutput import MultiOutputRegressor
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler


def build_model(name: str, seed: int):
    """Construct a deterministic multi-target baseline."""

    if name == "dummy":
        return MultiOutputRegressor(DummyRegressor(strategy="median"))
    if name == "ridge":
        return make_pipeline(StandardScaler(), Ridge(alpha=1.0))
    if name == "hist_gbr":
        base = HistGradientBoostingRegressor(
            learning_rate=0.08,
            max_iter=200,
            max_leaf_nodes=31,
            l2_regularization=1e-4,
            random_state=seed,
        )
        return MultiOutputRegressor(base, n_jobs=-1)
    raise ValueError(f"Unknown model: {name}")
