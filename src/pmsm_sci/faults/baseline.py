"""Leakage-resistant feature baselines for cross-machine fault detection."""

from __future__ import annotations

from collections.abc import Sequence

import numpy as np
import pandas as pd
from sklearn.ensemble import HistGradientBoostingClassifier, RandomForestClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler

METADATA_COLUMNS = {
    "member_path",
    "filename",
    "motor_watts",
    "severity_percent",
    "modality",
    "fault_family",
    "motor_id",
    "is_healthy",
    "record_id",
    "block_id",
    "window_id",
    "start_sample",
    "stop_sample",
}

ABSOLUTE_SCALE_COLUMNS = {
    "clarke_radius_mean",
    "fundamental_amplitude_mean",
    "zero_sequence_rms",
    "rms_a",
    "rms_b",
    "rms_c",
}


def feature_columns(frame: pd.DataFrame, arm: str) -> list[str]:
    """Select numeric signal features while explicitly excluding label metadata."""

    numeric = [
        column
        for column in frame.select_dtypes(include=[np.number]).columns
        if column not in METADATA_COLUMNS
    ]
    if arm in {"all_features", "healthy_relative"}:
        selected = numeric
    elif arm == "scale_free":
        selected = [column for column in numeric if column not in ABSOLUTE_SCALE_COLUMNS]
    else:
        raise ValueError(f"Unknown feature arm: {arm}")
    if not selected:
        raise ValueError("No model features were selected")
    return selected


def healthy_relative_features(
    frame: pd.DataFrame,
    columns: Sequence[str],
    reference_blocks: dict[str, Sequence[int]],
) -> tuple[np.ndarray, dict[str, dict[str, list[float]]]]:
    """Center each motor on its allowed healthy blocks and apply robust scaling."""

    transformed = np.empty((len(frame), len(columns)), dtype=np.float64)
    parameters: dict[str, dict[str, list[float]]] = {}
    assigned = np.zeros(len(frame), dtype=bool)
    for motor_id, blocks in reference_blocks.items():
        motor = frame["motor_id"].eq(motor_id).to_numpy()
        reference = (
            motor
            & frame["is_healthy"].astype(bool).to_numpy()
            & frame["block_id"].isin(blocks).to_numpy()
        )
        if not reference.any():
            raise ValueError(f"No healthy reference windows for {motor_id}")
        values = frame.loc[reference, columns].to_numpy(dtype=np.float64)
        center = np.median(values, axis=0)
        mad_scale = 1.4826 * np.median(np.abs(values - center), axis=0)
        standard_scale = np.std(values, axis=0)
        floor = 1e-8 * np.maximum(np.abs(center), 1.0)
        scale = np.where(mad_scale > floor, mad_scale, standard_scale)
        scale = np.where(scale > floor, scale, 1.0)
        transformed[motor] = (
            frame.loc[motor, columns].to_numpy(dtype=np.float64) - center
        ) / scale
        assigned |= motor
        parameters[motor_id] = {
            "center": center.tolist(),
            "scale": scale.tolist(),
        }
    if not assigned.all():
        missing = sorted(frame.loc[~assigned, "motor_id"].unique())
        raise ValueError(f"No reference specification for motors: {missing}")
    return transformed, parameters


def build_classifier(name: str, seed: int):
    """Construct a fixed first-pass supervised source-domain classifier."""

    if name == "logistic":
        return make_pipeline(
            StandardScaler(),
            LogisticRegression(
                C=1.0,
                class_weight="balanced",
                max_iter=2_000,
                random_state=seed,
            ),
        )
    if name == "hist_gbr":
        return HistGradientBoostingClassifier(
            class_weight="balanced",
            learning_rate=0.06,
            l2_regularization=1e-3,
            max_iter=250,
            max_leaf_nodes=31,
            random_state=seed,
        )
    if name == "random_forest":
        return RandomForestClassifier(
            n_estimators=400,
            min_samples_leaf=5,
            class_weight="balanced_subsample",
            n_jobs=-1,
            random_state=seed,
        )
    raise ValueError(f"Unknown classifier: {name}")


def classifier_scores(model, features: np.ndarray) -> np.ndarray:
    """Return an unsquashed anomaly score when the estimator exposes one."""

    if hasattr(model, "decision_function"):
        scores = np.asarray(model.decision_function(features), dtype=np.float64)
        if scores.ndim == 2:
            scores = scores[:, -1]
        return scores.reshape(-1)
    probabilities = np.asarray(model.predict_proba(features), dtype=np.float64)
    if probabilities.ndim != 2 or probabilities.shape[1] != 2:
        raise ValueError("Classifier must provide binary class probabilities")
    return probabilities[:, 1]


def source_train_and_calibration_masks(
    frame: pd.DataFrame,
    source_motors: Sequence[str],
    *,
    healthy_train_last_block: int = 23,
    healthy_calibration_first_block: int = 25,
) -> tuple[np.ndarray, np.ndarray]:
    """Hold late source-health blocks out of classifier fitting for thresholding."""

    source = frame["motor_id"].isin(source_motors)
    healthy = frame["is_healthy"].astype(bool)
    train = source & (
        ~healthy | (frame["block_id"].astype(int) <= healthy_train_last_block)
    )
    calibration = (
        source
        & healthy
        & (frame["block_id"].astype(int) >= healthy_calibration_first_block)
    )
    if np.any(train & calibration):
        raise AssertionError("Source train and calibration masks overlap")
    return train.to_numpy(), calibration.to_numpy()


def block_score_table(
    frame: pd.DataFrame, scores: np.ndarray, *, quantile: float = 1.0
) -> pd.DataFrame:
    """Aggregate window anomaly scores to the predeclared macro-block unit."""

    if len(frame) != len(scores):
        raise ValueError("frame and scores must have equal length")
    if not 0 < quantile <= 1:
        raise ValueError("quantile must lie in (0, 1]")
    working = frame[
        [
            "motor_id",
            "record_id",
            "fault_family",
            "severity_percent",
            "is_healthy",
            "block_id",
        ]
    ].copy()
    working["score"] = np.asarray(scores, dtype=np.float64)
    keys = [
        "motor_id",
        "record_id",
        "fault_family",
        "severity_percent",
        "is_healthy",
        "block_id",
    ]
    result = (
        working.groupby(keys, observed=True, sort=True)["score"]
        .agg(lambda values: values.quantile(quantile, interpolation="higher"))
        .reset_index()
    )
    return result
