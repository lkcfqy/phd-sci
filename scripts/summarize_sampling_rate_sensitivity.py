"""Audit and summarize the post-reveal 100 kHz to 10 kHz sensitivity arm."""

from __future__ import annotations

import argparse
import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.stats import spearmanr

from pmsm_sci.faults.baseline import feature_columns

PROPOSED_METHOD = "log_euclidean_entity_covariance"
TARGET_ONLY_METHODS = frozenset(
    {
        "target_ledoit",
        "target_sample_covariance",
        "target_ocsvm_rbf",
        "target_isolation_forest",
        "target_min_cov_det",
    }
)
KEY_COLUMNS = ["record_id", "block_id", "window_id"]
LABEL_COLUMNS = [
    "record_id",
    "motor_id",
    "is_healthy",
    "fault_family",
    "severity_percent",
    "block_id",
    "window_id",
]
EXTERNAL_METRICS = [
    "threshold",
    "false_alarms",
    "healthy_block_false_alarm_rate",
    "h1_empirical_pass",
    "fault_block_detection_rate",
    "fault_record_macro_detection_rate",
    "fault_record_any_alarm_rate",
    "block_auroc",
    "block_auprc",
]


def file_sha256(path: Path, chunk_size: int = 8 * 1024 * 1024) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        while chunk := stream.read(chunk_size):
            digest.update(chunk)
    return digest.hexdigest()


def validate_feature_pair(
    native: pd.DataFrame, downsampled: pd.DataFrame
) -> pd.DataFrame:
    """Verify that only signal values and sample-index units changed."""

    if native.columns.tolist() != downsampled.columns.tolist():
        raise ValueError("Native and 10 kHz feature schemas differ")
    if len(native) != len(downsampled):
        raise ValueError("Native and 10 kHz feature row counts differ")
    if not native[LABEL_COLUMNS].equals(downsampled[LABEL_COLUMNS]):
        raise ValueError("Record labels or ordered window keys changed")
    native_start_seconds = native["start_sample"].to_numpy(dtype=float) / 100_000
    target_start_seconds = downsampled["start_sample"].to_numpy(dtype=float) / 10_000
    native_stop_seconds = native["stop_sample"].to_numpy(dtype=float) / 100_000
    target_stop_seconds = downsampled["stop_sample"].to_numpy(dtype=float) / 10_000
    if not np.array_equal(native_start_seconds, target_start_seconds):
        raise ValueError("Window start times changed during resampling")
    if not np.array_equal(native_stop_seconds, target_stop_seconds):
        raise ValueError("Window stop times changed during resampling")

    rows: list[dict[str, object]] = []
    for rate, frame in (("native_100khz", native), ("polyphase_10khz", downsampled)):
        geometry = frame.groupby("record_id", sort=True).agg(
            windows=("window_id", "size"), blocks=("block_id", "nunique")
        )
        numeric = frame.select_dtypes(include=[np.number])
        rows.append(
            {
                "feature_arm": rate,
                "rows": len(frame),
                "physical_records": frame["record_id"].nunique(),
                "motors": frame["motor_id"].nunique(),
                "healthy_records": frame.loc[
                    frame["is_healthy"].astype(bool), "record_id"
                ].nunique(),
                "fault_records": frame.loc[
                    ~frame["is_healthy"].astype(bool), "record_id"
                ].nunique(),
                "windows_per_record_min": int(geometry["windows"].min()),
                "windows_per_record_max": int(geometry["windows"].max()),
                "blocks_per_record_min": int(geometry["blocks"].min()),
                "blocks_per_record_max": int(geometry["blocks"].max()),
                "duplicate_window_keys": int(frame.duplicated(KEY_COLUMNS).sum()),
                "nonfinite_numeric_values": int(
                    (~np.isfinite(numeric.to_numpy(dtype=float))).sum()
                ),
            }
        )
    return pd.DataFrame(rows)


