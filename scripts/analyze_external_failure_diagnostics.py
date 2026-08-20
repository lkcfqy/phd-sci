"""Diagnose the frozen external PMSM failure without refitting or rethresholding.

All calculations consume saved block/record predictions.  The script never opens a
MAT file, rebuilds a feature, fits an estimator, or changes an alarm threshold.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.stats import spearmanr
from sklearn.metrics import roc_auc_score

METHODS = (
    "target_ledoit",
    "target_sample_covariance",
    "source_covariance",
    "entity_balanced_covariance",
    "log_euclidean_entity_covariance",
    "target_ocsvm_rbf",
    "source_target_ocsvm_rbf",
    "target_isolation_forest",
    "source_target_isolation_forest",
    "target_min_cov_det",
    "source_target_min_cov_det",
)
PROPOSED = "log_euclidean_entity_covariance"
HORIZONS = (("first_4_blocks", 4), ("first_7_blocks", 7), ("all_8_blocks", 8))
ANALYSIS_START_SECONDS = 12.0
BLOCK_SECONDS = 3.0
HEALTH_AUDIT_BLOCK_OFFSET = 4
BOOTSTRAP_ITERATIONS = 10_000
BOOTSTRAP_SEED = 711

TRANSFER_PAIRS = (
    (
        "ocsvm",
        "target_ocsvm_rbf",
        "source_target_ocsvm_rbf",
        "same estimator; target-only minus source+target",
    ),
    (
        "isolation_forest",
        "target_isolation_forest",
        "source_target_isolation_forest",
        "same estimator; target-only minus source+target",
    ),
    (
        "min_cov_det",
        "target_min_cov_det",
        "source_target_min_cov_det",
        "same estimator; target-only minus source+target",
    ),
    (
        "sample_vs_arithmetic_entity_covariance",
        "target_sample_covariance",
        "entity_balanced_covariance",
        "closest covariance transfer contrast; matrix aggregation differs",
    ),
    (
        "sample_vs_log_euclidean_entity_covariance",
        "target_sample_covariance",
        "log_euclidean_entity_covariance",
        "closest covariance transfer contrast; matrix aggregation differs",
    ),
)

BLOCK_COLUMNS = {
    "record_id",
    "load_nm",
    "block_id",
    "score",
    "is_healthy",
    "fault_turns",
    "fault_phase",
    "role",
    "p_value",
    "alarm",
    "method",
}
RECORD_COLUMNS = {
    "record_id",
    "load_nm",
    "fault_turns",
    "fault_phase",
    "blocks",
    "alarms",
    "block_alarm_rate",
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--validation-dir",
        type=Path,
        default=Path("results/external_pmsm_validation"),
    )
    parser.add_argument(
        "--health-block-inventory",
        type=Path,
        default=Path("results/external_health_audit/block_inventory.csv"),
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("results/external_failure_diagnostics"),
    )
    parser.add_argument("--bootstrap-iterations", type=int, default=BOOTSTRAP_ITERATIONS)
    parser.add_argument("--seed", type=int, default=BOOTSTRAP_SEED)
    return parser.parse_args()


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise ValueError(message)


def boolean_series(series: pd.Series, name: str) -> pd.Series:
    """Convert a saved boolean column without accepting ambiguous values."""

    if pd.api.types.is_bool_dtype(series):
        return series.astype(bool)
    normalized = series.astype(str).str.strip().str.lower()
    _require(set(normalized.unique()).issubset({"true", "false"}), f"Invalid {name}")
    return normalized.eq("true")


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        while chunk := stream.read(1024 * 1024):
            digest.update(chunk)
    return digest.hexdigest()


def load_frozen_results(
    validation_dir: Path,
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """Load, reconcile, and validate all eleven frozen method outputs."""

    aggregate_path = validation_dir / "aggregate_summary.csv"
    _require(aggregate_path.is_file(), f"Missing {aggregate_path}")
    aggregate = pd.read_csv(aggregate_path)
    _require(
        len(aggregate) == len(METHODS) and set(aggregate["method"]) == set(METHODS),
        "Aggregate summary must contain exactly the eleven frozen methods",
    )
    _require(not aggregate["method"].duplicated().any(), "Duplicate aggregate method")

    block_parts: list[pd.DataFrame] = []
    record_parts: list[pd.DataFrame] = []
    checks: list[dict[str, object]] = []
    reference_keys: pd.DataFrame | None = None
    for method in METHODS:
        method_dir = validation_dir / method
        block_path = method_dir / "system_block_predictions.csv"
        record_path = method_dir / "fault_record_summary.csv"
        _require(block_path.is_file(), f"Missing {block_path}")
        _require(record_path.is_file(), f"Missing {record_path}")
        blocks = pd.read_csv(block_path)
        records = pd.read_csv(record_path)
        _require(not BLOCK_COLUMNS.difference(blocks.columns), f"{method}: block schema")
        _require(not RECORD_COLUMNS.difference(records.columns), f"{method}: record schema")
        blocks["is_healthy"] = boolean_series(blocks["is_healthy"], "is_healthy")
        blocks["alarm"] = boolean_series(blocks["alarm"], "alarm")

        _require(len(blocks) == 448, f"{method}: expected 448 block rows")
        _require(blocks["record_id"].nunique() == 56, f"{method}: expected 56 records")
        _require(
            not blocks.duplicated(["record_id", "block_id"]).any(),
            f"{method}: duplicate record-block key",
        )
        _require(
            blocks.groupby("record_id", observed=True).size().eq(8).all(),
            f"{method}: every record must have eight blocks",
        )
        _require(blocks["method"].eq(method).all(), f"{method}: method label mismatch")
        _require(np.isfinite(blocks["score"]).all(), f"{method}: non-finite score")
        _require(np.isfinite(blocks["p_value"]).all(), f"{method}: non-finite p-value")
        expected_roles = {
            "fault_test": 384,
            "health_test": 32,
            "calibration": 24,
            "adaptation": 4,
            "unused": 4,
        }
        _require(
            blocks["role"].value_counts().to_dict() == expected_roles,
            f"{method}: role counts changed",
        )
        _require(len(records) == 48, f"{method}: expected 48 fault records")
        _require(records["record_id"].nunique() == 48, f"{method}: duplicate fault record")
        _require(
            records.groupby("fault_turns", observed=True).size().eq(8).all(),
            f"{method}: fault-turn strata changed",
        )

        recomputed = (
            blocks[blocks["role"].eq("fault_test")]
            .groupby(
                ["record_id", "load_nm", "fault_turns", "fault_phase"],
                observed=True,
                sort=True,
            )
            .agg(
                blocks_recomputed=("alarm", "size"),
                alarms_recomputed=("alarm", "sum"),
                rate_recomputed=("alarm", "mean"),
            )
            .reset_index()
        )
        reconciled = records.merge(
            recomputed,
            on=["record_id", "load_nm", "fault_turns", "fault_phase"],
            validate="one_to_one",
        )
        _require(len(reconciled) == 48, f"{method}: record reconciliation lost rows")
        _require(
            np.allclose(reconciled["blocks"], reconciled["blocks_recomputed"])
            and np.allclose(reconciled["alarms"], reconciled["alarms_recomputed"])
            and np.allclose(reconciled["block_alarm_rate"], reconciled["rate_recomputed"]),
            f"{method}: saved record metrics do not reconcile",
        )
        aggregate_row = aggregate.set_index("method").loc[method]
        health = blocks[blocks["role"].eq("health_test")]
        faults = blocks[blocks["role"].eq("fault_test")]
        _require(
            int(aggregate_row["false_alarms"]) == int(health["alarm"].sum()),
            f"{method}: aggregate false alarms changed",
        )
        _require(
            np.isclose(aggregate_row["fault_block_detection_rate"], faults["alarm"].mean()),
            f"{method}: aggregate detection changed",
        )

        keys = blocks[
            [
                "record_id",
                "load_nm",
                "block_id",
                "is_healthy",
                "fault_turns",
                "fault_phase",
                "role",
            ]
        ].sort_values(["record_id", "block_id"], ignore_index=True)
        if reference_keys is None:
            reference_keys = keys
        else:
            _require(keys.equals(reference_keys), f"{method}: population differs by method")

        block_parts.append(blocks)
        record_parts.append(records.assign(method=method))
        checks.append(
            {
                "scope": method,
                "check": "grain_population_record_and_aggregate_reconciliation",
                "passed": True,
                "block_rows": len(blocks),
                "fault_records": len(records),
            }
        )
    return (
        aggregate,
        pd.concat(block_parts, ignore_index=True),
        pd.concat(record_parts, ignore_index=True),
        pd.DataFrame(checks),
    )


def load_speed_map(path: Path) -> pd.DataFrame:
    """Map analysis block/load cells to RPM observed in the matching health file."""

    inventory = pd.read_csv(path)
    required = {
        "load_nm",
        "block_id",
        "speed_rpm_min",
        "speed_rpm_median",
        "speed_rpm_max",
        "inside_frozen_12_36s_segment",
    }
    _require(not required.difference(inventory.columns), "Health block inventory schema")
    inside = boolean_series(
        inventory["inside_frozen_12_36s_segment"], "inside_frozen_12_36s_segment"
    )
    mapping = inventory.loc[inside, list(required.difference({"inside_frozen_12_36s_segment"}))]
    mapping = mapping.copy()
    mapping["load_nm"] = mapping["load_nm"].astype(int)
    mapping["block_id"] = mapping["block_id"].astype(int) - HEALTH_AUDIT_BLOCK_OFFSET
    mapping = mapping.rename(
        columns={
            "speed_rpm_min": "approx_speed_rpm_min",
            "speed_rpm_median": "approx_speed_rpm_median",
            "speed_rpm_max": "approx_speed_rpm_max",
        }
    )
    _require(len(mapping) == 64, "Expected eight loads by eight analysis blocks")
    _require(
        not mapping.duplicated(["load_nm", "block_id"]).any(),
        "Duplicate load-block speed map",
    )
    _require(set(mapping["block_id"]) == set(range(8)), "Speed map block IDs changed")
    return mapping.sort_values(["load_nm", "block_id"], ignore_index=True)


def attach_approximate_speed(blocks: pd.DataFrame, speed_map: pd.DataFrame) -> pd.DataFrame:
    """Attach health-record RPM as an explicitly approximate condition proxy."""

    working = blocks.copy()
    working["load_nm"] = working["load_nm"].astype(int)
    merged = working.merge(
        speed_map,
        on=["load_nm", "block_id"],
        how="left",
        validate="many_to_one",
    )
    _require(len(merged) == len(blocks), "Speed-map join changed block grain")
    _require(not merged["approx_speed_rpm_median"].isna().any(), "Missing speed proxy")
    return merged


def available_methods(blocks: pd.DataFrame) -> list[str]:
    """Return frozen methods present in a full or synthetic block table."""

    present = set(blocks["method"].astype(str))
    return [method for method in METHODS if method in present]


def horizon_diagnostics(blocks: pd.DataFrame) -> pd.DataFrame:
    """Compute fixed-horizon detection and record-any rates for all methods."""

    rows: list[dict[str, object]] = []
    for method in available_methods(blocks):
        method_blocks = blocks[blocks["method"].eq(method)]
        for label, stop in HORIZONS:
            faults = method_blocks[
                method_blocks["role"].eq("fault_test")
                & method_blocks["block_id"].lt(stop)
            ]
            health = method_blocks[
                method_blocks["role"].eq("health_test")
                & method_blocks["block_id"].lt(stop)
            ]
            record_any = faults.groupby("record_id", observed=True)["alarm"].any()
            health_record_any = health.groupby("record_id", observed=True)["alarm"].any()
            rows.append(
                {
                    "method": method,
                    "horizon": label,
                    "included_block_ids": " ".join(str(item) for item in range(stop)),
                    "fault_records": faults["record_id"].nunique(),
                    "fault_blocks": len(faults),
                    "fault_alarms": int(faults["alarm"].sum()),
                    "fault_block_detection_rate": float(faults["alarm"].mean()),
                    "fault_records_with_any_alarm": int(record_any.sum()),
                    "fault_record_any_alarm_rate": float(record_any.mean()),
                    "health_records": health["record_id"].nunique(),
                    "health_blocks": len(health),
                    "health_false_alarms": int(health["alarm"].sum()),
                    "healthy_block_false_alarm_rate": float(health["alarm"].mean()),
                    "health_records_with_any_alarm": int(health_record_any.sum()),
                    "health_record_any_alarm_rate": float(health_record_any.mean()),
                }
            )
    return pd.DataFrame(rows)


def first_alarm_records(blocks: pd.DataFrame) -> pd.DataFrame:
    """Locate each fault record's first frozen alarm and its health-derived RPM proxy."""

    rows: list[dict[str, object]] = []
    faults = blocks[blocks["role"].eq("fault_test")]
    keys = ["method", "record_id", "load_nm", "fault_turns", "fault_phase"]
    for key, group in faults.groupby(keys, observed=True, sort=True):
        ordered = group.sort_values("block_id")
        alarmed = ordered[ordered["alarm"]]
        first = alarmed.iloc[0] if len(alarmed) else None
        first_block = int(first["block_id"]) if first is not None else None
        rows.append(
            {
                "method": key[0],
                "record_id": key[1],
                "load_nm": int(key[2]),
                "fault_turns": int(key[3]),
                "fault_phase": key[4],
                "blocks": len(ordered),
                "alarms": int(ordered["alarm"].sum()),
                "any_alarm": bool(len(alarmed)),
                "first_alarm_block_id": first_block,
                "first_alarm_start_seconds": (
                    ANALYSIS_START_SECONDS + BLOCK_SECONDS * first_block
                    if first_block is not None
                    else None
                ),
                "first_alarm_stop_seconds": (
                    ANALYSIS_START_SECONDS + BLOCK_SECONDS * (first_block + 1)
                    if first_block is not None
                    else None
                ),
                "first_alarm_approx_rpm_min": (
                    float(first["approx_speed_rpm_min"]) if first is not None else None
                ),
                "first_alarm_approx_rpm_median": (
                    float(first["approx_speed_rpm_median"]) if first is not None else None
                ),
                "first_alarm_approx_rpm_max": (
                    float(first["approx_speed_rpm_max"]) if first is not None else None
                ),
                "rpm_source": "matching-load healthy record; approximate, not fault-record RPM",
            }
        )
    return pd.DataFrame(rows)


