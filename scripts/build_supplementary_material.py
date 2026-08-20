"""Build the submission supplementary material from frozen result artifacts."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

import pandas as pd

PROPOSED = "log_euclidean_entity_covariance"
METHOD_ORDER = (
    "target_ledoit",
    "target_sample_covariance",
    "source_covariance",
    "entity_balanced_covariance",
    PROPOSED,
    "target_ocsvm_rbf",
    "source_target_ocsvm_rbf",
    "target_isolation_forest",
    "source_target_isolation_forest",
    "target_min_cov_det",
    "source_target_min_cov_det",
)
TRANSIENT_METHOD_ORDER = (
    "target_ledoit",
    "target_sample_covariance",
    "target_log_covariance",
    "source_covariance",
    "entity_balanced_covariance",
    PROPOSED,
    "target_ocsvm_rbf",
    "source_target_ocsvm_rbf",
    "target_isolation_forest",
    "source_target_isolation_forest",
    "target_min_cov_det",
    "source_target_min_cov_det",
)
METHOD_LABELS = {
    "target_ledoit": "Target Ledoit–Wolf",
    "target_sample_covariance": "Target sample covariance",
    "target_log_covariance": "Target Log-Euclidean covariance",
    "source_covariance": "Source covariance",
    "entity_balanced_covariance": "Entity-balanced covariance",
    PROPOSED: "Proposed: Log-Euclidean entity covariance",
    "target_ocsvm_rbf": "Target OC-SVM (RBF)",
    "source_target_ocsvm_rbf": "Source+target OC-SVM (RBF)",
    "target_isolation_forest": "Target Isolation Forest",
    "source_target_isolation_forest": "Source+target Isolation Forest",
    "target_min_cov_det": "Target MinCovDet",
    "source_target_min_cov_det": "Source+target MinCovDet",
}
METHOD_SCOPES = {
    "target_ledoit": "target adaptation",
    "target_sample_covariance": "target adaptation",
    "source_covariance": "source healthy",
    "entity_balanced_covariance": "source entities + target",
    PROPOSED: "source entities + target",
    "target_ocsvm_rbf": "target adaptation",
    "source_target_ocsvm_rbf": "source-balanced + target",
    "target_isolation_forest": "target adaptation",
    "source_target_isolation_forest": "source-balanced + target",
    "target_min_cov_det": "target adaptation",
    "source_target_min_cov_det": "source-balanced + target",
}
TARGET_ONLY_METHODS = {
    "target_ledoit",
    "target_sample_covariance",
    "target_ocsvm_rbf",
    "target_isolation_forest",
    "target_min_cov_det",
}


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def file_sha256(path: Path, chunk_size: int = 8 * 1024 * 1024) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        while chunk := stream.read(chunk_size):
            digest.update(chunk)
    return digest.hexdigest()


def read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def escape_cell(value: object) -> str:
    return str(value).replace("|", "\\|").replace("\n", " ")


def markdown_table(headers: list[str], rows: list[list[object]]) -> str:
    if not rows:
        raise ValueError("A supplementary table cannot be empty")
    if any(len(row) != len(headers) for row in rows):
        raise ValueError("Supplementary table rows do not match the header")
    header = "| " + " | ".join(escape_cell(value) for value in headers) + " |"
    divider = "| " + " | ".join("---" for _ in headers) + " |"
    body = [
        "| " + " | ".join(escape_cell(value) for value in row) + " |"
        for row in rows
    ]
    return "\n".join([header, divider, *body])


def percent(value: float, digits: int = 2) -> str:
    return f"{100 * float(value):.{digits}f}"


def percentage_points(value: float, digits: int = 2) -> str:
    return f"{100 * float(value):+.{digits}f}"


def compact_float(value: float) -> str:
    return f"{float(value):.6g}"


def p_value(value: float) -> str:
    return f"{float(value):.4f}"


def method_label(method: object) -> str:
    key = str(method)
    if key not in METHOD_LABELS:
        raise KeyError(f"Unknown frozen method: {key}")
    return METHOD_LABELS[key]


def load_sources(root: Path) -> dict[str, Any]:
    csv_paths = {
        "external": "results/external_pmsm_validation/aggregate_summary.csv",
        "horizons": "results/external_failure_diagnostics/horizon_detection_record_any.csv",
        "first_alarm": "results/external_failure_diagnostics/first_alarm_summary.csv",
        "block_auroc": "results/external_failure_diagnostics/block_auroc.csv",
        "block_auroc_summary": "results/external_failure_diagnostics/block_auroc_summary.csv",
        "paired": "results/external_failure_diagnostics/paired_vs_proposed.csv",
        "transfer": "results/external_failure_diagnostics/target_vs_source_transfer.csv",
        "seed_ranges": "results/external_seed_sensitivity/aggregate_seed_ranges.csv",
        "seed_reconciliation": (
            "results/external_seed_sensitivity/primary_seed_reconciliation.csv"
        ),
        "drift": "results/external_feature_drift/feature_diagnostic_summary.csv",
        "geometry": "results/external_feature_drift/geometry_reconstruction.csv",
        "reconstruction": "results/external_feature_drift/score_reconstruction_checks.csv",
        "sampling": "results/sampling_rate_sensitivity/external_method_comparison.csv",
        "sampling_integrity": (
            "results/sampling_rate_sensitivity/feature_table_integrity.csv"
        ),
        "sampling_controls": (
            "results/sampling_rate_sensitivity/target_only_invariance_checks.csv"
        ),
        "sampling_internal": (
            "results/sampling_rate_sensitivity/kaist_internal_method_comparison.csv"
        ),
        "sampling_records": (
            "results/sampling_rate_sensitivity/proposed_record_differences.csv"
        ),
        "transient_compatibility_primary": (
            "results/transient_feature_build/record_compatibility.csv"
        ),
        "transient_compatibility_post": (
            "results/transient_feature_build_post_reveal_implicit_time/"
            "record_compatibility.csv"
        ),
        "transient_aggregate": (
            "results/transient_pmsm_validation_post_reveal_200w/"
            "aggregate_summary.csv"
        ),
        "transient_per_record": (
            "results/transient_pmsm_validation_post_reveal_200w/"
            "per_record_summary.csv"
        ),
        "transient_predictions": (
            "results/transient_pmsm_validation_post_reveal_200w/"
            "window_predictions.csv.gz"
        ),
    }
    json_paths = {
        "external_metadata": "results/external_pmsm_validation/run_metadata.json",
        "diagnostic_metadata": "results/external_failure_diagnostics/run_metadata.json",
        "seed_metadata": "results/external_seed_sensitivity/run_metadata.json",
        "drift_metadata": "results/external_feature_drift/run_metadata.json",
        "sampling_protocol": "results/sampling_rate_sensitivity/protocol_integrity.json",
        "sampling_extractor": "results/sampling_rate_sensitivity/extractor_audit.json",
        "transient_primary_metadata": (
            "results/transient_feature_build/run_metadata.json"
        ),
        "transient_post_metadata": (
            "results/transient_feature_build_post_reveal_implicit_time/"
            "run_metadata.json"
        ),
        "transient_validation_metadata": (
            "results/transient_pmsm_validation_post_reveal_200w/run_metadata.json"
        ),
    }
    sources: dict[str, Any] = {
        name: pd.read_csv(root / relative) for name, relative in csv_paths.items()
    }
    sources.update(
        {name: read_json(root / relative) for name, relative in json_paths.items()}
    )
    sources["source_features"] = pd.read_csv(
        root / "data/processed/kaist_current_features.csv.gz"
    )
    sources["external_features"] = pd.read_csv(
        root / "data/processed/external_dual_three_phase_health_features.csv.gz"
    )
    sources["csv_paths"] = csv_paths
    sources["json_paths"] = json_paths
    return sources


def validate_sources(root: Path, sources: dict[str, Any]) -> None:
    external = sources["external"]
    _require(len(external) == 11, "External summary must contain eleven methods")
    _require(
        tuple(external["method"].astype(str)) == METHOD_ORDER,
        "External methods or their frozen order changed",
    )
    _require(
        external["calibration_blocks"].eq(24).all()
        and external["health_test_blocks"].eq(32).all()
        and external["fault_records"].eq(48).all()
        and external["fault_blocks"].eq(384).all(),
        "External denominators changed",
    )

    source = sources["source_features"]
    target = sources["external_features"]
    _require(
        (len(source), source["record_id"].nunique()) == (27_000, 45),
        "KAIST feature-table grain changed",
    )
    _require(
        source.loc[source["is_healthy"].astype(bool), "record_id"].nunique() == 3
        and source.loc[~source["is_healthy"].astype(bool), "record_id"].nunique()
        == 42,
        "KAIST health/fault record counts changed",
    )
    _require(
        (len(target), target["record_id"].nunique(), target["subsystem"].nunique())
        == (13_440, 56, 2),
        "External feature-table grain changed",
    )
    _require(
        target.loc[target["is_healthy"].astype(bool), "record_id"].nunique() == 8
        and target.loc[~target["is_healthy"].astype(bool), "record_id"].nunique()
        == 48,
        "External health/fault record counts changed",
    )

    _require(len(sources["horizons"]) == 33, "Horizon table must be 11 x 3")
    _require(len(sources["first_alarm"]) == 11, "First-alarm table changed")
    _require(len(sources["block_auroc"]) == 88, "Block AUROC table must be 11 x 8")
    _require(len(sources["paired"]) == 10, "Paired-vs-Proposed family changed")
    _require(
        sources["paired"]["holm_family_size"].eq(10).all()
        and sources["paired"]["paired_fault_records"].eq(48).all(),
        "Paired-vs-Proposed multiplicity or record denominator changed",
    )
    _require(len(sources["transfer"]) == 5, "Target/source transfer family changed")
    _require(
        sources["transfer"]["holm_family_size"].eq(5).all()
        and sources["transfer"]["paired_fault_records"].eq(48).all(),
        "Target/source multiplicity or record denominator changed",
    )
    for comparison in (sources["paired"], sources["transfer"]):
        _require(
            comparison["independent_external_motors"].eq(1).all()
            and ~comparison["cross_motor_inference_valid"].astype(bool).any(),
            "A single-motor paired diagnostic was promoted to cross-motor inference",
        )

    _require(
        len(sources["seed_ranges"]) == 4
        and sources["seed_ranges"]["seeds"].eq(5).all(),
        "Five-seed sensitivity dimensions changed",
    )
    _require(
        len(sources["seed_reconciliation"]) == 4
        and sources["seed_reconciliation"]["passed"].astype(bool).all(),
        "Primary stochastic seed no longer reconciles",
    )
    _require(
        len(sources["geometry"]) == 2
        and sources["geometry"]["features"].eq(27).all()
        and sources["geometry"]["center_matches_frozen"].astype(bool).all()
        and sources["geometry"]["scale_matches_frozen"].astype(bool).all(),
        "Frozen geometry reconstruction changed",
    )
    _require(len(sources["reconstruction"]) == 448, "Reconstruction grain changed")
    _require(
        sources["reconstruction"]["frozen_score_error"].abs().max() < 1e-9,
        "Reconstructed scores no longer match frozen scores",
    )
    _require(len(sources["drift"]) == 27, "Feature diagnostic must contain 27 features")

    sampling = sources["sampling"]
    _require(
        set(sampling["method"].astype(str)) == set(METHOD_ORDER),
        "Sampling-rate method set changed",
    )
    _require(
        len(sources["sampling_controls"]) == 5
        and sources["sampling_controls"]["invariant"].astype(bool).all()
        and sources["sampling_controls"]["alarm_mismatches"].eq(0).all(),
        "Target-only sampling controls are no longer invariant",
    )
    _require(
        sources["sampling_protocol"]["all_frozen_fields_match"] is True
        and not sources["sampling_protocol"][
            "external_fault_outcomes_used_for_tuning"
        ],
        "Sampling sensitivity violated its frozen-protocol boundary",
    )

    external_metadata = sources["external_metadata"]
    source_path = root / "data/processed/kaist_current_features.csv.gz"
    external_path = (
        root / "data/processed/external_dual_three_phase_health_features.csv.gz"
    )
    _require(
        file_sha256(source_path) == external_metadata["source_features_sha256"],
        "KAIST input hash differs from the frozen validation metadata",
    )
    _require(
        file_sha256(external_path) == external_metadata["external_features_sha256"],
        "External input hash differs from the frozen validation metadata",
    )
    diagnostic_metadata = sources["diagnostic_metadata"]
    _require(
        diagnostic_metadata["analysis_only"]
        and not diagnostic_metadata["models_refit"]
        and not diagnostic_metadata["thresholds_changed"],
        "Failure diagnostics unexpectedly changed a model or threshold",
    )
    _require(
        sources["drift_metadata"]["new_model_fitted"] is False
        and sources["drift_metadata"]["threshold_changed_or_recomputed"] is False,
        "Feature drift unexpectedly changed a model or threshold",
    )
    _require(
        sources["seed_metadata"]["not_for_model_or_protocol_selection"] is True,
        "Seed sensitivity was used for model selection",
    )

    transient_primary = sources["transient_compatibility_primary"]
    transient_post = sources["transient_compatibility_post"]
    _require(
        len(transient_primary) == 21
        and transient_primary.groupby("motor_id").size().to_dict()
        == {"200W": 12, "20kW": 9}
        and not transient_primary["main_endpoint_compatible"].astype(bool).any(),
        "Frozen transient parser outcome changed",
    )
    _require(
        transient_primary["incompatible_reason"].eq(
            "ValueError: timeseries has no 10 kHz monotonic time candidate"
        ).all(),
        "Frozen transient parser failure reason changed",
    )
    post_counts = (
        transient_post.groupby(["motor_id", "main_endpoint_compatible"])
        .size()
        .to_dict()
    )
    _require(
        len(transient_post) == 21
        and post_counts == {("200W", True): 12, ("20kW", False): 5, ("20kW", True): 4},
        "Post-reveal transient compatibility changed",
    )
    rejected_20kw = transient_post.loc[
        (transient_post["motor_id"] == "20kW")
        & ~transient_post["main_endpoint_compatible"].astype(bool)
    ]
    _require(
        rejected_20kw["incompatible_reason"].eq(
            "ValueError: detected onset overlaps the frozen baseline interval"
        ).all(),
        "20 kW transient baseline-gate failure changed",
    )

    primary_metadata = sources["transient_primary_metadata"]
    post_metadata = sources["transient_post_metadata"]
    validation_metadata = sources["transient_validation_metadata"]
    _require(
        primary_metadata["records_attempted"] == 21
        and primary_metadata["records_main_endpoint_compatible"] == 0
        and primary_metadata["feature_rows"] == 0,
        "Frozen transient primary metadata changed",
    )
    _require(
        post_metadata["records_attempted"] == 21
        and post_metadata["records_main_endpoint_compatible"] == 16
        and post_metadata["feature_rows"] == 384
        and post_metadata["status"] == "post_reveal_sensitivity_not_primary_reveal"
        and post_metadata["main_endpoint_compatible_fraction_by_motor"]
        == {"200W": 1.0, "20kW": 4 / 9},
        "Post-reveal transient metadata changed",
    )
    transient_feature_path = (
        root
        / "data/processed/transient_pmsm_features_post_reveal_implicit_time.csv.gz"
    )
    _require(
        file_sha256(transient_feature_path) == post_metadata["feature_table_sha256"]
        == validation_metadata["target_features_sha256"],
        "Post-reveal transient feature hash changed",
    )

    transient = sources["transient_aggregate"]
    primary_seed = int(validation_metadata["primary_seed"])
    transient_primary_seed = transient.loc[transient["seed"] == primary_seed].copy()
    _require(
        len(transient_primary_seed) == 12
        and set(transient_primary_seed["method"].astype(str))
        == set(TRANSIENT_METHOD_ORDER),
        "Transient method family changed",
    )
    _require(
        transient_primary_seed["records"].eq(12).all()
        and transient_primary_seed["motors"].eq(1).all()
        and transient_primary_seed["healthy_windows"].eq(176).all()
        and transient_primary_seed["record_macro_detection_rate"].eq(0).all()
        and transient_primary_seed["fault_record_any_alarm_rate"].eq(0).all()
        and transient_primary_seed["false_alarms"].between(7, 13).all(),
        "Transient primary-seed denominators or null result changed",
    )
    per_record = sources["transient_per_record"]
    per_record_primary = per_record.loc[per_record["seed"] == primary_seed]
    _require(
        len(per_record_primary) == 144
        and per_record_primary["record_id"].nunique() == 12
        and per_record_primary["primary_fault_windows"].eq(5).all()
        and per_record_primary["detected_fault_windows"].eq(0).all(),
        "Transient record-level primary endpoint changed",
    )
    predictions = sources["transient_predictions"]
    predictions_primary = predictions.loc[predictions["seed"] == primary_seed]
    pre_counts = predictions_primary.loc[
        predictions_primary["segment"] == "pre_fault"
    ].groupby("method").size()
    post = predictions_primary.loc[predictions_primary["segment"] == "post_fault"]
    post_counts_by_method = post.groupby("method").size()
    first_second = post.loc[post["primary_post_window"].astype(bool)]
    first_counts_by_method = first_second.groupby("method").size()
    _require(
        pre_counts.eq(176).all()
        and post_counts_by_method.eq(120).all()
        and first_counts_by_method.eq(60).all()
        and not post["alarm"].astype(bool).any(),
        "Transient prediction horizons or zero-alarm result changed",
    )


def render_s1(sources: dict[str, Any]) -> str:
    metadata = sources["external_metadata"]
    feature_names = ", ".join(f"`{name}`" for name in metadata["feature_columns"])
    dataset_table = markdown_table(
        [
            "Dataset",
            "Physical motors",
            "Physical records",
            "Record-subsystem streams",
            "Sampling",
            "Frozen analysis grain",
        ],
        [
            [
                "KAIST source",
                "3 (1, 1.5, and 3 kW)",
                "45 (3 healthy; 42 fault)",
                "not applicable",
                "100 kHz; leading 120 s",
                "600 non-overlapping 0.2 s windows and 40 3 s blocks per record",
            ],
            [
                "External dual-three-phase PMSM",
                "1 (custom 30.16 kW)",
                "56 (8 healthy; 48 fault)",
                "112 (2 subsystems per record)",
                "10 kHz; [12, 36) s",
                "120 windows and 8 blocks per record-subsystem; one system block after maxima",
            ],
        ],
    )
    split_table = markdown_table(
        ["Stage", "KAIST leave-one-motor-out", "External validation"],
        [
            [
                "Source reference",
                "healthy blocks 0–23 for each of the two source motors; balanced subset 0, 8, 15, 23",
                "three KAIST source motors; covariance blocks 0–23 and balanced blocks 0, 8, 15, 23",
            ],
            [
                "Target adaptation",
                "blocks 0–3 (4 blocks; 60 windows) from the held-out motor's healthy record",
                "0 N·m healthy record, blocks 0–3 (60 windows per subsystem)",
            ],
            [
                "Guard / unused",
                "blocks 4 and 25",
                "0 N·m blocks 4–7 are unused for validation",
            ],
            [
                "Calibration",
                "healthy blocks 5–24 (20 blocks)",
                "healthy loads 10, 20, and 30 N·m; all 8 blocks (3 records; 24 system blocks)",
            ],
            [
                "Held-out health test",
                "healthy blocks 26–39 (14 blocks)",
                "healthy loads 5, 15, 25, and 35 N·m; all 8 blocks (4 records; 32 system blocks)",
            ],
            [
                "Fault test",
                "14 records × 40 blocks = 560 blocks per target motor",
                "6 turn-fault states × 8 loads = 48 records; 8 blocks each = 384 system blocks",
            ],
        ],
    )
    return f"""## S1. Data, experimental units, and locked splits

