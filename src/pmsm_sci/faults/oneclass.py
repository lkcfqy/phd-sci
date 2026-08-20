"""One-class anomaly baselines for healthy-only cross-machine evaluation."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

import numpy as np
import pandas as pd
from numpy.typing import ArrayLike, NDArray
from scipy.linalg import qr
from sklearn.covariance import MinCovDet
from sklearn.ensemble import IsolationForest
from sklearn.svm import OneClassSVM

TrainingScope = Literal["target", "source_target_balanced"]
EstimatorKind = Literal["ocsvm", "isolation_forest", "min_cov_det"]


@dataclass(frozen=True)
class OneClassSpec:
    """A fixed one-class model specification with no fault-tuned parameters."""

    name: str
    estimator_kind: EstimatorKind
    training_scope: TrainingScope
    stochastic: bool


METHOD_SPECS = (
    OneClassSpec("target_ocsvm_rbf", "ocsvm", "target", False),
    OneClassSpec(
        "source_target_ocsvm_rbf", "ocsvm", "source_target_balanced", False
    ),
    OneClassSpec(
        "target_isolation_forest", "isolation_forest", "target", True
    ),
    OneClassSpec(
        "source_target_isolation_forest",
        "isolation_forest",
        "source_target_balanced",
        True,
    ),
    OneClassSpec("target_min_cov_det", "min_cov_det", "target", True),
    OneClassSpec(
        "source_target_min_cov_det",
        "min_cov_det",
        "source_target_balanced",
        True,
    ),
)


def build_oneclass_estimator(
    estimator_kind: EstimatorKind,
    *,
    seed: int,
    isolation_trees: int = 500,
):
    """Build a fixed, commonly used one-class estimator.

    The anomaly threshold is deliberately not taken from any estimator's
    ``contamination`` or ``nu`` setting. It is set later using disjoint target
    healthy calibration blocks.
    """

    if estimator_kind == "ocsvm":
        return OneClassSVM(kernel="rbf", gamma="scale", nu=0.05)
    if estimator_kind == "isolation_forest":
        return IsolationForest(
            n_estimators=isolation_trees,
            max_samples="auto",
            contamination="auto",
            max_features=1.0,
            bootstrap=False,
            n_jobs=-1,
            random_state=seed,
        )
    if estimator_kind == "min_cov_det":
        return MinCovDet(
            assume_centered=True,
            support_fraction=None,
            random_state=seed,
        )
    raise ValueError(f"Unknown estimator kind: {estimator_kind}")


def oneclass_anomaly_scores(
    estimator, estimator_kind: EstimatorKind, values: ArrayLike
) -> NDArray[np.float64]:
    """Return scores oriented so that larger values are more anomalous."""

    data = np.asarray(values, dtype=np.float64)
    if data.ndim != 2 or data.shape[0] == 0:
        raise ValueError("values must be a non-empty two-dimensional array")
    if estimator_kind == "ocsvm":
        scores = -np.asarray(estimator.decision_function(data), dtype=np.float64)
    elif estimator_kind == "isolation_forest":
        scores = -np.asarray(estimator.score_samples(data), dtype=np.float64)
    elif estimator_kind == "min_cov_det":
        scores = np.asarray(estimator.mahalanobis(data), dtype=np.float64)
    else:
        raise ValueError(f"Unknown estimator kind: {estimator_kind}")
    scores = scores.reshape(-1)
    if not np.isfinite(scores).all():
        raise FloatingPointError("The one-class estimator produced non-finite scores")
    return scores


def independent_training_columns(values: ArrayLike) -> NDArray[np.int64]:
    """Choose a full-rank feature subset using only healthy training values.

    MinCovDet requires a nonsingular feature geometry. The scale-free feature
    arm contains one invariant frequency column and an exact linear relation
    among the three RMS ratios on this dataset. Rank-revealing QR removes such
    numerical redundancies without inspecting calibration or fault rows.
    """

    data = np.asarray(values, dtype=np.float64)
    if data.ndim != 2 or data.shape[0] < 2:
        raise ValueError("values must contain at least two rows")
    centered = data - data.mean(axis=0, keepdims=True)
    _, triangular, pivot = qr(centered, mode="economic", pivoting=True)
    diagonal = np.abs(np.diag(triangular))
    if diagonal.size == 0 or diagonal[0] == 0:
        raise ValueError("Training data has no varying feature")
    # ``sqrt(eps)`` treats algebraic identities perturbed only by feature-file
    # rounding as redundant, while retaining the smallest genuinely varying
    # direction in these healthy references by several orders of magnitude.
    tolerance = np.sqrt(np.finfo(float).eps) * diagonal[0]
    rank = int((diagonal > tolerance).sum())
    if rank == 0:
        raise ValueError("Training data has no numerically independent feature")
    return np.sort(np.asarray(pivot[:rank], dtype=np.int64))


def motor_balanced_reference_mask(
    frame: pd.DataFrame,
    reference_blocks: dict[str, list[int]],
) -> NDArray[np.bool_]:
    """Select the same number of complete healthy blocks from each motor.

    The target motor has only four adaptation blocks. Source motors therefore
    contribute four evenly spaced complete blocks from their 24 allowed
    reference blocks. Selection depends only on motor, health, and time index.
    """

    required = {"motor_id", "is_healthy", "block_id"}
    missing = required.difference(frame.columns)
    if missing:
        raise ValueError(f"frame is missing required columns: {sorted(missing)}")
    available_by_motor: dict[str, NDArray[np.int64]] = {}
    for motor, allowed_blocks in reference_blocks.items():
        allowed = (
            frame["motor_id"].eq(motor)
            & frame["is_healthy"].astype(bool)
            & frame["block_id"].isin(allowed_blocks)
        )
        blocks = np.sort(frame.loc[allowed, "block_id"].astype(int).unique())
        if blocks.size == 0:
            raise ValueError(f"No allowed healthy reference blocks for {motor}")
        available_by_motor[motor] = blocks

    common_blocks = min(blocks.size for blocks in available_by_motor.values())
    selected = np.zeros(len(frame), dtype=bool)
    for motor, blocks in available_by_motor.items():
        positions = np.rint(np.linspace(0, blocks.size - 1, common_blocks)).astype(int)
        chosen = blocks[positions]
        selected |= (
            frame["motor_id"].eq(motor)
            & frame["is_healthy"].astype(bool)
            & frame["block_id"].isin(chosen)
        ).to_numpy()
    return selected


def stratified_record_bootstrap_interval(
    records: pd.DataFrame,
    *,
    value_column: str,
    strata_column: str = "motor_id",
    iterations: int = 10_000,
    seed: int = 711,
) -> tuple[float, float]:
    """Percentile CI from a motor-stratified bootstrap of whole fault records.

    This resamples records, never their dependent blocks. The interval is
    conditional on the three observed motor capacities and is not a population
    guarantee for unseen motor designs.
    """

    if iterations < 100:
        raise ValueError("iterations must be at least 100")
    if value_column not in records or strata_column not in records:
        raise ValueError("records does not contain the requested columns")
    groups = [
        group[value_column].to_numpy(dtype=np.float64)
        for _, group in records.groupby(strata_column, sort=True)
    ]
    if not groups or any(group.size == 0 for group in groups):
        raise ValueError("Each bootstrap stratum must contain at least one record")
    if any(not np.isfinite(group).all() for group in groups):
        raise ValueError("Bootstrap values must be finite")

    rng = np.random.default_rng(seed)
    draws = np.empty(iterations, dtype=np.float64)
    for index in range(iterations):
        sampled = [rng.choice(group, size=group.size, replace=True) for group in groups]
        draws[index] = np.concatenate(sampled).mean()
    lower, upper = np.quantile(draws, [0.025, 0.975])
    return float(lower), float(upper)