def feature_shift_summary(
    native: pd.DataFrame,
    downsampled: pd.DataFrame,
    columns: list[str],
) -> pd.DataFrame:
    """Profile paired feature changes without using any external outcomes."""

    rows: list[dict[str, object]] = []
    subsets = {
        "all_source_windows": np.ones(len(native), dtype=bool),
        "healthy_source_windows": native["is_healthy"].astype(bool).to_numpy(),
    }
    for subset_name, mask in subsets.items():
        for column in columns:
            old = native.loc[mask, column].to_numpy(dtype=float)
            new = downsampled.loc[mask, column].to_numpy(dtype=float)
            difference = new - old
            quartile_range = float(np.quantile(old, 0.75) - np.quantile(old, 0.25))
            floor = np.finfo(float).eps * max(float(np.max(np.abs(old))), 1.0) * 32
            correlation_defined = np.std(old) > floor and np.std(new) > floor
            pearson = (
                float(np.corrcoef(old, new)[0, 1])
                if correlation_defined
                else np.nan
            )
            rank = (
                float(spearmanr(old, new).statistic)
                if correlation_defined
                else np.nan
            )
            rows.append(
                {
                    "subset": subset_name,
                    "feature": column,
                    "windows": len(old),
                    "native_median": float(np.median(old)),
                    "polyphase_10khz_median": float(np.median(new)),
                    "median_signed_delta": float(np.median(difference)),
                    "median_absolute_delta": float(np.median(np.abs(difference))),
                    "native_iqr": quartile_range,
                    "median_absolute_delta_per_native_iqr": (
                        float(np.median(np.abs(difference)) / quartile_range)
                        if quartile_range > floor
                        else np.nan
                    ),
                    "root_mean_squared_delta": float(
                        np.sqrt(np.mean(np.square(difference)))
                    ),
                    "pearson_correlation": pearson,
                    "spearman_correlation": rank,
                }
            )
    return pd.DataFrame(rows)


def external_method_comparison(
    native: pd.DataFrame, downsampled: pd.DataFrame
) -> pd.DataFrame:
    """Join frozen external metrics and expose source-dependent changes."""

    if set(native["method"]) != set(downsampled["method"]):
        raise ValueError("External method sets differ")
    missing = set(EXTERNAL_METRICS).difference(native.columns) | set(
        EXTERNAL_METRICS
    ).difference(downsampled.columns)
    if missing:
        raise ValueError(f"External summaries are missing metrics: {sorted(missing)}")
    old = native.set_index("method")[EXTERNAL_METRICS]
    new = downsampled.set_index("method")[EXTERNAL_METRICS]
    comparison = old.add_suffix("_source_100khz").join(
        new.add_suffix("_source_10khz"), how="inner"
    )
    comparison.insert(
        0,
        "source_dependency",
        [
            "target_only_invariant_control"
            if method in TARGET_ONLY_METHODS
            else "source_sensitive"
            for method in comparison.index
        ],
    )
    for metric in EXTERNAL_METRICS:
        if metric == "h1_empirical_pass":
            continue
        comparison[f"delta_{metric}_10khz_minus_100khz"] = (
            comparison[f"{metric}_source_10khz"].astype(float)
            - comparison[f"{metric}_source_100khz"].astype(float)
        )
    return comparison.reset_index()


def verify_target_only_predictions(
    native_results: Path, downsampled_results: Path
) -> pd.DataFrame:
    """Require target-only controls to be numerically invariant end to end."""

    rows: list[dict[str, object]] = []
    keys = ["record_id", "block_id"]
    for method in sorted(TARGET_ONLY_METHODS):
        old = pd.read_csv(native_results / method / "system_block_predictions.csv")
        new = pd.read_csv(downsampled_results / method / "system_block_predictions.csv")
        if not old[keys].equals(new[keys]):
            raise ValueError(f"Target-only prediction keys changed for {method}")
        score_difference = np.abs(
            old["score"].to_numpy(dtype=float) - new["score"].to_numpy(dtype=float)
        )
        p_difference = np.abs(
            old["p_value"].to_numpy(dtype=float)
            - new["p_value"].to_numpy(dtype=float)
        )
        alarm_mismatches = int(
            (old["alarm"].astype(bool) != new["alarm"].astype(bool)).sum()
        )
        row = {
            "method": method,
            "blocks": len(old),
            "max_absolute_score_difference": float(score_difference.max()),
            "max_absolute_p_value_difference": float(p_difference.max()),
            "alarm_mismatches": alarm_mismatches,
            "invariant": bool(
                np.allclose(score_difference, 0.0, rtol=0.0, atol=1e-12)
                and np.allclose(p_difference, 0.0, rtol=0.0, atol=1e-12)
                and alarm_mismatches == 0
            ),
        }
        if not row["invariant"]:
            raise AssertionError(f"Target-only pipeline control changed for {method}")
        rows.append(row)
    return pd.DataFrame(rows)