The **physical motor** is the generalization unit, the **MAT/TDMS record** is the
condition-level resampling unit, the 3 s **block** is the alarm unit, and the 0.2 s
window is the feature-extraction unit. Repeated windows and ordered blocks from one
record are not independent replications. The external dataset contains only one
physical motor; its 48 fault records are operating-condition records, not 48 motors.

{dataset_table}

The external MAT records contain two three-phase current subsystems (`SubSys1` and
`SubSys2`). Each subsystem is scored separately. A block score is the maximum over
15 windows within a subsystem followed by the maximum over the two subsystems. Thus,
each physical record contributes exactly eight system block scores.

### S1.1. Ordered split definitions

{split_table}

The external 6-by-8 grid is not crossed by fault phase. Fault-turn levels 1, 3, 5,
and 6 use phase U, whereas levels 2 and 4 use phase V. Consequently, fault-turn count
and phase effects are not separately identifiable; the turn-stratified record bootstrap
conditions on this fixed assignment rather than resolving it.

All models use the 27-feature scale-free arm: {feature_names}. Source features are
robustly centered and scaled within source motor; external target features are
robustly centered and scaled within subsystem from the frozen adaptation subset.
The split-conformal alarm level is `alpha = 0.05`. Arithmetic covariance methods use
ridge fraction 0.001 and the Proposed Log-Euclidean method uses the source-selected
ridge fraction 0.01. No external fault row enters fitting, scaling, calibration, or
threshold construction.
"""


def render_s2(sources: dict[str, Any]) -> str:
    external = sources["external"].set_index("method").loc[list(METHOD_ORDER)]
    rows: list[list[object]] = []
    for method, row in external.iterrows():
        rows.append(
            [
                method_label(method),
                METHOD_SCOPES[method],
                compact_float(row["threshold"]),
                f"{int(row['false_alarms'])}/32 ({percent(row['healthy_block_false_alarm_rate'])}%)",
                "pass" if bool(row["h1_empirical_pass"]) else "fail",
                f"{round(row['fault_block_detection_rate'] * 384)}/384 ({percent(row['fault_block_detection_rate'])}%)",
                f"{percent(row['fault_record_macro_detection_rate'])}%",
                (
                    f"[{percent(row['record_bootstrap_detection_ci_lower'])}, "
                    f"{percent(row['record_bootstrap_detection_ci_upper'])}]"
                ),
                f"{percent(row['fault_record_any_alarm_rate'])}%",
                f"{row['block_auroc']:.4f}",
                f"{row['block_auprc']:.4f}",
            ]
        )
    table = markdown_table(
        [
            "Method",
            "Healthy training/reference",
            "Threshold",
            "Health FA",
            "H1",
            "Fault block detection",
            "Record-macro detection",
            "Record-bootstrap 95% CI (%)",
            "Record any-alarm",
            "AUROC",
            "AUPRC",
        ],
        rows,
    )
    return f"""## S2. Complete frozen external comparison across 11 methods

