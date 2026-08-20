"""Post-reveal feature-drift and score-attribution audit for external failure."""

from __future__ import annotations

import argparse
import json
from datetime import UTC, datetime
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.stats import spearmanr
from sklearn.metrics import roc_auc_score

from pmsm_sci.faults.baseline import feature_columns
from pmsm_sci.faults.covariance import (
    log_euclidean_entity_covariance,
    mahalanobis_scores,
    sample_covariance,
)
from pmsm_sci.faults.external_validation import (
    ADAPTATION_BLOCKS,
    ADAPTATION_LOAD_NM,
    HEALTH_TEST_LOADS_NM,
    robust_reference_parameters,
    robust_transform,
    system_block_scores,
)

if __package__:
    from scripts.run_external_pmsm_validation import (
        external_roles,
        file_sha256,
        source_reference_geometry,
    )
else:
    from run_external_pmsm_validation import (  # type: ignore[import-not-found]
        external_roles,
        file_sha256,
        source_reference_geometry,
    )

METHOD = "log_euclidean_entity_covariance"
EXTERNAL_MOTOR_ID = "external_dual_three_phase"
SUBSYSTEMS = ("SubSys1", "SubSys2")
EXPECTED_FEATURES = 27


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--frozen-results-dir",
        type=Path,
        default=Path("results/external_pmsm_validation"),
    )
    parser.add_argument(
        "--results-dir",
        type=Path,
        default=Path("results/external_feature_drift"),
    )
    return parser.parse_args()


def feature_family(feature: str) -> str:
    """Assign transparent diagnostic families to every scale-free input."""

    if feature == "fundamental_hz":
        return "speed_proxy"
    if feature == "spectral_entropy":
        return "spectral_entropy"
    if feature.startswith(("harmonic_", "sideband_")) or feature == "thd_2_to_5_mean":
        return "harmonic_sideband"
    if feature in {
        "sequence_unbalance",
        "zero_sequence_ratio",
        "phase_rms_cv",
    }:
        return "sequence_imbalance"
    if (
        feature.startswith(("crest_", "kurtosis_", "rms_ratio_"))
        or feature
        in {
            "fundamental_amplitude_cv",
            "clarke_radius_cv",
        }
    ):
        return "current_shape"
    raise ValueError(f"Feature family is not defined for {feature}")


def symmetric_mahalanobis_contributions(
    values: np.ndarray,
    precision: np.ndarray,
) -> tuple[np.ndarray, np.ndarray]:
    """Split every symmetric quadratic cross-term equally across its features.

    For symmetric precision ``P``, feature ``j`` receives
    ``c_j = x_j (P x)_j``. The two allocations for a pair ``j,k`` sum to the
    full cross-term ``2 P_jk x_j x_k``, and ``sum_j c_j = x' P x``.
    Contributions may be negative because covariance cross-terms can be negative.
    """

    data = np.asarray(values, dtype=np.float64)
    matrix = np.asarray(precision, dtype=np.float64)
    if data.ndim != 2 or matrix.shape != (data.shape[1], data.shape[1]):
        raise ValueError("values and precision dimensions are inconsistent")
    if not np.allclose(matrix, matrix.T, rtol=1e-12, atol=1e-12):
        raise ValueError("precision must be symmetric")
    projected = data @ matrix.T
    contributions = data * projected
    scores = contributions.sum(axis=1)
    return scores, contributions


def _hedges_g(fault: np.ndarray, healthy: np.ndarray) -> float:
    if len(fault) < 2 or len(healthy) < 2:
        return np.nan
    fault_variance = np.var(fault, ddof=1)
    healthy_variance = np.var(healthy, ddof=1)
    denominator_df = len(fault) + len(healthy) - 2
    pooled_variance = (
        (len(fault) - 1) * fault_variance
        + (len(healthy) - 1) * healthy_variance
    ) / denominator_df
    if pooled_variance <= 0:
        return np.nan
    cohen_d = (np.mean(fault) - np.mean(healthy)) / np.sqrt(pooled_variance)
    correction = 1 - 3 / (4 * (len(fault) + len(healthy)) - 9)
    return float(correction * cohen_d)