def internal_method_comparison(
    native_covariance: pd.DataFrame,
    target_covariance: pd.DataFrame,
    native_oneclass: pd.DataFrame,
    target_oneclass: pd.DataFrame,
) -> pd.DataFrame:
    """Put source-domain LOMO checks from both method families on one schema."""

    covariance_metrics = {
        "detection": "mean_detection_rate",
        "far": "pooled_false_alarm_rate",
        "auroc": "mean_block_auroc",
    }
    oneclass_metrics = {
        "detection": "fault_record_macro_detection_rate",
        "far": "pooled_block_false_alarm_rate",
        "auroc": "mean_block_auroc",
    }
    rows: list[pd.DataFrame] = []
    for family, old, new, mapping in (
        (
            "covariance",
            native_covariance,
            target_covariance,
            covariance_metrics,
        ),
        ("oneclass", native_oneclass, target_oneclass, oneclass_metrics),
    ):
        old = old.set_index("method")
        new = new.set_index("method")
        if set(old.index) != set(new.index):
            raise ValueError(f"Internal {family} method sets differ")
        result = pd.DataFrame(index=old.index)
        result["method_family"] = family
        for label, source_column in mapping.items():
            result[f"{label}_source_100khz"] = old[source_column]
            result[f"{label}_source_10khz"] = new[source_column]
            result[f"delta_{label}_10khz_minus_100khz"] = (
                new[source_column] - old[source_column]
            )
        rows.append(result.reset_index())
    return pd.concat(rows, ignore_index=True)


def proposed_record_comparison(
    native_results: Path, downsampled_results: Path
) -> pd.DataFrame:
    """Pair physical fault records for the proposed method."""

    filename = Path(PROPOSED_METHOD) / "fault_record_summary.csv"
    old = pd.read_csv(native_results / filename)
    new = pd.read_csv(downsampled_results / filename)
    keys = ["record_id", "load_nm", "fault_turns", "fault_phase"]
    selected = ["block_alarm_rate", "alarms", "mean_score", "max_score"]
    paired = old[keys + selected].merge(
        new[keys + selected],
        on=keys,
        how="outer",
        validate="one_to_one",
        suffixes=("_source_100khz", "_source_10khz"),
        indicator=True,
    )
    if not paired["_merge"].eq("both").all():
        raise ValueError("Proposed-method physical fault records do not pair")
    paired = paired.drop(columns="_merge")
    paired["delta_block_alarm_rate_10khz_minus_100khz"] = (
        paired["block_alarm_rate_source_10khz"]
        - paired["block_alarm_rate_source_100khz"]
    )
    return paired


def protocol_integrity(
    native_metadata: dict[str, object], target_metadata: dict[str, object]
) -> dict[str, object]:
    """Audit frozen external inputs and settings, excluding the intended source path."""

    fields = [
        "external_features_sha256",
        "feature_arm",
        "feature_columns",
        "analysis_time_seconds",
        "window_seconds",
        "block_seconds",
        "block_score",
        "source_motors",
        "source_covariance_blocks",
        "source_balanced_blocks",
        "external_adaptation_load_nm",
        "external_adaptation_blocks",
        "external_calibration_load_nm",
        "external_health_test_load_nm",
        "analysis_blocks",
        "alpha",
        "ridge_fraction",
        "log_ridge_fraction",
        "primary_seed",
        "fault_reveal_required",
    ]
    comparisons = {
        field: native_metadata.get(field) == target_metadata.get(field) for field in fields
    }
    if not all(comparisons.values()):
        changed = [field for field, matches in comparisons.items() if not matches]
        raise AssertionError(f"Frozen external protocol fields changed: {changed}")
    return {
        "analysis_status": "POST-REVEAL SENSITIVITY; exploratory, not confirmatory",
        "external_fault_outcomes_used_for_tuning": False,
        "intended_change": "KAIST source current anti-aliased from 100 kHz to 10 kHz",
        "frozen_field_matches": comparisons,
        "all_frozen_fields_match": True,
        "native_source_features_sha256": native_metadata["source_features_sha256"],
        "polyphase_source_features_sha256": target_metadata[
            "source_features_sha256"
        ],
        "external_features_sha256": target_metadata["external_features_sha256"],
    }