Target MinCovDet was the strongest external method: 70.05% fault-block detection,
zero false alarms among 32 held-out healthy blocks, and AUROC 0.9268. It was also the
only method satisfying the prespecified empirical H1 rule. Proposed achieved 25.00%
detection, one false alarm (3.12%), and AUROC 0.6354. These external results are
reported in full below; method-specific score thresholds are not comparable in
magnitude across estimators.

The external pooled AUROC compares 384 fault blocks spanning all eight loads with 32
held-out health blocks from only 5, 15, 25, and 35 N·m. It is therefore a descriptive
ranking statistic under unequal load support, not a load-matched population estimand.

{table}

H1 requires both a descriptive Wilson upper bound no greater than 0.12 and a maximum
held-out-load false-alarm rate no greater than 0.15. The record-bootstrap interval
resamples complete fault records within the six fault-turn strata (10,000 draws,
seed 711). Because every fault record has eight blocks, block-weighted and
record-macro detection coincide here. Intervals are conditional on the observed
single external motor.
"""


def render_s3(sources: dict[str, Any]) -> str:
    paired = sources["paired"]
    paired_rows: list[list[object]] = []
    for _, row in paired.iterrows():
        paired_rows.append(
            [
                method_label(row["method_a"]),
                f"{percent(row['method_a_detection'])}%",
                f"{percent(row['method_b_detection'])}%",
                f"{percentage_points(row['method_a_minus_b_detection'])} pp",
                (
                    f"[{percentage_points(row['bootstrap_ci_lower'])}, "
                    f"{percentage_points(row['bootstrap_ci_upper'])}]"
                ),
                p_value(row["centered_bootstrap_two_sided_p"]),
                p_value(row["holm_adjusted_p"]),
                (
                    f"{int(row['records_method_a_better'])} / "
                    f"{int(row['records_tied'])} / "
                    f"{int(row['records_method_b_better'])}"
                ),
                (
                    f"{int(row['method_a_health_false_alarms'])} / "
                    f"{int(row['method_b_health_false_alarms'])}"
                ),
            ]
        )
    paired_table = markdown_table(
        [
            "Candidate",
            "Candidate detection",
            "Proposed detection",
            "Candidate − Proposed",
            "Paired 95% CI (pp)",
            "Bootstrap p",
            "Holm p",
            "Candidate / tie / Proposed records",
            "Candidate / Proposed health FA",
        ],
        paired_rows,
    )

    transfer = sources["transfer"]
    transfer_rows: list[list[object]] = []
    for _, row in transfer.iterrows():
        transfer_rows.append(
            [
                str(row["family"]).replace("_", " "),
                method_label(row["target_only_method"]),
                method_label(row["source_target_method"]),
                f"{percent(row['method_a_detection'])}%",
                f"{percent(row['method_b_detection'])}%",
                f"{percentage_points(row['method_a_minus_b_detection'])} pp",
                (
                    f"[{percentage_points(row['bootstrap_ci_lower'])}, "
                    f"{percentage_points(row['bootstrap_ci_upper'])}]"
                ),
                p_value(row["holm_adjusted_p"]),
                (
                    f"{int(row['records_method_a_better'])} / "
                    f"{int(row['records_tied'])} / "
                    f"{int(row['records_method_b_better'])}"
                ),
            ]
        )
    transfer_table = markdown_table(
        [
            "Contrast family",
            "Target-only",
            "Source-balanced counterpart",
            "Target detection",
            "Balanced detection",
            "Target − balanced",
            "Paired 95% CI (pp)",
            "Holm p",
            "Target / tie / balanced records",
        ],
        transfer_rows,
    )
    return f"""## S3. Conditional paired comparisons and source-transfer contrasts

