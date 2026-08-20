"""Metrics that expose average and worst-profile behavior."""

from __future__ import annotations

import numpy as np
import pandas as pd
from sklearn.metrics import mean_absolute_error, r2_score


def regression_metrics(
    y_true: np.ndarray,
    y_pred: np.ndarray,
    targets: list[str],
) -> dict[str, dict[str, float]]:
    """Compute per-target and macro regression metrics."""

    result: dict[str, dict[str, float]] = {}
    for index, target in enumerate(targets):
        error = y_pred[:, index] - y_true[:, index]
        result[target] = {
            "mae": float(mean_absolute_error(y_true[:, index], y_pred[:, index])),
            "rmse": float(np.sqrt(np.mean(np.square(error)))),
            "r2": float(r2_score(y_true[:, index], y_pred[:, index])),
        }
    result["macro"] = {
        metric: float(np.mean([result[target][metric] for target in targets]))
        for metric in ("mae", "rmse", "r2")
    }
    return result


def per_profile_rmse(
    y_true: np.ndarray,
    y_pred: np.ndarray,
    groups: pd.Series,
    targets: list[str],
) -> pd.DataFrame:
    """Return target-wise RMSE for every held-out profile."""

    rows: list[dict[str, float | int]] = []
    group_array = groups.to_numpy()
    for profile in sorted(np.unique(group_array)):
        mask = group_array == profile
        row: dict[str, float | int] = {"profile_id": int(profile), "n_rows": int(mask.sum())}
        for index, target in enumerate(targets):
            error = y_pred[mask, index] - y_true[mask, index]
            row[f"rmse_{target}"] = float(np.sqrt(np.mean(np.square(error))))
        row["rmse_macro"] = float(
            np.mean([row[f"rmse_{target}"] for target in targets])
        )
        rows.append(row)
    return pd.DataFrame(rows).sort_values("rmse_macro", ascending=False).reset_index(drop=True)