def _paired_dz(differences: np.ndarray) -> float:
    if len(differences) < 2:
        return np.nan
    scale = np.std(differences, ddof=1)
    if scale <= 0:
        return np.nan
    return float(np.mean(differences) / scale)


def load_frozen_inputs(
    frozen_results_dir: Path,
) -> tuple[pd.DataFrame, pd.DataFrame, list[str], pd.DataFrame, dict[str, object]]:
    """Load and validate the exact feature tables and frozen block scores."""

    metadata = json.loads(
        (frozen_results_dir / "run_metadata.json").read_text(encoding="utf-8")
    )
    if metadata.get("fault_reveal_required") is not True:
        raise ValueError("Feature drift requires the completed frozen fault reveal")
    source_path = Path(str(metadata["source_features"]))
    external_path = Path(str(metadata["external_features"]))
    if file_sha256(source_path) != metadata["source_features_sha256"]:
        raise ValueError("Source feature hash differs from the frozen run")
    if file_sha256(external_path) != metadata["external_features_sha256"]:
        raise ValueError("External feature hash differs from the frozen run")
    source = pd.read_csv(source_path)
    external = pd.read_csv(external_path).reset_index(drop=True)
    columns = feature_columns(source, "scale_free")
    if columns != metadata["feature_columns"] or len(columns) != EXPECTED_FEATURES:
        raise ValueError("Frozen scale-free feature list is inconsistent")
    if set(external["motor_id"].astype(str)) != {EXTERNAL_MOTOR_ID}:
        raise ValueError("External feature rows must belong to exactly one frozen motor")
    if len(external) != 13_440:
        raise ValueError("Expected 13,440 external feature windows")
    keys = ["record_id", "subsystem", "block_id", "window_id"]
    if external.duplicated(keys).any():
        raise ValueError("External record-subsystem-block-window keys are not unique")
    if external.groupby(["record_id", "subsystem", "block_id"]).size().ne(15).any():
        raise ValueError("Every record-subsystem block must contain 15 windows")
    if external.loc[~external["is_healthy"].astype(bool), "record_id"].nunique() != 48:
        raise ValueError("Expected 48 fault condition records")
    external["role"] = external_roles(external)
    if external.loc[external["role"].eq("fault_test"), "is_healthy"].any():
        raise ValueError("Fault role contains a healthy row")
    if not np.isfinite(external[columns].to_numpy(dtype=np.float64)).all():
        raise ValueError("External feature values must be finite")

    frozen_blocks = pd.read_csv(
        frozen_results_dir / METHOD / "system_block_predictions.csv"
    )
    if len(frozen_blocks) != 448:
        raise ValueError("Frozen Log-Euclidean output must contain 448 system blocks")
    if frozen_blocks.duplicated(["record_id", "load_nm", "block_id"]).any():
        raise ValueError("Frozen system block keys are not unique")
    return source, external, columns, frozen_blocks, metadata