### S3.1. Every frozen candidate versus Proposed

{paired_table}

### S3.2. Target-only versus source-balanced training/reference

{transfer_table}

Both tables use complete-record paired differences across the same 48 fault records,
stratified by fault turns. Two-sided centered bootstrap p-values use 10,000 draws
(seed 711); Holm adjustment is applied separately to the 10 candidate-vs-Proposed
comparisons and the five transfer contrasts. The smallest attainable nonzero
bootstrap estimate is 0.0001. These post-reveal comparisons quantify conditional
differences on one motor; their adjusted p-values do not establish cross-motor
generalization. The two covariance contrasts against target sample covariance are
the closest transfer comparisons but do not hold the matrix estimator fixed.
"""


def render_s4(sources: dict[str, Any]) -> str:
    horizons = sources["horizons"]
    horizon_rows: list[list[object]] = []
    for method in METHOD_ORDER:
        selected = horizons[horizons["method"].eq(method)].set_index("horizon")
        row: list[object] = [method_label(method)]
        for horizon in ("first_4_blocks", "first_7_blocks", "all_8_blocks"):
            values = selected.loc[horizon]
            row.append(
                f"{percent(values['fault_block_detection_rate'])} / "
                f"{percent(values['fault_record_any_alarm_rate'])} / "
                f"{percent(values['healthy_block_false_alarm_rate'])}"
            )
        horizon_rows.append(row)
    horizon_table = markdown_table(
        [
            "Method",
            "Blocks 0–3: detection / any / health FA (%)",
            "Blocks 0–6: detection / any / health FA (%)",
            "Blocks 0–7: detection / any / health FA (%)",
        ],
        horizon_rows,
    )

    first = sources["first_alarm"].set_index("method").loc[list(METHOD_ORDER)]
    first_rows: list[list[object]] = []
    for method, row in first.iterrows():
        first_rows.append(
            [
                method_label(method),
                f"{int(row['records_with_any_alarm'])}/48",
                int(row["records_without_alarm"]),
                (
                    f"{row['first_alarm_block_q25']:.2g} / "
                    f"{row['first_alarm_block_median']:.2g} / "
                    f"{row['first_alarm_block_q75']:.2g}"
                ),
                (
                    f"{row['first_alarm_approx_rpm_q25']:.0f} / "
                    f"{row['first_alarm_approx_rpm_median']:.0f} / "
                    f"{row['first_alarm_approx_rpm_q75']:.0f}"
                ),
            ]
        )
    first_table = markdown_table(
        [
            "Method",
            "Records ever alarmed",
            "Never alarmed",
            "First block Q1 / median / Q3",
            "Healthy-RPM proxy Q1 / median / Q3",
        ],
        first_rows,
    )

    block = sources["block_auroc"]
    summary = sources["block_auroc_summary"].set_index("method")
    block_rows: list[list[object]] = []
    for method in METHOD_ORDER:
        selected = block[block["method"].eq(method)].sort_values("block_id")
        _require(len(selected) == 8, f"{method} no longer has eight block AUROCs")
        block_rows.append(
            [
                method_label(method),
                *[f"{value:.3f}" for value in selected["block_matched_auroc"]],
                f"{summary.loc[method, 'equal_weight_mean_block_auroc']:.3f}",
                f"{summary.loc[method, 'pooled_block_auroc']:.3f}",
            ]
        )
    block_table = markdown_table(
        [
            "Method",
            "B0",
            "B1",
            "B2",
            "B3",
            "B4",
            "B5",
            "B6",
            "B7",
            "Equal-weight mean",
            "Pooled",
        ],
        block_rows,
    )
    return f"""## S4. Horizon, first-alarm, and acceleration-position diagnostics

