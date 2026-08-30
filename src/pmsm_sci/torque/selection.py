"""Source-only hyperparameter selection for torque response surfaces."""

from __future__ import annotations

from collections.abc import Iterable

import numpy as np
from sklearn.model_selection import KFold

from .models import FourierSurrogate, build_regressor


def candidate_grid(name: str) -> list[dict[str, float]]:
    """Return the frozen, compact candidate grid for a response surface."""

    if name == "poly2_ridge":
        return [{"alpha": value} for value in (1e-7, 1e-5, 1e-3, 1e-1)]
    if name == "rbf_kernel_ridge":
        return [
            {"alpha": alpha, "gamma": gamma}
            for gamma in (0.025, 0.05, 0.1, 0.2)
            for alpha in (1e-6, 1e-4, 1e-2)
        ]
    if name == "ard_gaussian_process":
        return [{"dimensions": 20.0, "length_scale_upper": 10.0}]
    if name == "extra_trees":
        return [
            {"n_estimators": 300.0, "min_samples_leaf": leaf, "max_features": 1.0}
            for leaf in (1.0, 2.0, 4.0)
        ]
    raise ValueError(f"Unknown torque regressor: {name}")


def select_hyperparameters(
    name: str,
    parameters: np.ndarray,
    torque: np.ndarray,
    *,
    seed: int,
    retained_components: int = 11,
    candidates: Iterable[dict[str, float]] | None = None,
) -> tuple[dict[str, float], list[dict[str, float | int | str]]]:
    """Select settings by three-fold waveform MAE without calibration or target data."""

    x = np.asarray(parameters, dtype=float)
    y = np.asarray(torque, dtype=float)
    if x.ndim != 2 or y.ndim != 2 or len(x) != len(y):
        raise ValueError("parameters and torque must be aligned two-dimensional arrays")
    grid = list(candidates) if candidates is not None else candidate_grid(name)
    if not grid:
        raise ValueError("at least one candidate is required")
    if name == "ard_gaussian_process":
        if len(grid) != 1:
            raise ValueError("ARD Gaussian process uses one fit-only kernel specification")
        settings = grid[0]
        return settings, [
            {
                "model": name,
                "candidate_id": 0,
                "parameters": repr(settings),
                "cv_waveform_mae": float("nan"),
                "cv_mean_curve_max_error": float("nan"),
                "selection_basis": "fit-only log marginal likelihood",
                "selected": 1,
            }
        ]

    rows: list[dict[str, float | int | str]] = []
    folds = KFold(n_splits=3, shuffle=True, random_state=seed)
    for candidate_id, settings in enumerate(grid):
        fold_mae: list[float] = []
        fold_curve_max: list[float] = []
        for fold_id, (train, validation) in enumerate(folds.split(x)):
            model = FourierSurrogate(
                build_regressor(name, seed=seed + fold_id, parameters=settings),
                n_angles=y.shape[1],
                retained_components=retained_components,
            ).fit(x[train], y[train])
            prediction = model.predict(x[validation])
            absolute_error = np.abs(y[validation] - prediction)
            fold_mae.append(float(np.mean(absolute_error)))
            fold_curve_max.append(float(np.mean(np.max(absolute_error, axis=1))))
        rows.append(
            {
                "model": name,
                "candidate_id": candidate_id,
                "parameters": repr(settings),
                "cv_waveform_mae": float(np.mean(fold_mae)),
                "cv_mean_curve_max_error": float(np.mean(fold_curve_max)),
            }
        )

    best_row = min(rows, key=lambda row: (row["cv_waveform_mae"], row["candidate_id"]))
    best = grid[int(best_row["candidate_id"])]
    for row in rows:
        row["selected"] = int(row["candidate_id"] == best_row["candidate_id"])
    return best, rows