def reconstruct_frozen_geometry(
    source: pd.DataFrame,
    external: pd.DataFrame,
    columns: list[str],
    metadata: dict[str, object],
) -> tuple[
    np.ndarray,
    np.ndarray,
    np.ndarray,
    dict[str, np.ndarray],
    pd.DataFrame,
]:
    """Reconstruct the frozen deterministic geometry and its exact contributions."""

    _, source_covariances, _, _ = source_reference_geometry(source, columns)
    transformed = np.full((len(external), len(columns)), np.nan, dtype=np.float64)
    scores = np.full(len(external), np.nan, dtype=np.float64)
    contributions = np.full_like(transformed, np.nan)
    covariances: dict[str, np.ndarray] = {}
    diagnostics: list[dict[str, object]] = []
    frozen_references = metadata["subsystem_references"]
    ridge = float(metadata["log_ridge_fraction"])

    for subsystem in SUBSYSTEMS:
        mask = external["subsystem"].astype(str).eq(subsystem).to_numpy()
        frame = external.loc[mask]
        raw = frame[columns].to_numpy(dtype=np.float64)
        adaptation = (
            frame["is_healthy"].astype(bool)
            & frame["load_nm"].astype(int).eq(ADAPTATION_LOAD_NM)
            & frame["block_id"].astype(int).isin(ADAPTATION_BLOCKS)
        ).to_numpy()
        if adaptation.sum() != 60:
            raise AssertionError(f"{subsystem}: expected 60 frozen adaptation windows")
        center, scale = robust_reference_parameters(raw[adaptation])
        frozen_center = np.asarray(frozen_references[subsystem]["center"], dtype=float)
        frozen_scale = np.asarray(frozen_references[subsystem]["scale"], dtype=float)
        if not np.allclose(center, frozen_center, rtol=1e-12, atol=1e-12):
            raise AssertionError(f"{subsystem}: center does not match frozen artifact")
        if not np.allclose(scale, frozen_scale, rtol=1e-12, atol=1e-12):
            raise AssertionError(f"{subsystem}: scale does not match frozen artifact")
        values = robust_transform(raw, center, scale)
        target_covariance = sample_covariance(values[adaptation])
        covariance = log_euclidean_entity_covariance(
            [*source_covariances, target_covariance], ridge
        )
        precision = np.linalg.pinv(covariance, hermitian=True)
        quadratic_scores = mahalanobis_scores(
            values, covariance, np.zeros(len(columns), dtype=np.float64)
        )
        allocated_scores, allocated = symmetric_mahalanobis_contributions(
            values, precision
        )
        if not np.allclose(
            allocated_scores, quadratic_scores, rtol=1e-10, atol=1e-8
        ):
            raise AssertionError("Symmetric feature allocations do not sum to score")
        transformed[mask] = values
        scores[mask] = quadratic_scores
        contributions[mask] = allocated
        covariances[subsystem] = covariance
        diagnostics.append(
            {
                "subsystem": subsystem,
                "features": len(columns),
                "adaptation_windows": int(adaptation.sum()),
                "ridge_fraction": ridge,
                "covariance_rank": int(np.linalg.matrix_rank(covariance)),
                "covariance_condition_number": float(np.linalg.cond(covariance)),
                "max_window_contribution_sum_error": float(
                    np.max(np.abs(allocated_scores - quadratic_scores))
                ),
                "center_matches_frozen": True,
                "scale_matches_frozen": True,
            }
        )
    if not (
        np.isfinite(transformed).all()
        and np.isfinite(scores).all()
        and np.isfinite(contributions).all()
    ):
        raise FloatingPointError("Frozen geometry reconstruction is incomplete")
    return transformed, scores, contributions, covariances, pd.DataFrame(diagnostics)