All records follow the same [12, 36) s acceleration segment, divided into block IDs
0–7. Block position therefore co-moves with speed. The primary all-eight-block
metric gives late high-speed blocks more opportunities to alarm; the following
post-reveal horizon cuts retain the frozen scores and thresholds.

### S4.1. First four, first seven, and all eight blocks

{horizon_table}

Each cell reports fault-block detection, fault-record any-alarm, and held-out healthy
block false-alarm rate. Denominators are respectively 192/48/16 for blocks 0–3,
336/48/28 for blocks 0–6, and 384/48/32 for blocks 0–7.

### S4.2. First alarm by physical fault record

{first_table}

First-alarm quantiles are calculated only among records that ever alarm. The RPM
quantity is the median RPM from the matching-load healthy record and block; it is a
proxy, not a measured fault-record RPM and not a stationary time-to-detection
estimate. Proposed first alarm occurred at median block 6, while Target MinCovDet
first alarm occurred at median block 1.

### S4.3. AUROC matched by acceleration block

{block_table}

Blocks B0–B7 correspond to [12,15), [15,18), [18,21), [21,24), [24,27), [27,30),
[30,33), and [33,36) s. Each position-specific AUROC compares four held-out healthy
blocks with 48 fault blocks at the same position. The equal-weight mean describes
matched-position discrimination; the pooled AUROC remains the frozen primary
ranking metric. Neither treats the eight ordered blocks as independent motors.
"""


def render_s5(sources: dict[str, Any]) -> str:
    ranges = sources["seed_ranges"]
    rows: list[list[object]] = []
    for _, row in ranges.iterrows():
        rows.append(
            [
                method_label(row["method"]),
                f"{percent(row['primary_detection_rate'])}%",
                f"{percent(row['detection_min'])}–{percent(row['detection_max'])}%",
                f"{100 * row['detection_range']:.2f} pp",
                f"{100 * row['max_abs_detection_change_from_primary']:.2f} pp",
                (
                    f"{int(row['false_alarms_min'])}–{int(row['false_alarms_max'])}/32 "
                    f"({percent(row['far_min'])}–{percent(row['far_max'])}%)"
                ),
                f"{int(row['h1_pass_seeds'])}/5",
                f"{compact_float(row['threshold_min'])}–{compact_float(row['threshold_max'])}",
                f"{row['block_auroc_min']:.4f}–{row['block_auroc_max']:.4f}",
            ]
        )
    table = markdown_table(
        [
            "Stochastic method",
            "Primary detection",
            "Five-seed detection",
            "Range",
            "Max |change| from primary",
            "Health FA range",
            "H1 passes",
            "Threshold range",
            "AUROC range",
        ],
        rows,
    )
    seeds = ", ".join(str(seed) for seed in sources["seed_metadata"]["seeds"])
    return f"""## S5. Five-seed stochastic sensitivity

{table}

