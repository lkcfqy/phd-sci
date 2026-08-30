"""Transparent response-surface baselines for Fourier-reduced torque curves."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import numpy as np
from sklearn.ensemble import ExtraTreesRegressor
from sklearn.gaussian_process import GaussianProcessRegressor
from sklearn.gaussian_process.kernels import RBF, ConstantKernel
from sklearn.kernel_ridge import KernelRidge
from sklearn.linear_model import Ridge
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import PolynomialFeatures, StandardScaler

from .fourier import decode_torque, encode_torque


def build_regressor(name: str, *, seed: int, parameters: dict[str, float] | None = None) -> Any:
    """Build a deterministic multi-output response surface."""

    settings = parameters or {}
    if name == "poly2_ridge":
        return make_pipeline(
            StandardScaler(),
            PolynomialFeatures(degree=2, include_bias=False),
            Ridge(alpha=float(settings.get("alpha", 1e-5))),
        )
    if name == "rbf_kernel_ridge":
        return KernelRidge(
            alpha=float(settings.get("alpha", 1e-4)),
            gamma=float(settings.get("gamma", 0.05)),
            kernel="rbf",
        )
    if name == "ard_gaussian_process":
        dimensions = int(settings.get("dimensions", 20))
        upper = float(settings.get("length_scale_upper", 10.0))
        kernel = ConstantKernel(1.0, constant_value_bounds=(1e-2, 1e2)) * RBF(
            length_scale=np.ones(dimensions),
            length_scale_bounds=(0.03, upper),
        )
        return GaussianProcessRegressor(
            kernel=kernel,
            alpha=1e-8,
            normalize_y=True,
            n_restarts_optimizer=0,
            random_state=seed,
        )
    if name == "extra_trees":
        return ExtraTreesRegressor(
            n_estimators=int(settings.get("n_estimators", 300)),
            min_samples_leaf=int(settings.get("min_samples_leaf", 1)),
            max_features=float(settings.get("max_features", 1.0)),
            n_jobs=-1,
            random_state=seed,
        )
    raise ValueError(f"Unknown torque regressor: {name}")


@dataclass
class FourierSurrogate:
    """Wrap a vector regressor with fixed Fourier encoding and reconstruction."""

    regressor: Any
    n_angles: int = 120
    retained_components: int = 11

    def fit(self, parameters: np.ndarray, torque: np.ndarray) -> FourierSurrogate:
        x = np.asarray(parameters, dtype=float)
        y = np.asarray(torque, dtype=float)
        self.regressor.fit(x, encode_torque(y, self.retained_components))
        return self

    def predict(self, parameters: np.ndarray) -> np.ndarray:
        coordinates = self.regressor.predict(np.asarray(parameters, dtype=float))
        return decode_torque(
            coordinates,
            n_angles=self.n_angles,
            retained_components=self.retained_components,
        )