def winning_window_contribution_tables(
    external: pd.DataFrame,
    scores: np.ndarray,
    contributions: np.ndarray,
    columns: list[str],
    frozen_blocks: pd.DataFrame,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Select the exact system-max window and audit its score allocation."""

    reconstructed = system_block_scores(external, scores)
    keys = ["record_id", "load_nm", "block_id"]
    comparison = reconstructed.merge(
        frozen_blocks,
        on=keys,
        suffixes=("_reconstructed", "_frozen"),
        validate="one_to_one",
    )
    if len(comparison) != 448:
        raise AssertionError("Frozen/reconstructed block join must retain 448 rows")
    for name in ("score", "subsystem_score_SubSys1", "subsystem_score_SubSys2"):
        if not np.allclose(
            comparison[f"{name}_reconstructed"],
            comparison[f"{name}_frozen"],
            rtol=1e-12,
            atol=1e-10,
        ):
            raise AssertionError(f"Reconstructed {name} differs from frozen scores")

    working = external[
        [
            "record_id",
            "load_nm",
            "subsystem",
            "block_id",
            "window_id",
            "is_healthy",
            "fault_turns",
            "fault_phase",
            "role",
        ]
    ].copy()
    working["row_index"] = np.arange(len(external))
    working["window_score"] = scores
    winner_indices = (
        working.groupby(keys, observed=True, sort=True)["window_score"].idxmax().to_numpy()
    )
    winners = working.loc[winner_indices].sort_values(keys, ignore_index=True)
    winner_contributions = contributions[winners["row_index"].to_numpy(dtype=int)]
    winner_scores = winners["window_score"].to_numpy(dtype=np.float64)
    contribution_sums = winner_contributions.sum(axis=1)
    absolute_denominator = np.abs(winner_contributions).sum(axis=1)

    frozen_ordered = frozen_blocks.sort_values(keys, ignore_index=True)
    if not winners[keys].equals(frozen_ordered[keys]):
        raise AssertionError("Winning-window keys do not align to frozen system blocks")
    checks = winners.copy()
    checks["frozen_system_score"] = frozen_ordered["score"].to_numpy(dtype=float)
    checks["contribution_sum"] = contribution_sums
    checks["contribution_sum_error"] = contribution_sums - winner_scores
    checks["frozen_score_error"] = winner_scores - checks["frozen_system_score"]
    checks["alarm"] = frozen_ordered["alarm"].astype(bool).to_numpy()
    checks["p_value"] = frozen_ordered["p_value"].to_numpy(dtype=float)
    checks["external_motor_id"] = EXTERNAL_MOTOR_ID
    if np.max(np.abs(checks["contribution_sum_error"])) > 1e-8:
        raise AssertionError("Winning contributions do not sum to their score")

    repeated = checks.loc[checks.index.repeat(len(columns))].reset_index(drop=True)
    repeated["feature"] = np.tile(columns, len(checks))
    repeated["feature_family"] = repeated["feature"].map(feature_family)
    repeated["signed_contribution"] = winner_contributions.reshape(-1)
    repeated["score_share"] = (
        winner_contributions / winner_scores[:, None]
    ).reshape(-1)
    repeated["absolute_contribution_share"] = (
        np.abs(winner_contributions) / absolute_denominator[:, None]
    ).reshape(-1)
    keep = [
        "external_motor_id",
        "record_id",
        "load_nm",
        "block_id",
        "is_healthy",
        "fault_turns",
        "fault_phase",
        "role",
        "subsystem",
        "window_id",
        "window_score",
        "alarm",
        "feature",
        "feature_family",
        "signed_contribution",
        "score_share",
        "absolute_contribution_share",
    ]
    return checks, repeated[keep]


def record_block_feature_units(
    external: pd.DataFrame,
    transformed: np.ndarray,
    columns: list[str],
) -> pd.DataFrame:
    """Aggregate correlated windows to record-subsystem-block feature means."""

    metadata_columns = [
        "record_id",
        "load_nm",
        "subsystem",
        "block_id",
        "is_healthy",
        "fault_turns",
        "fault_phase",
        "role",
        "motor_id",
    ]
    working = external[metadata_columns + columns].copy()
    working["fault_phase"] = working["fault_phase"].fillna("none")
    transformed_frame = pd.DataFrame(
        transformed,
        columns=[f"z__{column}" for column in columns],
        index=working.index,
    )
    working = pd.concat([working, transformed_frame], axis=1)
    group_keys = metadata_columns.copy()
    units = (
        working.groupby(group_keys, observed=True, sort=True, dropna=False)
        .agg(
            windows=("record_id", "size"),
            **{column: (column, "mean") for column in columns},
            **{f"z__{column}": (f"z__{column}", "mean") for column in columns},
        )
        .reset_index()
    )
    if len(units) != 896 or not units["windows"].eq(15).all():
        raise AssertionError("Expected 896 record-subsystem-block units of 15 windows")
    speed = units[
        ["record_id", "subsystem", "block_id", "fundamental_hz"]
    ].rename(columns={"fundamental_hz": "speed_proxy_hz"})
    raw = units.melt(
        id_vars=metadata_columns + ["windows"],
        value_vars=columns,
        var_name="feature",
        value_name="raw_value",
    )
    z_columns = [f"z__{column}" for column in columns]
    standardized = units.melt(
        id_vars=["record_id", "subsystem", "block_id"],
        value_vars=z_columns,
        var_name="feature",
        value_name="robust_z_value",
    )
    standardized["feature"] = standardized["feature"].str.removeprefix("z__")
    long = raw.merge(
        standardized,
        on=["record_id", "subsystem", "block_id", "feature"],
        validate="one_to_one",
    ).merge(
        speed,
        on=["record_id", "subsystem", "block_id"],
        validate="many_to_one",
    )
    long["feature_family"] = long["feature"].map(feature_family)
    long["health_population"] = np.where(
        long["is_healthy"].astype(bool), "healthy_" + long["role"], "fault"
    )
    return long


def _population_copies(units: pd.DataFrame) -> pd.DataFrame:
    healthy = units[units["is_healthy"].astype(bool)].copy()
    healthy["population"] = "healthy_all"
    by_role = units[units["is_healthy"].astype(bool)].copy()
    by_role["population"] = "healthy_" + by_role["role"].astype(str)
    faults = units[~units["is_healthy"].astype(bool)].copy()
    faults["population"] = "fault"
    return pd.concat([healthy, by_role, faults], ignore_index=True)


def feature_block_drift(units: pd.DataFrame) -> pd.DataFrame:
    working = _population_copies(units)
    return (
        working.groupby(
            ["feature", "feature_family", "population", "block_id"],
            observed=True,
            sort=True,
        )
        .agg(
            independent_motors=("motor_id", "nunique"),
            record_subsystem_units=("raw_value", "size"),
            speed_proxy_hz_mean=("speed_proxy_hz", "mean"),
            raw_mean=("raw_value", "mean"),
            raw_std=("raw_value", "std"),
            raw_q25=("raw_value", lambda values: values.quantile(0.25)),
            raw_median=("raw_value", "median"),
            raw_q75=("raw_value", lambda values: values.quantile(0.75)),
            robust_z_mean=("robust_z_value", "mean"),
            robust_z_median=("robust_z_value", "median"),
        )
        .reset_index()
    )


def feature_speed_associations(units: pd.DataFrame) -> pd.DataFrame:
    working = _population_copies(units)
    rows: list[dict[str, object]] = []
    for (feature, family, population), group in working.groupby(
        ["feature", "feature_family", "population"], observed=True, sort=True
    ):
        raw_result = spearmanr(group["speed_proxy_hz"], group["raw_value"])
        z_result = spearmanr(group["speed_proxy_hz"], group["robust_z_value"])
        rows.append(
            {
                "feature": feature,
                "feature_family": family,
                "population": population,
                "independent_motors": group["motor_id"].nunique(),
                "record_subsystem_block_units": len(group),
                "spearman_raw_vs_speed_proxy": float(raw_result.statistic),
                "spearman_robust_z_vs_speed_proxy": float(z_result.statistic),
                "speed_proxy": "fundamental_hz (electrical-frequency proxy)",
                "inferential_p_value_claimed": False,
            }
        )
    return pd.DataFrame(rows)


def same_block_feature_effects(units: pd.DataFrame) -> pd.DataFrame:
    """Compute same-block effects at the record-subsystem-block unit."""

    scopes = {
        "all_matched_loads": set(range(0, 36, 5)),
        "heldout_health_test_loads": set(HEALTH_TEST_LOADS_NM),
    }
    rows: list[dict[str, object]] = []
    for scope, loads in scopes.items():
        scoped = units[units["load_nm"].astype(int).isin(loads)]
        healthy = scoped[scoped["is_healthy"].astype(bool)]
        faults = scoped[~scoped["is_healthy"].astype(bool)]
        match_keys = ["load_nm", "subsystem", "block_id", "feature"]
        health_values = healthy[match_keys + ["raw_value", "robust_z_value"]].rename(
            columns={
                "raw_value": "matched_health_raw",
                "robust_z_value": "matched_health_z",
            }
        )
        if health_values.duplicated(match_keys).any():
            raise AssertionError("Each load-subsystem-block-feature needs one health unit")
        paired = faults.merge(
            health_values,
            on=match_keys,
            how="left",
            validate="many_to_one",
        )
        if len(paired) != len(faults) or paired["matched_health_raw"].isna().any():
            raise AssertionError("Same-block health matching lost fault units")
        paired["raw_difference"] = paired["raw_value"] - paired["matched_health_raw"]
        paired["z_difference"] = (
            paired["robust_z_value"] - paired["matched_health_z"]
        )

        for feature in sorted(units["feature"].unique()):
            family = feature_family(feature)
            for block_id in (-1, *range(8)):
                health_group = healthy[healthy["feature"].eq(feature)]
                fault_group = faults[faults["feature"].eq(feature)]
                paired_group = paired[paired["feature"].eq(feature)]
                if block_id >= 0:
                    health_group = health_group[health_group["block_id"].eq(block_id)]
                    fault_group = fault_group[fault_group["block_id"].eq(block_id)]
                    paired_group = paired_group[paired_group["block_id"].eq(block_id)]
                labels = np.concatenate(
                    [np.zeros(len(health_group)), np.ones(len(fault_group))]
                )
                raw_values = np.concatenate(
                    [health_group["raw_value"], fault_group["raw_value"]]
                )
                z_values = np.concatenate(
                    [health_group["robust_z_value"], fault_group["robust_z_value"]]
                )
                raw_auc = float(roc_auc_score(labels, raw_values))
                z_auc = float(roc_auc_score(labels, z_values))
                raw_fault = fault_group["raw_value"].to_numpy(dtype=float)
                raw_health = health_group["raw_value"].to_numpy(dtype=float)
                z_fault = fault_group["robust_z_value"].to_numpy(dtype=float)
                z_health = health_group["robust_z_value"].to_numpy(dtype=float)
                rows.append(
                    {
                        "scope": scope,
                        "feature": feature,
                        "feature_family": family,
                        "block_id": block_id,
                        "block_label": "all_blocks" if block_id < 0 else str(block_id),
                        "independent_motors": 1,
                        "healthy_units": len(health_group),
                        "fault_units": len(fault_group),
                        "matched_fault_health_pairs": len(paired_group),
                        "healthy_raw_mean": float(np.mean(raw_health)),
                        "fault_raw_mean": float(np.mean(raw_fault)),
                        "raw_hedges_g_fault_minus_health": _hedges_g(
                            raw_fault, raw_health
                        ),
                        "raw_single_feature_auc_fault_higher": raw_auc,
                        "raw_direction_free_auc": max(raw_auc, 1 - raw_auc),
                        "matched_raw_difference_mean": float(
                            paired_group["raw_difference"].mean()
                        ),
                        "matched_raw_difference_median": float(
                            paired_group["raw_difference"].median()
                        ),
                        "matched_raw_dz": _paired_dz(
                            paired_group["raw_difference"].to_numpy(dtype=float)
                        ),
                        "robust_z_hedges_g_fault_minus_health": _hedges_g(
                            z_fault, z_health
                        ),
                        "robust_z_single_feature_auc_fault_higher": z_auc,
                        "robust_z_direction_free_auc": max(z_auc, 1 - z_auc),
                        "matched_robust_z_dz": _paired_dz(
                            paired_group["z_difference"].to_numpy(dtype=float)
                        ),
                        "auroc_inferential_claimed": False,
                    }
                )
    return pd.DataFrame(rows)


def contribution_summaries(
    winning: pd.DataFrame,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    working = _population_copies(winning)
    by_block = (
        working.groupby(
            ["feature", "feature_family", "population", "block_id"],
            observed=True,
            sort=True,
        )
        .agg(
            system_blocks=("signed_contribution", "size"),
            signed_contribution_mean=("signed_contribution", "mean"),
            signed_contribution_median=("signed_contribution", "median"),
            absolute_contribution_mean=(
                "signed_contribution",
                lambda values: np.abs(values).mean(),
            ),
            score_share_mean=("score_share", "mean"),
            absolute_contribution_share_mean=(
                "absolute_contribution_share",
                "mean",
            ),
            negative_contribution_fraction=(
                "signed_contribution",
                lambda values: (values < 0).mean(),
            ),
        )
        .reset_index()
    )
    overall = (
        working.groupby(
            ["feature", "feature_family", "population"],
            observed=True,
            sort=True,
        )
        .agg(
            system_blocks=("signed_contribution", "size"),
            signed_contribution_mean=("signed_contribution", "mean"),
            signed_contribution_median=("signed_contribution", "median"),
            absolute_contribution_mean=(
                "signed_contribution",
                lambda values: np.abs(values).mean(),
            ),
            score_share_mean=("score_share", "mean"),
            absolute_contribution_share_mean=(
                "absolute_contribution_share",
                "mean",
            ),
            negative_contribution_fraction=(
                "signed_contribution",
                lambda values: (values < 0).mean(),
            ),
        )
        .reset_index()
    )
    return by_block, overall


def diagnostic_summary(
    effects: pd.DataFrame,
    speed: pd.DataFrame,
    contribution: pd.DataFrame,
) -> pd.DataFrame:
    primary_effect = effects[
        effects["scope"].eq("heldout_health_test_loads")
        & effects["block_id"].eq(-1)
    ].copy()
    speed_wide = speed[speed["population"].isin(["healthy_all", "fault"])].pivot(
        index=["feature", "feature_family"],
        columns="population",
        values="spearman_raw_vs_speed_proxy",
    ).reset_index()
    speed_wide = speed_wide.rename(
        columns={
            "healthy_all": "healthy_speed_spearman",
            "fault": "fault_speed_spearman",
        }
    )
    contribution_wide = contribution[
        contribution["population"].isin(["healthy_health_test", "fault"])
    ].pivot(
        index=["feature", "feature_family"],
        columns="population",
        values="absolute_contribution_share_mean",
    ).reset_index()
    contribution_wide = contribution_wide.rename(
        columns={
            "healthy_health_test": "healthy_test_absolute_contribution_share",
            "fault": "fault_absolute_contribution_share",
        }
    )
    result = primary_effect.merge(
        speed_wide,
        on=["feature", "feature_family"],
        validate="one_to_one",
    ).merge(
        contribution_wide,
        on=["feature", "feature_family"],
        validate="one_to_one",
    )
    result["max_absolute_speed_spearman"] = result[
        ["healthy_speed_spearman", "fault_speed_spearman"]
    ].abs().max(axis=1)
    return result.sort_values(
        ["fault_absolute_contribution_share", "raw_direction_free_auc"],
        ascending=False,
        ignore_index=True,
    )


def main() -> None:
    args = parse_args()
    source, external, columns, frozen_blocks, metadata = load_frozen_inputs(
        args.frozen_results_dir
    )
    transformed, scores, contributions, covariances, geometry = (
        reconstruct_frozen_geometry(source, external, columns, metadata)
    )
    checks, winning = winning_window_contribution_tables(
        external, scores, contributions, columns, frozen_blocks
    )
    units = record_block_feature_units(external, transformed, columns)
    block_drift = feature_block_drift(units)
    speed = feature_speed_associations(units)
    effects = same_block_feature_effects(units)
    contribution_by_block, contribution_overall = contribution_summaries(winning)
    overview = diagnostic_summary(effects, speed, contribution_overall)

    args.results_dir.mkdir(parents=True, exist_ok=True)
    units.to_csv(
        args.results_dir / "record_block_subsystem_feature_means.csv.gz",
        index=False,
        compression="gzip",
    )
    block_drift.to_csv(args.results_dir / "feature_block_drift.csv", index=False)
    speed.to_csv(args.results_dir / "feature_speed_associations.csv", index=False)
    effects.to_csv(args.results_dir / "same_block_feature_effects.csv", index=False)
    checks.to_csv(args.results_dir / "score_reconstruction_checks.csv", index=False)
    winning.to_csv(
        args.results_dir / "winning_window_feature_contributions.csv.gz",
        index=False,
        compression="gzip",
    )
    contribution_by_block.to_csv(
        args.results_dir / "mahalanobis_contribution_by_block.csv", index=False
    )
    contribution_overall.to_csv(
        args.results_dir / "mahalanobis_contribution_overall.csv", index=False
    )
    overview.to_csv(args.results_dir / "feature_diagnostic_summary.csv", index=False)
    geometry.to_csv(args.results_dir / "geometry_reconstruction.csv", index=False)
    for subsystem, covariance in covariances.items():
        np.savez_compressed(
            args.results_dir / f"reconstructed_{subsystem}_log_covariance.npz",
            covariance=covariance,
            feature_columns=np.asarray(columns),
        )

    output_metadata = {
        "created_utc": datetime.now(UTC).isoformat(),
        "analysis_label": "post-reveal exploratory external failure diagnosis",
        "new_model_fitted": False,
        "threshold_changed_or_recomputed": False,
        "frozen_method": METHOD,
        "source_features_sha256": metadata["source_features_sha256"],
        "external_features_sha256": metadata["external_features_sha256"],
        "feature_columns": columns,
        "feature_count": len(columns),
        "analysis_unit_for_drift": "record-subsystem-block mean (15 windows)",
        "speed_proxy": "fundamental_hz in Hz; electrical-frequency proxy, not asserted RPM",
        "effect_scopes": {
            "all_matched_loads": list(range(0, 36, 5)),
            "heldout_health_test_loads": list(HEALTH_TEST_LOADS_NM),
        },
        "effect_interpretation": (
            "Single-feature AUROC and effects are descriptive, same-block comparisons. "
            "For each load/subsystem/block, one healthy condition is reused for the six "
            "fault-turn comparisons; pair counts are therefore not independent machine "
            "replicates. All repeated conditions come from one motor."
        ),
        "mahalanobis_allocation": (
            "For symmetric precision P, feature j receives c_j=x_j(Px)_j. This splits "
            "each pairwise cross-term equally between its two features and guarantees "
            "sum_j c_j=x'Px. Signed contributions can be negative."
        ),
        "geometry_provenance": (
            "The covariance is reconstructed deterministically from the hash-locked "
            "source/external feature tables and frozen center, scale, adaptation, and "
            "ridge metadata. Fault labels do not enter this reconstruction."
        ),
        "system_score_attribution": (
            "Contributions are reported for the winning subsystem/window that generated "
            "the frozen system block maximum. Reconstructed block scores are checked "
            "against the frozen artifact before output."
        ),
        "independent_external_motors": 1,
        "fault_records": 48,
        "single_motor_conditional": True,
        "exploratory_only": True,
        "causal_feature_claim": False,
        "inference_boundary": (
            "Health and fault records are conditions from one physical motor. Block and "
            "fundamental frequency co-move during the frozen speed ramp, so associations "
            "cannot identify a causal fault feature or generalize across motors."
        ),
    }
    (args.results_dir / "run_metadata.json").write_text(
        json.dumps(output_metadata, indent=2), encoding="utf-8"
    )
    print(overview.head(15).to_string(index=False))


if __name__ == "__main__":
    main()