The frozen seeds are {seeds}; 20260820 is the primary seed. For each seed, the
estimator is refitted only on the same frozen healthy training subset, and its
threshold is mechanically recalibrated from the same 24 healthy calibration blocks
at alpha 0.05. No fault score affects a threshold. Primary-seed reconciliation gave
zero alarm mismatches for all four methods (maximum score discrepancy
1.46 × 10^-11). No formal seed-stability gate was specified before reveal, so the full ranges
are descriptive and were not used to change the reported model or protocol.
"""


def render_s6(sources: dict[str, Any]) -> str:
    drift = sources["drift"].sort_values(
        "robust_z_direction_free_auc", ascending=False
    ).head(8)
    drift_rows: list[list[object]] = []
    for _, row in drift.iterrows():
        drift_rows.append(
            [
                row["feature"],
                str(row["feature_family"]).replace("_", " "),
                f"{row['raw_direction_free_auc']:.3f}",
                f"{row['robust_z_direction_free_auc']:.3f}",
                f"{row['matched_robust_z_dz']:+.3f}",
                f"{percent(row['fault_absolute_contribution_share'])}%",
                f"{percent(row['healthy_test_absolute_contribution_share'])}%",
                f"{row['max_absolute_speed_spearman']:.3f}",
            ]
        )
    drift_table = markdown_table(
        [
            "Feature",
            "Family",
            "Raw direction-free AUROC",
            "Robust-z direction-free AUROC",
            "Matched robust-z dz",
            "Fault |contribution| share",
            "Health |contribution| share",
            "Max |speed rho|",
        ],
        drift_rows,
    )
    geometry = sources["geometry"]
    geometry_rows: list[list[object]] = []
    for _, row in geometry.iterrows():
        geometry_rows.append(
            [
                row["subsystem"],
                int(row["adaptation_windows"]),
                int(row["covariance_rank"]),
                f"{row['covariance_condition_number']:.2f}",
                f"{row['max_window_contribution_sum_error']:.3e}",
                "yes" if bool(row["center_matches_frozen"]) else "no",
                "yes" if bool(row["scale_matches_frozen"]) else "no",
            ]
        )
    geometry_table = markdown_table(
        [
            "Subsystem",
            "Adaptation windows",
            "Rank / 27",
            "Condition number",
            "Max contribution-sum error",
            "Center match",
            "Scale match",
        ],
        geometry_rows,
    )
    reconstruction = sources["reconstruction"]
    max_score_error = reconstruction["frozen_score_error"].abs().max()
    max_contribution_error = reconstruction["contribution_sum_error"].abs().max()
    return f"""## S6. Post-reveal feature drift and frozen-geometry reconstruction

The feature diagnostic is descriptive and uses record-subsystem-block means (15
windows). The table shows the eight largest direction-free single-feature AUROCs on
held-out health loads, comparing 384 fault blocks with 64 record-subsystem healthy
blocks at matching loads and block positions. One healthy condition is reused across
six fault-turn comparisons, so the 384 pairs are not independent motor replications.

{drift_table}

Harmonic-3 ratios discriminate fault from health individually but receive less than
1% of the frozen score's absolute contribution, whereas `rms_ratio_a` receives
21.62%. This mismatch is a diagnostic of the locked multivariate geometry, not a
license to reweight features after reveal. Block and fundamental frequency co-move,
and the reported speed associations do not identify causal fault features.

### S6.1. Exact reconstruction checks

{geometry_table}

Across all 448 physical-record block scores, the maximum absolute reconstructed-
versus-frozen score error was {max_score_error:.3e}; the maximum feature-contribution
sum error was {max_contribution_error:.3e}. The reconstructed center, scale,
Log-Euclidean covariance, winning subsystem/window, system maximum, p-value, and
alarm were checked without fitting a new model or recomputing a threshold. Fault
labels did not enter covariance reconstruction.
"""


def render_s7(sources: dict[str, Any]) -> str:
    sampling = sources["sampling"].set_index("method").loc[list(METHOD_ORDER)]
    rows: list[list[object]] = []
    for method, row in sampling.iterrows():
        rows.append(
            [
                method_label(method),
                "target-only control" if method in TARGET_ONLY_METHODS else "source-sensitive",
                f"{percent(row['fault_block_detection_rate_source_100khz'])}%",
                f"{percent(row['fault_block_detection_rate_source_10khz'])}%",
                (
                    f"{percentage_points(row['delta_fault_block_detection_rate_10khz_minus_100khz'])} pp"
                ),
                f"{percent(row['healthy_block_false_alarm_rate_source_100khz'])}%",
                f"{percent(row['healthy_block_false_alarm_rate_source_10khz'])}%",
                f"{row['block_auroc_source_100khz']:.4f}",
                f"{row['block_auroc_source_10khz']:.4f}",
            ]
        )
    table = markdown_table(
        [
            "Method",
            "Sampling dependency",
            "Detection, 100 kHz source",
            "Detection, 10 kHz source",
            "Change",
            "Health FAR, 100 kHz",
            "Health FAR, 10 kHz",
            "AUROC, 100 kHz",
            "AUROC, 10 kHz",
        ],
        rows,
    )
    integrity = sources["sampling_integrity"]
    integrity_rows = [
        [
            row["feature_arm"],
            int(row["rows"]),
            int(row["physical_records"]),
            f"{int(row['windows_per_record_min'])}–{int(row['windows_per_record_max'])}",
            f"{int(row['blocks_per_record_min'])}–{int(row['blocks_per_record_max'])}",
            int(row["duplicate_window_keys"]),
            int(row["nonfinite_numeric_values"]),
        ]
        for _, row in integrity.iterrows()
    ]
    integrity_table = markdown_table(
        [
            "Source feature arm",
            "Rows",
            "Records",
            "Windows / record",
            "Blocks / record",
            "Duplicate keys",
            "Nonfinite values",
        ],
        integrity_rows,
    )
    internal = sources["sampling_internal"].set_index("method").loc[PROPOSED]
    records = sources["sampling_records"]
    deltas = records["delta_block_alarm_rate_10khz_minus_100khz"]
    improved = int((deltas > 0).sum())
    tied = int((deltas == 0).sum())
    worsened = int((deltas < 0).sum())
    return f"""## S7. Post-reveal 100 kHz to 10 kHz sampling-rate sensitivity

The KAIST three-phase current was mechanically anti-aliased and decimated from
100 kHz to 10 kHz with `scipy.signal.resample_poly` (`up=1`, `down=10`, Kaiser
beta 5.0, line padding) over each complete leading 120 s record before the frozen
0.2 s windows were cut. The feature definitions, 3 s maximum block aggregation,
splits, ridge values, methods, seeds, calibration rule, and external feature table
were unchanged. This analysis was specified after fault reveal and was not used for
model or protocol selection.

{integrity_table}

{table}

