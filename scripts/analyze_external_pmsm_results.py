"""Analyze frozen external PMSM result tables without refitting or rethresholding."""

from __future__ import annotations

import argparse
import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path

import numpy as np
import pandas as pd

EXPECTED_METHODS = (
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
EXTERNAL_MOTOR_ID = "external_dual_three_phase"
EXPECTED_TURNS = tuple(range(1, 7))
EXPECTED_LOADS_NM = tuple(range(0, 36, 5))
BOOTSTRAP_ITERATIONS = 10_000
BOOTSTRAP_SEED = 711

BLOCK_REQUIRED = {
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
RECORD_REQUIRED = {
    "record_id",
    "load_nm",
    "fault_turns",
    "fault_phase",
    "blocks",
    "alarms",
    "block_alarm_rate",
    "mean_score",
    "max_score",
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--validation-dir",
        type=Path,
        default=Path("results/external_pmsm_validation"),
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("results/external_pmsm_analysis"),
    )
    parser.add_argument(
        "--bootstrap-iterations", type=int, default=BOOTSTRAP_ITERATIONS
    )
    parser.add_argument("--seed", type=int, default=BOOTSTRAP_SEED)
    return parser.parse_args()


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise ValueError(message)


def _boolean(series: pd.Series, name: str) -> pd.Series:
    if pd.api.types.is_bool_dtype(series):
        return series.astype(bool)
    normalized = series.astype(str).str.strip().str.lower()
    _require(set(normalized.unique()).issubset({"true", "false"}), f"Invalid {name}")
    return normalized.eq("true")


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        while chunk := stream.read(1024 * 1024):
            digest.update(chunk)
    return digest.hexdigest()


def stratified_record_bootstrap_draws(
    records: pd.DataFrame,
    *,
    value_column: str,
    strata_column: str = "fault_turns",
    iterations: int = BOOTSTRAP_ITERATIONS,
    seed: int = BOOTSTRAP_SEED,
) -> np.ndarray:
    """Resample complete records within every fault-turn stratum."""

    if iterations < 100:
        raise ValueError("iterations must be at least 100")
    missing = {value_column, strata_column}.difference(records.columns)
    if missing:
        raise ValueError(f"Bootstrap columns missing: {sorted(missing)}")
    groups = [
        group[value_column].to_numpy(dtype=np.float64)
        for _, group in records.groupby(strata_column, sort=True)
    ]
    if len(groups) != 6 or any(len(group) != 8 for group in groups):
        raise ValueError("Bootstrap requires six fault-turn strata of eight records")
    if any(not np.isfinite(group).all() for group in groups):
        raise ValueError("Bootstrap values must be finite")

    rng = np.random.default_rng(seed)
    draws = np.empty(iterations, dtype=np.float64)
    for index in range(iterations):
        sampled = [rng.choice(group, size=len(group), replace=True) for group in groups]
        draws[index] = np.concatenate(sampled).mean()
    return draws


def _recompute_fault_records(blocks: pd.DataFrame) -> pd.DataFrame:
    faults = blocks[blocks["role"].eq("fault_test")]
    return (
        faults.groupby(
            ["record_id", "load_nm", "fault_turns", "fault_phase"],
            observed=True,
            sort=True,
        )
        .agg(
            blocks=("alarm", "size"),
            alarms=("alarm", "sum"),
            block_alarm_rate=("alarm", "mean"),
            mean_score=("score", "mean"),
            max_score=("score", "max"),
        )
        .reset_index()
    )


def _validate_record_grid(records: pd.DataFrame, method: str) -> None:
    _require(len(records) == 48, f"{method}: expected 48 fault records")
    _require(records["record_id"].nunique() == 48, f"{method}: duplicate record IDs")
    _require(
        set(records["fault_turns"].astype(int)) == set(EXPECTED_TURNS),
        f"{method}: incomplete fault-turn strata",
    )
    _require(
        set(records["load_nm"].astype(int)) == set(EXPECTED_LOADS_NM),
        f"{method}: incomplete load levels",
    )
    grid = records.groupby(["fault_turns", "load_nm"], observed=True).size()
    _require(len(grid) == 48 and grid.eq(1).all(), f"{method}: turn-load grid is not 6x8")
    per_turn = records.groupby("fault_turns", observed=True).size()
    _require(per_turn.eq(8).all(), f"{method}: each turn must contain eight records")
    _require(
        records["record_id"].str.startswith(f"{EXTERNAL_MOTOR_ID}_").all(),
        f"{method}: record IDs do not belong to the frozen external motor",
    )


def load_and_validate_results(
    validation_dir: Path,
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, list[dict[str, object]]]:
    """Load all methods and verify grain, coverage, and saved-summary agreement."""

    summary_path = validation_dir / "aggregate_summary.csv"
    _require(summary_path.is_file(), f"Missing {summary_path}")
    source_summary = pd.read_csv(summary_path)
    _require(
        set(source_summary["method"]) == set(EXPECTED_METHODS)
        and len(source_summary) == len(EXPECTED_METHODS),
        "aggregate_summary.csv must contain exactly the 11 frozen methods",
    )
    _require(not source_summary["method"].duplicated().any(), "Duplicate summary method")

    checks: list[dict[str, object]] = [
        {
            "scope": "global",
            "check": "exact_method_coverage",
            "passed": True,
            "observed": len(source_summary),
            "expected": 11,
        }
    ]
    block_parts: list[pd.DataFrame] = []
    record_parts: list[pd.DataFrame] = []
    reference_block_metadata: pd.DataFrame | None = None
    reference_record_metadata: pd.DataFrame | None = None

    for method in EXPECTED_METHODS:
        method_dir = validation_dir / method
        block_path = method_dir / "system_block_predictions.csv"
        record_path = method_dir / "fault_record_summary.csv"
        _require(block_path.is_file(), f"Missing {block_path}")
        _require(record_path.is_file(), f"Missing {record_path}")
        blocks = pd.read_csv(block_path)
        records = pd.read_csv(record_path)
        missing_blocks = BLOCK_REQUIRED.difference(blocks.columns)
        missing_records = RECORD_REQUIRED.difference(records.columns)
        _require(not missing_blocks, f"{method}: missing block columns {missing_blocks}")
        _require(not missing_records, f"{method}: missing record columns {missing_records}")
        _require(len(blocks) == 448, f"{method}: expected 448 block rows")
        _require(blocks["record_id"].nunique() == 56, f"{method}: expected 56 records")
        _require(
            not blocks.duplicated(["record_id", "block_id"]).any(),
            f"{method}: duplicate record-block keys",
        )
        _require(
            blocks.groupby("record_id", observed=True).size().eq(8).all(),
            f"{method}: every record must contain eight blocks",
        )
        _require(set(blocks["block_id"].astype(int)) == set(range(8)), f"{method}: blocks")
        _require(blocks["method"].eq(method).all(), f"{method}: method column mismatch")
        blocks["is_healthy"] = _boolean(blocks["is_healthy"], "is_healthy")
        blocks["alarm"] = _boolean(blocks["alarm"], "alarm")
        _require(np.isfinite(blocks["score"]).all(), f"{method}: non-finite score")
        _require(np.isfinite(blocks["p_value"]).all(), f"{method}: non-finite p-value")

        role_counts = blocks["role"].value_counts().to_dict()
        expected_roles = {
            "fault_test": 384,
            "health_test": 32,
            "calibration": 24,
            "adaptation": 4,
            "unused": 4,
        }
        _require(role_counts == expected_roles, f"{method}: unexpected role counts")
        _require(
            blocks.loc[blocks["role"].eq("fault_test"), "is_healthy"].eq(False).all(),
            f"{method}: fault role contains healthy rows",
        )
        _require(
            blocks.loc[~blocks["role"].eq("fault_test"), "is_healthy"].all(),
            f"{method}: a health role contains fault rows",
        )

        _validate_record_grid(records, method)
        recomputed = _recompute_fault_records(blocks)
        comparison = records.merge(
            recomputed,
            on=["record_id", "load_nm", "fault_turns", "fault_phase"],
            suffixes=("_saved", "_recomputed"),
            validate="one_to_one",
        )
        _require(len(comparison) == 48, f"{method}: record-summary join lost rows")
        for column in ("blocks", "alarms", "block_alarm_rate", "mean_score", "max_score"):
            _require(
                np.allclose(
                    comparison[f"{column}_saved"],
                    comparison[f"{column}_recomputed"],
                    rtol=1e-12,
                    atol=1e-12,
                ),
                f"{method}: saved {column} does not reconcile to blocks",
            )

        source_row = source_summary[source_summary["method"].eq(method)].iloc[0]
        health_test = blocks[blocks["role"].eq("health_test")]
        faults = blocks[blocks["role"].eq("fault_test")]
        high_impact = {
            "false_alarms": int(health_test["alarm"].sum()),
            "healthy_block_false_alarm_rate": float(health_test["alarm"].mean()),
            "fault_records": int(faults["record_id"].nunique()),
            "fault_blocks": len(faults),
            "fault_block_detection_rate": float(faults["alarm"].mean()),
            "fault_record_macro_detection_rate": float(records["block_alarm_rate"].mean()),
            "fault_record_any_alarm_rate": float((records["alarms"] > 0).mean()),
        }
        for column, value in high_impact.items():
            _require(
                np.isclose(float(source_row[column]), value, rtol=1e-12, atol=1e-12),
                f"{method}: aggregate {column} does not reconcile",
            )

        block_metadata = blocks[
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
        record_metadata = records[
            ["record_id", "load_nm", "fault_turns", "fault_phase"]
        ].sort_values("record_id", ignore_index=True)
        if reference_block_metadata is None:
            reference_block_metadata = block_metadata
            reference_record_metadata = record_metadata
        else:
            _require(
                block_metadata.equals(reference_block_metadata),
                f"{method}: block populations differ across methods",
            )
            _require(
                record_metadata.equals(reference_record_metadata),
                f"{method}: fault-record populations differ across methods",
            )

        blocks = blocks.copy()
        records = records.copy()
        blocks["external_motor_id"] = EXTERNAL_MOTOR_ID
        records["external_motor_id"] = EXTERNAL_MOTOR_ID
        record_parts.append(records.assign(method=method))
        block_parts.append(blocks)
        checks.extend(
            [
                {
                    "scope": method,
                    "check": "unique_record_block_grain",
                    "passed": True,
                    "observed": len(blocks),
                    "expected": 448,
                },
                {
                    "scope": method,
                    "check": "complete_fault_turn_load_grid",
                    "passed": True,
                    "observed": len(records),
                    "expected": 48,
                },
                {
                    "scope": method,
                    "check": "record_and_aggregate_reconciliation",
                    "passed": True,
                    "observed": "all high-impact metrics match",
                    "expected": "exact/allclose",
                },
            ]
        )

    combined_blocks = pd.concat(block_parts, ignore_index=True)
    combined_records = pd.concat(record_parts, ignore_index=True)
    return source_summary, combined_blocks, combined_records, checks


def build_method_summary(
    source_summary: pd.DataFrame,
    records: pd.DataFrame,
    *,
    iterations: int,
    seed: int,
) -> pd.DataFrame:
    """Create the 11-method summary with record-level bootstrap intervals."""

    rows: list[dict[str, object]] = []
    source_by_method = source_summary.set_index("method")
    for method in EXPECTED_METHODS:
        method_records = records[records["method"].eq(method)]
        draws = stratified_record_bootstrap_draws(
            method_records,
            value_column="block_alarm_rate",
            iterations=iterations,
            seed=seed,
        )
        row = source_by_method.loc[method].to_dict()
        row.update(
            {
                "method": method,
                "external_motor_id": EXTERNAL_MOTOR_ID,
                "independent_external_motors": 1,
                "bootstrap_unit": "complete_fault_record",
                "bootstrap_strata": "fault_turns (6 strata, 8 records each)",
                "bootstrap_iterations": iterations,
                "bootstrap_seed": seed,
                "recomputed_record_ci_lower": float(np.quantile(draws, 0.025)),
                "recomputed_record_ci_upper": float(np.quantile(draws, 0.975)),
            }
        )
        rows.append(row)
    return pd.DataFrame(rows)


def paired_proposed_comparisons(
    blocks: pd.DataFrame,
    records: pd.DataFrame,
    *,
    iterations: int,
    seed: int,
) -> pd.DataFrame:
    """Compare Proposed with every baseline at the paired-record level."""

    proposed = records[records["method"].eq(PROPOSED)][
        ["record_id", "load_nm", "fault_turns", "fault_phase", "block_alarm_rate"]
    ].rename(columns={"block_alarm_rate": "proposed_detection_rate"})
    proposed_health = blocks[
        blocks["method"].eq(PROPOSED) & blocks["role"].eq("health_test")
    ]
    available_methods = set(records["method"].astype(str))
    _require(PROPOSED in available_methods, "Proposed records are missing")
    rows: list[dict[str, object]] = []
    for baseline in EXPECTED_METHODS:
        if baseline == PROPOSED or baseline not in available_methods:
            continue
        baseline_records = records[records["method"].eq(baseline)][
            ["record_id", "load_nm", "fault_turns", "fault_phase", "block_alarm_rate"]
        ].rename(columns={"block_alarm_rate": "baseline_detection_rate"})
        paired = proposed.merge(
            baseline_records,
            on=["record_id", "load_nm", "fault_turns", "fault_phase"],
            validate="one_to_one",
        )
        _require(len(paired) == 48, f"{baseline}: paired join must retain 48 records")
        paired["difference"] = (
            paired["proposed_detection_rate"] - paired["baseline_detection_rate"]
        )
        draws = stratified_record_bootstrap_draws(
            paired,
            value_column="difference",
            iterations=iterations,
            seed=seed,
        )
        baseline_health = blocks[
            blocks["method"].eq(baseline) & blocks["role"].eq("health_test")
        ]
        rows.append(
            {
                "proposed": PROPOSED,
                "baseline": baseline,
                "external_motor_id": EXTERNAL_MOTOR_ID,
                "independent_external_motors": 1,
                "paired_fault_records": len(paired),
                "fault_turn_strata": paired["fault_turns"].nunique(),
                "records_per_stratum": 8,
                "proposed_record_macro_detection": float(
                    paired["proposed_detection_rate"].mean()
                ),
                "baseline_record_macro_detection": float(
                    paired["baseline_detection_rate"].mean()
                ),
                "proposed_minus_baseline_detection": float(paired["difference"].mean()),
                "paired_bootstrap_ci_lower": float(np.quantile(draws, 0.025)),
                "paired_bootstrap_ci_upper": float(np.quantile(draws, 0.975)),
                "bootstrap_probability_proposed_better": float(np.mean(draws > 0)),
                "records_proposed_better": int((paired["difference"] > 0).sum()),
                "records_tied": int(paired["difference"].eq(0).sum()),
                "records_baseline_better": int((paired["difference"] < 0).sum()),
                "proposed_health_false_alarms": int(proposed_health["alarm"].sum()),
                "baseline_health_false_alarms": int(baseline_health["alarm"].sum()),
                "health_test_blocks_each": len(proposed_health),
                "bootstrap_iterations": iterations,
                "bootstrap_seed": seed,
                "ci_multiplicity_adjusted": False,
            }
        )
    return pd.DataFrame(rows)


def proposed_turn_load_tables(
    records: pd.DataFrame,
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """Return complete Proposed turn-by-load and marginal detection tables."""

    proposed = records[records["method"].eq(PROPOSED)].copy()
    _validate_record_grid(proposed, PROPOSED)
    columns = [
        "external_motor_id",
        "fault_turns",
        "fault_phase",
        "load_nm",
        "record_id",
        "blocks",
        "alarms",
        "block_alarm_rate",
        "mean_score",
        "max_score",
    ]
    turn_load = proposed[columns].rename(
        columns={"block_alarm_rate": "detection_rate"}
    ).sort_values(["fault_turns", "load_nm"], ignore_index=True)
    matrix = turn_load.pivot(
        index=["fault_turns", "fault_phase"],
        columns="load_nm",
        values="detection_rate",
    ).reset_index()
    matrix.columns = [
        str(column) if isinstance(column, str) else f"load_{int(column)}Nm"
        for column in matrix.columns
    ]
    turn_summary = (
        proposed.groupby(["fault_turns", "fault_phase"], observed=True, sort=True)
        .agg(
            load_conditions=("load_nm", "nunique"),
            records=("record_id", "nunique"),
            blocks=("blocks", "sum"),
            alarms=("alarms", "sum"),
            detection_rate=("block_alarm_rate", "mean"),
            records_with_any_alarm=("alarms", lambda values: int((values > 0).sum())),
            mean_record_score=("mean_score", "mean"),
        )
        .reset_index()
    )
    load_summary = (
        proposed.groupby("load_nm", observed=True, sort=True)
        .agg(
            fault_turn_levels=("fault_turns", "nunique"),
            records=("record_id", "nunique"),
            blocks=("blocks", "sum"),
            alarms=("alarms", "sum"),
            detection_rate=("block_alarm_rate", "mean"),
            records_with_any_alarm=("alarms", lambda values: int((values > 0).sum())),
            mean_record_score=("mean_score", "mean"),
        )
        .reset_index()
    )
    return turn_load, matrix, turn_summary, load_summary


def block_id_score_alarm_summary(blocks: pd.DataFrame) -> pd.DataFrame:
    """Summarize alarms and raw scores by within-record block position."""

    parts: list[pd.DataFrame] = []
    populations = {
        "fault": blocks["role"].eq("fault_test"),
        "healthy_test": blocks["role"].eq("health_test"),
        "healthy_all": blocks["is_healthy"].astype(bool),
    }
    for population, mask in populations.items():
        selected = blocks[mask].copy()
        selected["population"] = population
        parts.append(selected)
    working = pd.concat(parts, ignore_index=True)
    summary = (
        working.groupby(["method", "population", "block_id"], observed=True, sort=True)
        .agg(
            external_motor_count=("external_motor_id", "nunique"),
            records=("record_id", "nunique"),
            blocks=("record_id", "size"),
            alarms=("alarm", "sum"),
            alarm_rate=("alarm", "mean"),
            score_mean=("score", "mean"),
            score_std=("score", "std"),
            score_min=("score", "min"),
            score_q25=("score", lambda values: values.quantile(0.25)),
            score_median=("score", "median"),
            score_q75=("score", lambda values: values.quantile(0.75)),
            score_max=("score", "max"),
        )
        .reset_index()
    )
    return summary


def input_manifest(validation_dir: Path) -> pd.DataFrame:
    paths = [
        validation_dir / "aggregate_summary.csv",
        validation_dir / "run_metadata.json",
    ]
    for method in EXPECTED_METHODS:
        paths.extend(
            [
                validation_dir / method / "system_block_predictions.csv",
                validation_dir / method / "fault_record_summary.csv",
                validation_dir / method / "summary.json",
            ]
        )
    return pd.DataFrame(
        [
            {
                "path": str(path.resolve()),
                "bytes": path.stat().st_size,
                "sha256": _sha256(path),
            }
            for path in paths
        ]
    )


def main() -> None:
    args = parse_args()
    if args.bootstrap_iterations < 100:
        raise ValueError("bootstrap-iterations must be at least 100")
    source_summary, blocks, records, checks = load_and_validate_results(
        args.validation_dir
    )
    method_summary = build_method_summary(
        source_summary,
        records,
        iterations=args.bootstrap_iterations,
        seed=args.seed,
    )
    paired = paired_proposed_comparisons(
        blocks,
        records,
        iterations=args.bootstrap_iterations,
        seed=args.seed,
    )
    turn_load, turn_load_matrix, turn_summary, load_summary = proposed_turn_load_tables(
        records
    )
    block_summary = block_id_score_alarm_summary(blocks)

    args.output_dir.mkdir(parents=True, exist_ok=True)
    method_summary.to_csv(args.output_dir / "method_summary.csv", index=False)
    paired.to_csv(args.output_dir / "proposed_paired_record_comparisons.csv", index=False)
    turn_load.to_csv(args.output_dir / "proposed_turn_by_load.csv", index=False)
    turn_load_matrix.to_csv(
        args.output_dir / "proposed_turn_by_load_matrix.csv", index=False
    )
    turn_summary.to_csv(args.output_dir / "proposed_turn_summary.csv", index=False)
    load_summary.to_csv(args.output_dir / "proposed_load_summary.csv", index=False)
    block_summary.to_csv(args.output_dir / "block_id_score_alarm_summary.csv", index=False)
    block_summary[block_summary["method"].eq(PROPOSED)].to_csv(
        args.output_dir / "proposed_block_id_score_alarm_summary.csv", index=False
    )
    pd.DataFrame(checks).to_csv(args.output_dir / "data_quality_checks.csv", index=False)
    input_manifest(args.validation_dir).to_csv(
        args.output_dir / "input_manifest.csv", index=False
    )

    metadata = {
        "created_utc": datetime.now(UTC).isoformat(),
        "source_validation_dir": str(args.validation_dir.resolve()),
        "analysis_only": True,
        "models_refit": False,
        "thresholds_changed": False,
        "methods": list(EXPECTED_METHODS),
        "method_count": len(EXPECTED_METHODS),
        "proposed_method": PROPOSED,
        "external_motor_id": EXTERNAL_MOTOR_ID,
        "independent_external_motor_count": 1,
        "fault_records": 48,
        "blocks_per_fault_record": 8,
        "fault_turn_strata": list(EXPECTED_TURNS),
        "records_per_fault_turn": 8,
        "loads_nm": list(EXPECTED_LOADS_NM),
        "paired_bootstrap": {
            "unit": "complete fault record",
            "stratification": "fault_turns",
            "iterations": args.bootstrap_iterations,
            "seed": args.seed,
            "interval": "unadjusted percentile 95% CI",
        },
        "data_validation": {
            "assessment": "Share with caveats",
            "checks_passed": len(checks),
            "checks_failed": 0,
            "record_block_key_unique": True,
            "method_populations_identical": True,
            "saved_record_and_aggregate_metrics_reconciled": True,
        },
        "inference_boundary": (
            "All 48 fault records are operating-condition records from one physical "
            "external dual-three-phase PMSM, not 48 independent motors. Bootstrap "
            "intervals quantify record variation conditional on this motor and the six "
            "observed fault-turn strata; they do not support a cross-motor population "
            "claim or prove record independence."
        ),
        "design_caveat": (
            "Fault phase and fault turns are confounded by the available file design; "
            "no independent phase-effect inference is made."
        ),
        "score_caveat": (
            "Raw score scales are method-specific. Score summaries are suitable for "
            "within-method block-position diagnosis, not direct cross-method magnitude "
            "comparison."
        ),
    }
    (args.output_dir / "analysis_metadata.json").write_text(
        json.dumps(metadata, indent=2), encoding="utf-8"
    )

    print(method_summary.to_string(index=False))
    print("\nPaired Proposed comparisons:\n")
    print(paired.to_string(index=False))


if __name__ == "__main__":
    main()