def summarize_first_alarms(
    first_alarm: pd.DataFrame,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Summarize first-alarm location and preserve the full block distribution."""

    summaries: list[dict[str, object]] = []
    distributions: list[dict[str, object]] = []
    for method in sorted(first_alarm["method"].astype(str).unique(), key=METHODS.index):
        selected = first_alarm[first_alarm["method"].eq(method)]
        alarmed = selected[selected["any_alarm"]]
        summaries.append(
            {
                "method": method,
                "fault_records": len(selected),
                "records_with_any_alarm": len(alarmed),
                "records_without_alarm": len(selected) - len(alarmed),
                "record_any_alarm_rate": float(selected["any_alarm"].mean()),
                "first_alarm_block_q25": float(alarmed["first_alarm_block_id"].quantile(0.25)),
                "first_alarm_block_median": float(alarmed["first_alarm_block_id"].median()),
                "first_alarm_block_q75": float(alarmed["first_alarm_block_id"].quantile(0.75)),
                "first_alarm_approx_rpm_q25": float(
                    alarmed["first_alarm_approx_rpm_median"].quantile(0.25)
                ),
                "first_alarm_approx_rpm_median": float(
                    alarmed["first_alarm_approx_rpm_median"].median()
                ),
                "first_alarm_approx_rpm_q75": float(
                    alarmed["first_alarm_approx_rpm_median"].quantile(0.75)
                ),
            }
        )
        counts = selected["first_alarm_block_id"].value_counts(dropna=False)
        for block_id, count in counts.items():
            never = pd.isna(block_id)
            distributions.append(
                {
                    "method": method,
                    "first_alarm_block": "never" if never else str(int(block_id)),
                    "records": int(count),
                    "record_fraction": float(count / len(selected)),
                }
            )
    return pd.DataFrame(summaries), pd.DataFrame(distributions)


def block_auroc_diagnostics(
    blocks: pd.DataFrame,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Compute speed-position-matched AUROC and an equal-block-position mean."""

    rows: list[dict[str, object]] = []
    summaries: list[dict[str, object]] = []
    for method in available_methods(blocks):
        selected = blocks[blocks["method"].eq(method)]
        per_block: list[float] = []
        for block_id in range(8):
            health = selected[
                selected["role"].eq("health_test") & selected["block_id"].eq(block_id)
            ]
            faults = selected[
                selected["role"].eq("fault_test") & selected["block_id"].eq(block_id)
            ]
            labels = np.concatenate(
                [np.zeros(len(health), dtype=int), np.ones(len(faults), dtype=int)]
            )
            scores = np.concatenate([health["score"], faults["score"]])
            auroc = float(roc_auc_score(labels, scores))
            per_block.append(auroc)
            rows.append(
                {
                    "method": method,
                    "block_id": block_id,
                    "interval_start_seconds": ANALYSIS_START_SECONDS + block_id * BLOCK_SECONDS,
                    "interval_stop_seconds": (
                        ANALYSIS_START_SECONDS + (block_id + 1) * BLOCK_SECONDS
                    ),
                    "healthy_blocks": len(health),
                    "fault_blocks": len(faults),
                    "block_matched_auroc": auroc,
                }
            )
        health = selected[selected["role"].eq("health_test")]
        faults = selected[selected["role"].eq("fault_test")]
        pooled_labels = np.concatenate(
            [np.zeros(len(health), dtype=int), np.ones(len(faults), dtype=int)]
        )
        pooled_scores = np.concatenate([health["score"], faults["score"]])
        summaries.append(
            {
                "method": method,
                "equal_weight_mean_block_auroc": float(np.mean(per_block)),
                "minimum_block_auroc": float(np.min(per_block)),
                "maximum_block_auroc": float(np.max(per_block)),
                "pooled_block_auroc": float(roc_auc_score(pooled_labels, pooled_scores)),
                "interpretation": (
                    "Equal weighting describes discrimination at matched acceleration "
                    "positions; it is post-reveal diagnostic, not a replacement primary metric."
                ),
            }
        )
    return pd.DataFrame(rows), pd.DataFrame(summaries)


def _spearman(x: pd.Series, y: pd.Series) -> tuple[float, float]:
    result = spearmanr(x.to_numpy(dtype=float), y.to_numpy(dtype=float))
    return float(result.statistic), float(result.pvalue)


def score_speed_diagnostics(
    blocks: pd.DataFrame,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Describe score drift against block position and health-derived RPM."""

    record_rows: list[dict[str, object]] = []
    summary_rows: list[dict[str, object]] = []
    populations = {"healthy_test": "health_test", "fault": "fault_test"}
    for method in available_methods(blocks):
        for population, role in populations.items():
            selected = blocks[
                blocks["method"].eq(method) & blocks["role"].eq(role)
            ]
            block_rho, block_p = _spearman(selected["block_id"], selected["score"])
            rpm_rho, rpm_p = _spearman(
                selected["approx_speed_rpm_median"], selected["score"]
            )
            per_record: list[float] = []
            for record_id, record in selected.groupby("record_id", observed=True):
                rho, naive_p = _spearman(record["block_id"], record["score"])
                per_record.append(rho)
                record_rows.append(
                    {
                        "method": method,
                        "population": population,
                        "record_id": record_id,
                        "load_nm": int(record["load_nm"].iloc[0]),
                        "fault_turns": int(record["fault_turns"].iloc[0]),
                        "records_blocks": len(record),
                        "spearman_block_score": rho,
                        "naive_p_value": naive_p,
                    }
                )
            summary_rows.append(
                {
                    "method": method,
                    "population": population,
                    "blocks": len(selected),
                    "records": selected["record_id"].nunique(),
                    "pooled_spearman_block_score": block_rho,
                    "pooled_naive_p_value_block_score": block_p,
                    "pooled_spearman_approx_rpm_score": rpm_rho,
                    "pooled_naive_p_value_approx_rpm_score": rpm_p,
                    "record_spearman_q25": float(np.quantile(per_record, 0.25)),
                    "record_spearman_median": float(np.median(per_record)),
                    "record_spearman_q75": float(np.quantile(per_record, 0.75)),
                    "records_with_positive_spearman": int((np.asarray(per_record) > 0).sum()),
                    "inference_valid": False,
                    "interpretation": (
                        "Descriptive only: ordered blocks are repeated within one physical motor."
                    ),
                }
            )
    return pd.DataFrame(summary_rows), pd.DataFrame(record_rows)


def paired_bootstrap(
    differences: np.ndarray,
    strata: np.ndarray,
    *,
    iterations: int,
    seed: int,
) -> dict[str, float]:
    """Paired record bootstrap with a centered-null two-sided p-value."""

    values = np.asarray(differences, dtype=np.float64)
    labels = np.asarray(strata)
    _require(values.ndim == 1 and len(values) == len(labels), "Invalid paired values")
    _require(np.isfinite(values).all(), "Paired differences must be finite")
    groups = [np.flatnonzero(labels == label) for label in sorted(set(labels))]
    _require(groups and all(len(group) > 0 for group in groups), "Empty bootstrap stratum")
    rng = np.random.default_rng(seed)
    draws = np.empty(iterations, dtype=np.float64)
    null_draws = np.empty(iterations, dtype=np.float64)
    centered = values - values.mean()
    for index in range(iterations):
        sampled_indices = np.concatenate(
            [rng.choice(group, size=len(group), replace=True) for group in groups]
        )
        draws[index] = values[sampled_indices].mean()
        null_draws[index] = centered[sampled_indices].mean()
    observed = float(values.mean())
    p_value = (1.0 + np.sum(np.abs(null_draws) >= abs(observed))) / (iterations + 1.0)
    return {
        "mean_difference": observed,
        "bootstrap_ci_lower": float(np.quantile(draws, 0.025)),
        "bootstrap_ci_upper": float(np.quantile(draws, 0.975)),
        "centered_bootstrap_two_sided_p": float(p_value),
    }


def holm_adjust(p_values: np.ndarray) -> np.ndarray:
    """Return Holm family-wise adjusted p-values in original order."""

    values = np.asarray(p_values, dtype=np.float64)
    _require(values.ndim == 1 and len(values) > 0, "p_values must be one-dimensional")
    _require(np.all((values >= 0.0) & (values <= 1.0)), "p_values outside [0, 1]")
    order = np.argsort(values, kind="stable")
    sorted_values = values[order]
    factors = len(values) - np.arange(len(values))
    adjusted_sorted = np.minimum(1.0, np.maximum.accumulate(sorted_values * factors))
    adjusted = np.empty_like(adjusted_sorted)
    adjusted[order] = adjusted_sorted
    return adjusted


def _paired_method_row(
    records: pd.DataFrame,
    blocks: pd.DataFrame,
    *,
    method_a: str,
    method_b: str,
    iterations: int,
    seed: int,
) -> dict[str, object]:
    """Compare method A minus method B on identical complete fault records."""

    keys = ["record_id", "load_nm", "fault_turns", "fault_phase"]
    left = records[records["method"].eq(method_a)][keys + ["block_alarm_rate"]].rename(
        columns={"block_alarm_rate": "rate_a"}
    )
    right = records[records["method"].eq(method_b)][keys + ["block_alarm_rate"]].rename(
        columns={"block_alarm_rate": "rate_b"}
    )
    paired = left.merge(right, on=keys, validate="one_to_one")
    _require(len(paired) == 48, f"{method_a} vs {method_b}: expected 48 pairs")
    differences = paired["rate_a"].to_numpy() - paired["rate_b"].to_numpy()
    bootstrap = paired_bootstrap(
        differences,
        paired["fault_turns"].to_numpy(),
        iterations=iterations,
        seed=seed,
    )
    health_a = blocks[blocks["method"].eq(method_a) & blocks["role"].eq("health_test")]
    health_b = blocks[blocks["method"].eq(method_b) & blocks["role"].eq("health_test")]
    return {
        "method_a": method_a,
        "method_b": method_b,
        "paired_fault_records": len(paired),
        "method_a_detection": float(paired["rate_a"].mean()),
        "method_b_detection": float(paired["rate_b"].mean()),
        "method_a_minus_b_detection": bootstrap["mean_difference"],
        "bootstrap_ci_lower": bootstrap["bootstrap_ci_lower"],
        "bootstrap_ci_upper": bootstrap["bootstrap_ci_upper"],
        "centered_bootstrap_two_sided_p": bootstrap["centered_bootstrap_two_sided_p"],
        "records_method_a_better": int((differences > 0).sum()),
        "records_tied": int((differences == 0).sum()),
        "records_method_b_better": int((differences < 0).sum()),
        "method_a_health_false_alarms": int(health_a["alarm"].sum()),
        "method_b_health_false_alarms": int(health_b["alarm"].sum()),
        "bootstrap_unit": "complete fault record",
        "bootstrap_strata": "fault_turns (6 strata x 8 load records)",
        "bootstrap_iterations": iterations,
        "bootstrap_seed": seed,
        "independent_external_motors": 1,
        "cross_motor_inference_valid": False,
    }


def comparisons_vs_proposed(
    records: pd.DataFrame,
    blocks: pd.DataFrame,
    *,
    iterations: int,
    seed: int,
) -> pd.DataFrame:
    """Compare every frozen comparator with Proposed and apply Holm correction."""

    rows: list[dict[str, object]] = []
    for candidate in METHODS:
        if candidate == PROPOSED:
            continue
        row = _paired_method_row(
            records,
            blocks,
            method_a=candidate,
            method_b=PROPOSED,
            iterations=iterations,
            seed=seed,
        )
        row.update(
            {
                "candidate": candidate,
                "reference": PROPOSED,
                "difference_direction": "candidate minus Proposed",
            }
        )
        rows.append(row)
    result = pd.DataFrame(rows)
    result["holm_adjusted_p"] = holm_adjust(
        result["centered_bootstrap_two_sided_p"].to_numpy()
    )
    result["holm_family_size"] = len(result)
    result["reject_equal_mean_at_familywise_0p05"] = result["holm_adjusted_p"].le(0.05)
    return result.sort_values("method_a_minus_b_detection", ascending=False, ignore_index=True)


def target_vs_source_transfer(
    records: pd.DataFrame,
    blocks: pd.DataFrame,
    *,
    iterations: int,
    seed: int,
) -> pd.DataFrame:
    """Compare target-only with source-augmented versions on the same records."""

    rows: list[dict[str, object]] = []
    for family, target, source_target, pair_type in TRANSFER_PAIRS:
        row = _paired_method_row(
            records,
            blocks,
            method_a=target,
            method_b=source_target,
            iterations=iterations,
            seed=seed,
        )
        row.update(
            {
                "family": family,
                "target_only_method": target,
                "source_target_method": source_target,
                "difference_direction": "target-only minus source+target",
                "pair_type": pair_type,
            }
        )
        rows.append(row)
    result = pd.DataFrame(rows)
    result["holm_adjusted_p"] = holm_adjust(
        result["centered_bootstrap_two_sided_p"].to_numpy()
    )
    result["holm_family_size"] = len(result)
    result["reject_equal_mean_at_familywise_0p05"] = result["holm_adjusted_p"].le(0.05)
    return result.sort_values("method_a_minus_b_detection", ascending=False, ignore_index=True)


def combined_method_summary(
    horizon: pd.DataFrame,
    first_alarm: pd.DataFrame,
    auroc: pd.DataFrame,
    speed: pd.DataFrame,
) -> pd.DataFrame:
    """Create one compact row per method from the detailed diagnostics."""

    rows: list[dict[str, object]] = []
    for method in METHODS:
        horizons = horizon[horizon["method"].eq(method)].set_index("horizon")
        alarm = first_alarm[first_alarm["method"].eq(method)].iloc[0]
        auc = auroc[auroc["method"].eq(method)].iloc[0]
        method_speed = speed[speed["method"].eq(method)].set_index("population")
        row: dict[str, object] = {
            "method": method,
            "first_alarm_block_median": alarm["first_alarm_block_median"],
            "first_alarm_approx_rpm_median": alarm["first_alarm_approx_rpm_median"],
            "records_without_alarm": int(alarm["records_without_alarm"]),
            "equal_weight_mean_block_auroc": auc["equal_weight_mean_block_auroc"],
            "pooled_block_auroc": auc["pooled_block_auroc"],
            "healthy_pooled_spearman_block_score": method_speed.loc[
                "healthy_test", "pooled_spearman_block_score"
            ],
            "fault_pooled_spearman_block_score": method_speed.loc[
                "fault", "pooled_spearman_block_score"
            ],
        }
        for label, _ in HORIZONS:
            row[f"{label}_detection"] = horizons.loc[
                label, "fault_block_detection_rate"
            ]
            row[f"{label}_record_any"] = horizons.loc[
                label, "fault_record_any_alarm_rate"
            ]
            row[f"{label}_healthy_far"] = horizons.loc[
                label, "healthy_block_false_alarm_rate"
            ]
        rows.append(row)
    return pd.DataFrame(rows)


def interpretation_markdown(
    method_summary: pd.DataFrame,
    vs_proposed: pd.DataFrame,
    transfer: pd.DataFrame,
) -> str:
    """Render exact, bounded interpretation of the saved diagnostics."""

    proposed = method_summary.set_index("method").loc[PROPOSED]
    min_cov = method_summary.set_index("method").loc["target_min_cov_det"]
    min_cov_pair = vs_proposed[vs_proposed["candidate"].eq("target_min_cov_det")].iloc[0]
    transfer_pair = transfer[transfer["family"].eq("min_cov_det")].iloc[0]
    return f"""# Frozen External Failure Diagnostics

This is a post-reveal, analysis-only audit. No estimator was refit, no feature or
threshold was changed, and no diagnostic replaces the frozen primary endpoint.

## Exact findings

- Proposed block detection was {proposed['first_4_blocks_detection']:.4f} over the
  first four blocks, {proposed['first_7_blocks_detection']:.4f} over the first seven,
  and {proposed['all_8_blocks_detection']:.4f} over all eight. Record-any alarm rose
  from {proposed['first_4_blocks_record_any']:.4f} to
  {proposed['first_7_blocks_record_any']:.4f} and finally
  {proposed['all_8_blocks_record_any']:.4f}.
- Proposed's median first alarm was block {proposed['first_alarm_block_median']:.1f},
  approximately {proposed['first_alarm_approx_rpm_median']:.1f} rpm using the matching
  healthy load record. RPM is a proxy, not a measurement copied from a fault record.
- Proposed pooled AUROC was {proposed['pooled_block_auroc']:.4f}; the equal-weight mean
  of eight block-position-specific AUROCs was
  {proposed['equal_weight_mean_block_auroc']:.4f}. The latter shows fault information
  after matching acceleration position, but is exploratory.
- Proposed score drift was strong in both held-out health
  (Spearman block-score {proposed['healthy_pooled_spearman_block_score']:.4f}) and
  faults ({proposed['fault_pooled_spearman_block_score']:.4f}). Ordered blocks are
  dependent, so these correlations are descriptive.
- Target MinCovDet achieved {min_cov['all_8_blocks_detection']:.4f} detection and
  {min_cov['pooled_block_auroc']:.4f} AUROC. Its paired record advantage over Proposed
  was {min_cov_pair['method_a_minus_b_detection']:.4f}, with unadjusted bootstrap 95%
  interval [{min_cov_pair['bootstrap_ci_lower']:.4f},
  {min_cov_pair['bootstrap_ci_upper']:.4f}] and Holm-adjusted p
  {min_cov_pair['holm_adjusted_p']:.6f}.
- In the same-estimator MinCovDet contrast, target-only minus source+target detection
  was {transfer_pair['method_a_minus_b_detection']:.4f}, interval
  [{transfer_pair['bootstrap_ci_lower']:.4f},
  {transfer_pair['bootstrap_ci_upper']:.4f}]. This is evidence of conditional negative
  transfer on this motor, not a cross-motor population effect.

## Interpretation boundary

All 48 fault records are operating-condition records from one physical external motor.
The paired bootstrap resamples complete records within fault-turn strata and quantifies
variation conditional on this motor; it cannot create independent motors or prove
record independence. Holm adjustment controls only the listed family of post-reveal
method comparisons. Per-block AUROC, first-alarm RPM, and speed correlations diagnose
the frozen failure and must not be presented as new confirmatory endpoints.
"""


def write_outputs(
    output_dir: Path,
    *,
    validation_dir: Path,
    health_inventory: Path,
    checks: pd.DataFrame,
    horizon: pd.DataFrame,
    first_alarm: pd.DataFrame,
    first_summary: pd.DataFrame,
    first_distribution: pd.DataFrame,
    block_auroc: pd.DataFrame,
    auroc_summary: pd.DataFrame,
    speed_summary: pd.DataFrame,
    record_speed: pd.DataFrame,
    vs_proposed: pd.DataFrame,
    transfer: pd.DataFrame,
    method_summary: pd.DataFrame,
    iterations: int,
    seed: int,
) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    outputs = {
        "horizon_detection_record_any.csv": horizon,
        "first_alarm_by_record.csv": first_alarm,
        "first_alarm_summary.csv": first_summary,
        "first_alarm_distribution.csv": first_distribution,
        "block_auroc.csv": block_auroc,
        "block_auroc_summary.csv": auroc_summary,
        "score_speed_spearman.csv": speed_summary,
        "record_score_speed_spearman.csv": record_speed,
        "paired_vs_proposed.csv": vs_proposed,
        "target_vs_source_transfer.csv": transfer,
        "method_diagnostics_summary.csv": method_summary,
        "data_quality_checks.csv": checks,
    }
    for filename, frame in outputs.items():
        frame.to_csv(output_dir / filename, index=False)
    (output_dir / "INTERPRETATION.md").write_text(
        interpretation_markdown(method_summary, vs_proposed, transfer), encoding="utf-8"
    )
    input_paths = [
        validation_dir / "aggregate_summary.csv",
        health_inventory,
        *[
            validation_dir / method / "system_block_predictions.csv"
            for method in METHODS
        ],
        *[validation_dir / method / "fault_record_summary.csv" for method in METHODS],
    ]
    metadata = {
        "created_utc": datetime.now(UTC).isoformat(),
        "analysis_only": True,
        "models_refit": False,
        "thresholds_changed": False,
        "frozen_methods": list(METHODS),
        "proposed_method": PROPOSED,
        "external_physical_motors": 1,
        "fault_records": 48,
        "health_test_records": 4,
        "blocks_per_record": 8,
        "horizons": {label: list(range(stop)) for label, stop in HORIZONS},
        "bootstrap": {
            "unit": "complete fault record",
            "strata": "fault_turns",
            "iterations": iterations,
            "seed": seed,
            "ci": "unadjusted percentile 95% interval",
            "p_value": "two-sided centered paired-record bootstrap",
            "multiplicity": "Holm correction within each reported comparison family",
        },
        "rpm_proxy": (
            "Median/min/max RPM from the matching-load healthy record and block; "
            "not a fault-record RPM measurement."
        ),
        "inference_boundary": (
            "All intervals and comparisons are conditional on one external physical "
            "motor. Records and ordered blocks are not asserted independent."
        ),
        "inputs": [
            {
                "path": str(path.resolve()),
                "bytes": path.stat().st_size,
                "sha256": file_sha256(path),
            }
            for path in input_paths
        ],
    }
    (output_dir / "run_metadata.json").write_text(
        json.dumps(metadata, indent=2), encoding="utf-8"
    )


def main() -> None:
    args = parse_args()
    if args.bootstrap_iterations < 100:
        raise ValueError("bootstrap-iterations must be at least 100")
    _, blocks, records, checks = load_frozen_results(args.validation_dir)
    speed_map = load_speed_map(args.health_block_inventory)
    blocks = attach_approximate_speed(blocks, speed_map)

    horizon = horizon_diagnostics(blocks)
    first_alarm = first_alarm_records(blocks)
    first_summary, first_distribution = summarize_first_alarms(first_alarm)
    block_auroc, auroc_summary = block_auroc_diagnostics(blocks)
    speed_summary, record_speed = score_speed_diagnostics(blocks)
    vs_proposed = comparisons_vs_proposed(
        records,
        blocks,
        iterations=args.bootstrap_iterations,
        seed=args.seed,
    )
    transfer = target_vs_source_transfer(
        records,
        blocks,
        iterations=args.bootstrap_iterations,
        seed=args.seed,
    )
    method_summary = combined_method_summary(
        horizon, first_summary, auroc_summary, speed_summary
    )
    write_outputs(
        args.output_dir,
        validation_dir=args.validation_dir,
        health_inventory=args.health_block_inventory,
        checks=checks,
        horizon=horizon,
        first_alarm=first_alarm,
        first_summary=first_summary,
        first_distribution=first_distribution,
        block_auroc=block_auroc,
        auroc_summary=auroc_summary,
        speed_summary=speed_summary,
        record_speed=record_speed,
        vs_proposed=vs_proposed,
        transfer=transfer,
        method_summary=method_summary,
        iterations=args.bootstrap_iterations,
        seed=args.seed,
    )
    print(method_summary.to_string(index=False))


if __name__ == "__main__":
    main()