Proposed detection changed from 25.00% to 24.74% (-0.26 percentage points), and
AUROC changed from 0.6354 to 0.6331. Across the 48 physical fault records, alarm
rate improved for {improved}, tied for {tied}, and worsened for {worsened}. Its KAIST
leave-one-motor-out source detection remained {percent(internal['detection_source_10khz'])}%
(100 kHz: {percent(internal['detection_source_100khz'])}%) and AUROC remained
{internal['auroc_source_10khz']:.4f} (100 kHz: {internal['auroc_source_100khz']:.4f}),
so the 10 kHz arm was not globally unusable. All five target-only controls reproduced
448/448 block scores, p-values, and alarms with zero mismatches. These results do not
support source/target sampling-rate mismatch as the primary explanation for the
observed negative transfer.
"""


def render_s8(root: Path, sources: dict[str, Any]) -> str:
    artifacts = [
        ("processed input", "data/processed/kaist_current_features.csv.gz"),
        (
            "processed input",
            "data/processed/external_dual_three_phase_health_features.csv.gz",
        ),
        (
            "sampling input",
            "data/processed/kaist_current_features_10khz.csv.gz",
        ),
        (
            "raw-file hash registry",
            "data/processed/external_dual_three_phase_health_features.csv.metadata.json",
        ),
        ("primary result", "results/external_pmsm_validation/aggregate_summary.csv"),
        (
            "paired diagnostic",
            "results/external_failure_diagnostics/paired_vs_proposed.csv",
        ),
        (
            "horizon diagnostic",
            "results/external_failure_diagnostics/horizon_detection_record_any.csv",
        ),
        (
            "position diagnostic",
            "results/external_failure_diagnostics/block_auroc.csv",
        ),
        (
            "seed diagnostic",
            "results/external_seed_sensitivity/aggregate_seed_ranges.csv",
        ),
        (
            "feature diagnostic",
            "results/external_feature_drift/feature_diagnostic_summary.csv",
        ),
        (
            "geometry check",
            "results/external_feature_drift/score_reconstruction_checks.csv",
        ),
        (
            "sampling diagnostic",
            "results/sampling_rate_sensitivity/external_method_comparison.csv",
        ),
    ]
    rows = [
        [category, f"`{relative}`", file_sha256(root / relative)]
        for category, relative in artifacts
    ]
    table = markdown_table(["Role", "Artifact", "SHA-256"], rows)
    return f"""## S8. Hash registry, interpretation limits, and next validation step

{table}

The external processed-feature metadata JSON contains the individual SHA-256 hash,
sampling rate, length, health/fault metadata, and subsystem/window counts for all 56
MAT records. The hash registry above fixes the inputs and derived result tables from
which this supplement was mechanically generated.

### S8.1. Limits on inference

- **One external motor.** The eight loads, six fault-turn configurations, two
  subsystems, and eight ordered blocks are repeated conditions on one physical
  dual-three-phase motor. Neither record bootstrap nor Holm correction creates
  independent motor replication.

- **Dependent calibration and test blocks.** The 24 calibration blocks come from
  three healthy load records and the 32 held-out health blocks from four records.
  Conformal p-values and Wilson intervals are therefore empirical/descriptive, not
  guarantees under arbitrary within-record dependence.

- **Post-reveal diagnostics.** Sections S3–S7 were specified after external fault
  reveal. They retain the frozen predictions or mechanically rerun an explicitly
  defined sampling arm; they introduce no new selected model, feature, ridge,
  threshold, aggregation, or primary claim.

- **Speed-position coupling.** The analyzed record segment is an acceleration ramp.
  Block ID, time, electrical-frequency proxy, and speed co-move, so first-alarm and
  feature associations cannot isolate causal effects or stationary detection delay.

- **Current-only scope.** The pipeline reads only the two three-phase current sets.
  Voltage, dq variables, and other modalities were not used. The test therefore does
  not cover faults whose detectable signature requires those channels.

- **Dataset-specific target adaptation.** Target-only methods use 60 healthy
  adaptation windows per subsystem, while source-balanced variants combine these
  with source healthy references. Performance gaps describe this locked protocol,
  not every possible transfer strategy.

The decisive next validation is a prospectively frozen replication on additional
independent external motors, preferably with stationary speed/load segments as well
as ramps. Until that experiment, external uncertainty is conditional on the single
observed motor and the failure of source balancing should not be generalized as a
population-level effect.
"""


def render_s9(root: Path, sources: dict[str, Any]) -> str:
    primary = sources["transient_compatibility_primary"]
    post = sources["transient_compatibility_post"]
    compatibility_rows: list[list[object]] = []
    for stage, table in (
        ("Frozen primary parser", primary),
        ("Post-reveal implicit-time repair", post),
    ):
        for motor in ("200W", "20kW"):
            motor_rows = table.loc[table["motor_id"] == motor]
            compatible = int(motor_rows["main_endpoint_compatible"].astype(bool).sum())
            total = len(motor_rows)
            if stage == "Frozen primary parser":
                interpretation = "no features or scores"
            elif motor == "200W":
                interpretation = "descriptive sensitivity only"
            else:
                interpretation = "44.44%; failed the frozen 80% gate"
            compatibility_rows.append(
                [
                    stage,
                    motor,
                    f"{compatible}/{total}",
                    percent(compatible / total),
                    interpretation,
                ]
            )
    compatibility_table = markdown_table(
        ["Stage", "Motor", "Compatible records", "Fraction (%)", "Use"],
        compatibility_rows,
    )

    metadata = sources["transient_validation_metadata"]
    primary_seed = int(metadata["primary_seed"])
    aggregate = sources["transient_aggregate"]
    aggregate = aggregate.loc[aggregate["seed"] == primary_seed].set_index("method")
    predictions = sources["transient_predictions"]
    predictions = predictions.loc[predictions["seed"] == primary_seed]
    method_rows = []
    for method in TRANSIENT_METHOD_ORDER:
        summary = aggregate.loc[method]
        method_predictions = predictions.loc[predictions["method"] == method]
        post_predictions = method_predictions.loc[
            method_predictions["segment"] == "post_fault"
        ]
        first_second = post_predictions.loc[
            post_predictions["primary_post_window"].astype(bool)
        ]
        method_rows.append(
            [
                method_label(method),
                f"{int(summary['false_alarms'])}/{int(summary['healthy_windows'])}",
                f"{int(first_second['alarm'].astype(bool).sum())}/{len(first_second)}",
                (
                    f"{int(summary['fault_record_any_alarm_rate'] * summary['records'])}/"
                    f"{int(summary['records'])}"
                ),
                (
                    f"{int(post_predictions['alarm'].astype(bool).sum())}/"
                    f"{len(post_predictions)}"
                ),
                f"{float(summary['mean_record_auroc']):.3f}",
            ]
        )
    method_table = markdown_table(
        [
            "Method",
            "Held-out prefault alarms",
            "First 1 s fault alarms",
            "Record-any alarms",
            "Full 2 s fault alarms",
            "Mean record AUROC",
        ],
        method_rows,
    )

    hash_artifacts = [
        (
            "prospectively frozen pre-reveal protocol",
            "docs/secondary_transient_validation_protocol.md",
        ),
        ("chronological reveal log", "docs/secondary_transient_reveal_log.md"),
        (
            "frozen parser compatibility",
            "results/transient_feature_build/record_compatibility.csv",
        ),
        (
            "post-reveal compatibility",
            (
                "results/transient_feature_build_post_reveal_implicit_time/"
                "record_compatibility.csv"
            ),
        ),
        (
            "post-reveal features",
            "data/processed/transient_pmsm_features_post_reveal_implicit_time.csv.gz",
        ),
        (
            "200 W method summary",
            "results/transient_pmsm_validation_post_reveal_200w/aggregate_summary.csv",
        ),
        (
            "200 W record summary",
            "results/transient_pmsm_validation_post_reveal_200w/per_record_summary.csv",
        ),
        (
            "200 W predictions",
            (
                "results/transient_pmsm_validation_post_reveal_200w/"
                "window_predictions.csv.gz"
            ),
        ),
    ]
    hash_table = markdown_table(
        ["Role", "Artifact", "SHA-256"],
        [
            [role, f"`{relative}`", file_sha256(root / relative)]
            for role, relative in hash_artifacts
        ],
    )

    per_record = sources["transient_per_record"]
    per_record = per_record.loc[per_record["seed"] == primary_seed]
    fit_min = int(per_record["fit_record_count"].min())
    fit_max = int(per_record["fit_record_count"].max())
    fit_count = str(fit_min) if fit_min == fit_max else f"{fit_min}-{fit_max}"
    calibration_records = sorted(per_record["calibration_record_count"].unique())
    calibration_min = int(per_record["calibration_windows"].min())
    calibration_max = int(per_record["calibration_windows"].max())
    proposed = aggregate.loc[PROPOSED]
    min_cov = aggregate.loc["target_min_cov_det"]
    return f"""## S9. Prospectively logged secondary transient-set audit