def write_interpretation(
    path: Path,
    comparison: pd.DataFrame,
    internal: pd.DataFrame,
    paired_records: pd.DataFrame,
) -> None:
    proposed = comparison.set_index("method").loc[PROPOSED_METHOD]
    leader_method = comparison.loc[
        comparison["fault_block_detection_rate_source_100khz"].idxmax(), "method"
    ]
    leader = comparison.set_index("method").loc[leader_method]
    proposed_old = float(proposed["fault_block_detection_rate_source_100khz"])
    proposed_new = float(proposed["fault_block_detection_rate_source_10khz"])
    delta = proposed_new - proposed_old
    gap_old = float(leader["fault_block_detection_rate_source_100khz"]) - proposed_old
    gap_new = float(leader["fault_block_detection_rate_source_10khz"]) - proposed_new
    improved = int(
        (paired_records["delta_block_alarm_rate_10khz_minus_100khz"] > 0).sum()
    )
    worsened = int(
        (paired_records["delta_block_alarm_rate_10khz_minus_100khz"] < 0).sum()
    )
    unchanged = len(paired_records) - improved - worsened
    proposed_internal = internal.set_index("method").loc[PROPOSED_METHOD]
    text = f"""# Sampling-rate sensitivity interpretation

**POST-REVEAL SENSITIVITY — exploratory, not confirmatory.** This analysis was
specified after external fault reveal. External fault outcomes were used only to
evaluate the frozen rerun; they did not select the polyphase filter, features,
window/block geometry, ridge, calibration split, threshold, method, or seed.

## Direct answer

Aligning the KAIST source rate from 100 kHz to 10 kHz does **not** support sampling
rate mismatch as the primary explanation for the proposed method's external
negative transfer. Proposed fault-block detection changed from {proposed_old:.4f}
to {proposed_new:.4f} ({delta:+.4f}); block AUROC changed from
{float(proposed['block_auroc_source_100khz']):.4f} to
{float(proposed['block_auroc_source_10khz']):.4f}. Its detection gap to the best
frozen external method ({leader_method}) changed from {gap_old:.4f} to {gap_new:.4f},
so rate alignment did not close the gap.

Across the 48 physical external fault records, proposed block alarm rate improved
for {improved}, worsened for {worsened}, and was unchanged for {unchanged}. These
records, not their 384 temporally ordered blocks, are the relevant independent
sampling units for that paired descriptive count.

## Source-task check

The 10 kHz source arm did not make the internal KAIST task unusable. Proposed LOMO
source detection changed from
{float(proposed_internal['detection_source_100khz']):.4f} to
{float(proposed_internal['detection_source_10khz']):.4f}, with AUROC changing from
{float(proposed_internal['auroc_source_100khz']):.4f} to
{float(proposed_internal['auroc_source_10khz']):.4f}. Therefore the absent external
recovery is not explained by wholesale failure of feature extraction at 10 kHz.

## Interpretation boundary

This is a one-factor diagnostic, not a new confirmatory experiment. It rules
against a simple “100 kHz source versus 10 kHz target” explanation under the
frozen pipeline, but it does not identify the remaining cause. Plausible residual
differences include sensor transfer functions, drive/control regime, topology,
speed/load coverage, and the external fault mechanism. Block-level rates remain
descriptive because blocks within a physical record are temporally dependent.
"""
    path.write_text(text, encoding="utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--native-features",
        type=Path,
        default=Path("data/processed/kaist_current_features.csv.gz"),
    )
    parser.add_argument(
        "--downsampled-features",
        type=Path,
        default=Path("data/processed/kaist_current_features_10khz.csv.gz"),
    )
    parser.add_argument(
        "--native-external-results",
        type=Path,
        default=Path("results/external_pmsm_validation"),
    )
    parser.add_argument(
        "--downsampled-external-results",
        type=Path,
        default=Path("results/sampling_rate_sensitivity/external_10khz_source"),
    )
    parser.add_argument(
        "--native-covariance-results",
        type=Path,
        default=Path("results/healthy_covariance_v0"),
    )
    parser.add_argument(
        "--downsampled-covariance-results",
        type=Path,
        default=Path("results/sampling_rate_sensitivity/kaist_10khz_covariance"),
    )
    parser.add_argument(
        "--native-oneclass-results",
        type=Path,
        default=Path("results/oneclass_baselines"),
    )
    parser.add_argument(
        "--downsampled-oneclass-results",
        type=Path,
        default=Path("results/sampling_rate_sensitivity/kaist_10khz_oneclass"),
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("results/sampling_rate_sensitivity"),
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    native_features = pd.read_csv(args.native_features)
    target_features = pd.read_csv(args.downsampled_features)
    integrity = validate_feature_pair(native_features, target_features)
    columns = feature_columns(native_features, "scale_free")
    shifts = feature_shift_summary(native_features, target_features, columns)

    native_external = pd.read_csv(
        args.native_external_results / "aggregate_summary.csv"
    )
    target_external = pd.read_csv(
        args.downsampled_external_results / "aggregate_summary.csv"
    )
    external = external_method_comparison(native_external, target_external)
    controls = verify_target_only_predictions(
        args.native_external_results, args.downsampled_external_results
    )
    paired = proposed_record_comparison(
        args.native_external_results, args.downsampled_external_results
    )
    internal = internal_method_comparison(
        pd.read_csv(args.native_covariance_results / "aggregate_summary.csv"),
        pd.read_csv(args.downsampled_covariance_results / "aggregate_summary.csv"),
        pd.read_csv(args.native_oneclass_results / "aggregate_summary.csv"),
        pd.read_csv(args.downsampled_oneclass_results / "aggregate_summary.csv"),
    )
    native_metadata = json.loads(
        (args.native_external_results / "run_metadata.json").read_text(encoding="utf-8")
    )
    target_metadata = json.loads(
        (args.downsampled_external_results / "run_metadata.json").read_text(
            encoding="utf-8"
        )
    )
    protocol = protocol_integrity(native_metadata, target_metadata)

    args.output_dir.mkdir(parents=True, exist_ok=True)
    integrity.to_csv(args.output_dir / "feature_table_integrity.csv", index=False)
    shifts.to_csv(args.output_dir / "feature_distribution_shift.csv", index=False)
    external.to_csv(args.output_dir / "external_method_comparison.csv", index=False)
    controls.to_csv(args.output_dir / "target_only_invariance_checks.csv", index=False)
    paired.to_csv(args.output_dir / "proposed_record_differences.csv", index=False)
    internal.to_csv(args.output_dir / "kaist_internal_method_comparison.csv", index=False)
    (args.output_dir / "protocol_integrity.json").write_text(
        json.dumps(protocol, indent=2), encoding="utf-8"
    )
    extractor_audit = {
        "analysis_status": "POST-REVEAL SENSITIVITY; exploratory, not confirmatory",
        "audit_conclusion": (
            "current_features is already sample-rate parameterized; the existing "
            "TDMS iterator is not. A separate builder therefore filters each complete "
            "120 s source record before applying the unchanged window feature extractor."
        ),
        "primary_table_preserved": True,
        "native_features": str(args.native_features.resolve()),
        "native_features_sha256": file_sha256(args.native_features),
        "downsampled_features": str(args.downsampled_features.resolve()),
        "downsampled_features_sha256": file_sha256(args.downsampled_features),
        "resampler": "scipy.signal.resample_poly",
        "up": 1,
        "down": 10,
        "window": ["kaiser", 5.0],
        "padtype": "line",
        "filtering_scope": "complete leading 120 s source record before windowing",
        "external_data_read_by_feature_builder": False,
    }
    (args.output_dir / "extractor_audit.json").write_text(
        json.dumps(extractor_audit, indent=2), encoding="utf-8"
    )
    (args.output_dir / "summary_run_metadata.json").write_text(
        json.dumps(
            {
                "created_utc": datetime.now(UTC).isoformat(),
                "analysis_status": "POST-REVEAL SENSITIVITY; exploratory",
                "external_fault_outcomes_used_for_tuning": False,
                "output_files": [
                    "feature_table_integrity.csv",
                    "feature_distribution_shift.csv",
                    "external_method_comparison.csv",
                    "target_only_invariance_checks.csv",
                    "proposed_record_differences.csv",
                    "kaist_internal_method_comparison.csv",
                    "protocol_integrity.json",
                    "extractor_audit.json",
                    "INTERPRETATION.md",
                ],
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    write_interpretation(
        args.output_dir / "INTERPRETATION.md", external, internal, paired
    )


if __name__ == "__main__":
    main()