This audit used Zenodo 10.5281/zenodo.15631383: 12 records from one 200 W
PMSM and nine records from one 20 kW PMSM, all sampled at 10 kHz and all
containing a transition from prefault operation to an interturn short circuit. It has
no separate healthy-only records. Signal values remained sealed until the parser,
onset rule, whole-record split, 80% motor-compatibility gate, detector family, and
outputs had been frozen.

### S9.1. Compatibility gate and preserved primary failure

{compatibility_table}

The frozen primary parser required an explicit monotonic 10 kHz time candidate.
All 21 MATLAB `timeseries` objects instead stored uniform timing in `TimeInfo` while
their explicit `Time_` arrays were empty. The run therefore stopped before feature
extraction and produced no detector scores. After that failure was committed, a
separate opt-in parser reconstructed time from the stored start, increment, and length.
Five 20 kW records then remained incompatible because detected onset overlapped the
frozen 0.5 s baseline. No alternative baseline or record subset was selected, so the
20 kW motor has no quantitative endpoint.

### S9.2. Post-reveal 200 W single-motor sensitivity

Each of 12 200 W records was held out in turn. Depending on the hash split,
{fit_count} other records supplied prefault fit windows and
{calibration_records[0]} records supplied {calibration_min}-{calibration_max}
calibration windows; the held-out record supplied 176 prefault test windows, five
primary first-second windows, and ten windows over the full 2 s post-onset horizon.

{method_table}

Every method produced zero thresholded alarms in both post-onset horizons. Held-out
prefault alarms ranged from 7/176 to 13/176. Proposed produced
{int(proposed['false_alarms'])}/176 prefault alarms and mean record AUROC
{float(proposed['mean_record_auroc']):.3f}; Target MinCovDet produced
{int(min_cov['false_alarms'])}/176 and AUROC
{float(min_cov['mean_record_auroc']):.3f}. Because all 12 methods tie at zero detection,
paired thresholded transfer comparisons are uninformative; score-ranking differences
do not rescue the missed early alarms. This analysis is post-reveal, contains one
physical motor, and reuses prefault and fault segments from the same transition
records. It cannot confirm cross-capacity transfer or support population inference.

### S9.3. Audit hashes

{hash_table}

The immutable frozen parser failure and the opt-in repaired analysis are stored in
separate result directories. The repaired feature-table hash is checked against both
the extractor and validation metadata before this section is generated.
"""


def build_supplementary(root: Path) -> str:
    sources = load_sources(root)
    validate_sources(root, sources)
    summary = """# Supplementary Material: Healthy-Only Cross-Machine PMSM Fault Detection

> Submission draft generated mechanically from hash-locked CSV/JSON artifacts. The
> frozen external experiment uses one physical motor. Sections S3–S7 are
> explicitly post-reveal diagnostics and did not select a new model or threshold.
> Section S9 preserves a prospectively logged parser failure and labels the repaired
> 200 W analysis as post-reveal sensitivity.

## Technical summary

The complete frozen external comparison favors Target MinCovDet, not Proposed:
Target MinCovDet detected 70.05% of 384 fault blocks with 0/32 held-out healthy false
alarms, whereas Proposed detected 25.00% with 1/32 false alarms. Conditional
complete-record comparisons show that adding source healthy data generally reduced
external performance, except that target-only and source+target OC-SVM tied in mean
detection. The apparent performance increase late in each record is coupled to the
shared acceleration ramp. Five-seed, feature-geometry, and 100 kHz-to-10 kHz
sensitivity analyses did not change the frozen primary result. All external
intervals and post-reveal comparisons remain conditional on a single physical motor.
The secondary 21-record transient audit did not supply confirmatory evidence: the
frozen parser accepted 0/21 records, the repaired 20 kW arm failed its compatibility
gate, and all methods had zero first-second detection in the repaired 200 W sensitivity.
"""
    sections = [
        render_s1(sources),
        render_s2(sources),
        render_s3(sources),
        render_s4(sources),
        render_s5(sources),
        render_s6(sources),
        render_s7(sources),
        render_s8(root, sources),
        render_s9(root, sources),
    ]
    return summary.rstrip() + "\n\n" + "\n\n".join(section.strip() for section in sections) + "\n"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path("."))
    parser.add_argument(
        "--output", type=Path, default=Path("paper/supplementary_material.md")
    )
    parser.add_argument("--check", action="store_true")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    root = args.root.resolve()
    report = build_supplementary(root)
    output = args.output if args.output.is_absolute() else root / args.output
    if args.check:
        if not output.exists() or output.read_text(encoding="utf-8") != report:
            raise SystemExit(
                f"{output} is missing or stale; rerun scripts/build_supplementary_material.py"
            )
        print(f"verified {output}")
        return
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(report, encoding="utf-8")
    print(f"wrote {output}")


if __name__ == "__main__":
    main()
