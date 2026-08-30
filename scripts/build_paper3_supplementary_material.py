"""Build the evidence-backed supplementary material for Paper 3."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
from collections.abc import Iterable, Sequence
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "papers/paper3_calibration_transport/supplementary_material.md"
RESULTS = ROOT / "results"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=OUTPUT)
    parser.add_argument("--check", action="store_true")
    return parser.parse_args()


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def read_summary(path: Path) -> dict[str, object]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    summary = payload.get("summary", payload)
    if not isinstance(summary, dict):
        raise TypeError(f"{path} does not contain a summary object")
    return summary


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def md_table(headers: Sequence[str], rows: Iterable[Sequence[object]]) -> str:
    rendered = ["| " + " | ".join(headers) + " |"]
    rendered.append("|" + "|".join("---" for _ in headers) + "|")
    for row in rows:
        values = [str(value).replace("|", r"\|") for value in row]
        rendered.append("| " + " | ".join(values) + " |")
    return "\n".join(rendered)


def pct(value: str | float, digits: int = 2) -> str:
    return f"{100 * float(value):.{digits}f}%"


def build_content() -> str:
    development_dir = RESULTS / "paper3_development"
    confirmation_dir = RESULTS / "paper3_pmsg_confirmation"
    development = read_csv(development_dir / "aggregate_summary.csv")
    confirmation = read_csv(confirmation_dir / "aggregate_summary.csv")
    condition = read_csv(confirmation_dir / "selected_condition_summary.csv")
    fault_cases = read_csv(confirmation_dir / "selected_fault_case_summary.csv")
    session = read_summary(RESULTS / "paper3_pmsg_session_anchor/summary.json")
    topology = read_summary(RESULTS / "paper3_pmsg_topology_crossfit/summary.json")
    conditioned = read_summary(RESULTS / "paper3_pmsg_conditioned_anchor/summary.json")
    topology_folds = read_csv(
        RESULTS / "paper3_pmsg_topology_crossfit/per_fold_summary.csv"
    )
    conditioned_folds = read_csv(
        RESULTS / "paper3_pmsg_conditioned_anchor/per_fold_summary.csv"
    )
    evidence = json.loads(
        (
            ROOT / "papers/paper3_calibration_transport/evidence_validation.json"
        ).read_text(encoding="utf-8")
    )
    metadata = json.loads(
        (
            ROOT / "data/processed/paper3_pmsg_confirmation_features.csv.metadata.json"
        ).read_text(encoding="utf-8")
    )

    assert len(development) == 7
    assert len(confirmation) == 7
    assert len(condition) == 17
    assert len(fault_cases) == 24
    assert len(topology_folds) == 3 and len(conditioned_folds) == 3
    assert evidence["status"] == "pass"
    assert metadata["rows"] == 2493 and metadata["records"] == 225
    selected = next(row for row in confirmation if row["method"] == "spline_residual")
    assert int(selected["pre_fault_sessions_with_alarm"]) == 71
    assert int(selected["fault_records_detected"]) == 156
    assert int(session["pre_fault_false_alarms"]) == 17
    assert int(topology["pre_false_alarms"]) == 14
    assert int(conditioned["pre_false_alarms"]) == 18

    method_labels = {
        "unconditioned_residual": "Unconditioned residual",
        "linear_residual": "Linear residual",
        "quadratic_residual": "Quadratic residual",
        "spline_residual": "Spline residual",
        "spline_local_scale": "Spline + local scale",
        "isolation_forest": "Isolation Forest",
        "min_cov_det": "MinCovDet",
    }
    feature_names = [
        "sequence_unbalance",
        "fundamental_amplitude_cv",
        "phase_rms_cv",
        "clarke_radius_cv",
        "zero_sequence_ratio",
        "spectral_entropy",
        "sideband_lower_ratio",
        "sideband_upper_ratio",
        "harmonic_2_ratio_mean",
        "harmonic_2_ratio_max",
        "harmonic_3_ratio_mean",
        "harmonic_3_ratio_max",
        "harmonic_4_ratio_mean",
        "harmonic_4_ratio_max",
        "harmonic_5_ratio_mean",
        "harmonic_5_ratio_max",
        "thd_2_to_5_mean",
        "rms_ratio_a",
        "crest_a",
        "kurtosis_a",
        "rms_ratio_b",
        "crest_b",
        "kurtosis_b",
        "rms_ratio_c",
        "crest_c",
        "kurtosis_c",
    ]
    assert metadata["outcome_features"] == feature_names

    sections = [
        (
            "---\n"
            'title: "Supplementary Material: When Healthy-Only Alarm Calibration Does Not Transport Across Permanent-Magnet Synchronous Machines"\n'
            'author: "Anonymous review version"\n'
            "---\n"
        ),
        (
            "# S1. Evidence chronology and immutable boundary\n\n"
            "The development method was chosen with development fault labels. The PMSG "
            "protocol, selected method, feature schema, healthy roles, windows, alpha, and "
            "failure gates were then frozen before a PMSG signal variable was deserialized. "
            "All later session-anchor analyses are post-reveal. A repository size query had "
            "already fetched some Git objects containing MAT blobs, but no signal array was "
            "checked out for analysis, loaded, plotted, or summarized; the precise claim is "
            "therefore a signal-unrevealed metadata freeze.\n\n"
            + md_table(
                ["Artifact", "SHA-256"],
                (
                    (name.replace("_", " "), f"`{digest}`")
                    for name, digest in evidence["frozen_hashes"].items()
                ),
            )
            + "\n\nThe PMSG source is tag `v1.1.0`, commit "
            "`e02fba475cf82b375412a7382143dc29da5241ef`, tree "
            "`65430929e4886935d463f1e1410b5476d255f4d4`. All 225 MAT files passed the "
            "common-schema and time-base audit without a compatibility patch."
        ),
        (
            "# S2. Feature and information schema\n\n"
            "The detector uses time and three phase currents. Development additionally loads "
            "commanded speed and filename load as exogenous context; confirmation uses filename "
            "speed and torque setting code. Fault current, relay state, measured angle/speed, "
            "voltage, dq quantities, and absolute current scale are excluded. The 26 ordered "
            "outcomes are:\n\n"
            + md_table(
                ["Index", "Feature"],
                ((index, f"`{name}`") for index, name in enumerate(feature_names, start=1)),
            )
            + "\n\nPMSG feature inventory: 117 standalone-health windows, 648 pre-fault "
            "windows, 432 active-fault windows, and 1,296 recovery windows, totaling 2,493 "
            "rows from 225 records. Only `t`, `Ia`, `Ib`, and `Ic` were deserialized."
        ),
        (
            "# S3. Complete development benchmark\n\n"
            "Values below use only the six interpolation loads (5--30 N m) for selection. "
            "Each method has 48 healthy test blocks and 288 fault blocks. Detection is the "
            "equal-record macro average of actionable block alarms. Development fault labels "
            "select the method; these rows are not external confirmation.\n\n"
            + md_table(
                [
                    "Method",
                    "Healthy alarms",
                    "FAR",
                    "Detection",
                    "Abstention",
                    "Eligible",
                ],
                (
                    (
                        method_labels[row["method"]],
                        f"{int(row['primary_health_actionable_alarms'])}/48",
                        pct(row["primary_health_block_actionable_far"]),
                        pct(row["primary_record_macro_actionable_detection"]),
                        pct(row["primary_fault_abstention"]),
                        "yes (selected)"
                        if row["method"] == "spline_residual"
                        else ("yes" if row["selection_eligible"] == "True" else "no"),
                    )
                    for row in development
                ),
            )
        ),
        (
            "# S4. Complete frozen PMSG benchmark\n\n"
            "All methods use the same 39-window healthy calibration role and 216 fault "
            "sessions. A pre-fault session alarms if any of its three frozen pre-fault windows "
            "alarms; a fault record is detected if either of two active windows alarms. Only "
            "the spline residual is confirmatory. No method passed the 5% FAR point gate.\n\n"
            + md_table(
                [
                    "Method",
                    "Threshold",
                    "Pre-fault alarms",
                    "FAR (95% Wilson)",
                    "Detected",
                    "Detection (95% Wilson)",
                    "AUROC",
                ],
                (
                    (
                        method_labels[row["method"]]
                        + (" **[selected]**" if row["method"] == "spline_residual" else ""),
                        f"{float(row['threshold']):.4f}",
                        f"{int(row['pre_fault_sessions_with_alarm'])}/216",
                        (
                            f"{pct(row['pre_fault_session_far'])} "
                            f"({pct(row['pre_fault_session_far_wilson_lower'])}--"
                            f"{pct(row['pre_fault_session_far_wilson_upper'])})"
                        ),
                        f"{int(row['fault_records_detected'])}/216",
                        (
                            f"{pct(row['fault_record_detection'])} "
                            f"({pct(row['fault_record_detection_wilson_lower'])}--"
                            f"{pct(row['fault_record_detection_wilson_upper'])})"
                        ),
                        f"{float(row['record_score_auroc']):.4f}",
                    )
                    for row in confirmation
                ),
            )
        ),
        (
            "# S5. Frozen selected-method condition results\n\n"
            "Each speed-by-setting cell contains 24 sessions. These repetitions come from one "
            "physical PMSG and are not population replicates. Setting codes 52, 64, and 80 "
            "are not asserted to be N m.\n\n"
            + md_table(
                ["Facet", "Level", "Records", "Detection", "Pre-fault FAR"],
                (
                    (
                        row["facet"],
                        row["level"],
                        row["records"],
                        pct(row["record_detection"]),
                        pct(row["pre_session_far"]),
                    )
                    for row in condition
                ),
            )
            + "\n\n## S5.1 Fault-topology rows\n\n"
            + md_table(
                [
                    "Family",
                    "Terminals",
                    "Span (%)",
                    "Detection",
                    "Pre-fault FAR",
                    "First-window detection",
                ],
                (
                    (
                        row["fault_family"],
                        f"{row['terminal_a']}--{row['terminal_b']}",
                        f"{float(row['fault_span_percent']):.2f}",
                        pct(row["detection"]),
                        pct(row["pre_session_far"]),
                        pct(row["first_window_detection"]),
                    )
                    for row in fault_cases
                ),
            )
        ),
        (
            "# S6. Post-reveal session analyses\n\n"
            "These analyses were specified only after the independent PMSG result was known. "
            "They cannot replace confirmation.\n\n"
            + md_table(
                ["Analysis", "False alarms", "FAR", "Detected", "Detection", "First/second/censored"],
                (
                    (
                        "Session anchor",
                        f"{int(session['pre_fault_false_alarms'])}/216",
                        pct(session["pre_fault_session_far"]),
                        f"{int(session['fault_records_detected'])}/216",
                        pct(session["fault_record_detection"]),
                        f"{session['detected_first_window']}/{session['detected_second_window_only']}/{session['censored_beyond_0p4s']}",
                    ),
                    (
                        "Matched-session topology cross-fit",
                        f"{int(topology['pre_false_alarms'])}/216",
                        pct(topology["pre_session_far"]),
                        f"{int(topology['fault_records_detected'])}/216",
                        pct(topology["fault_record_detection"]),
                        f"{topology['detected_first_window']}/{topology['detected_second_window_only']}/{topology['censored_beyond_0p4s']}",
                    ),
                    (
                        "Conditioned-anchor topology cross-fit",
                        f"{int(conditioned['pre_false_alarms'])}/216",
                        pct(conditioned["pre_session_far"]),
                        f"{int(conditioned['fault_records_detected'])}/216",
                        pct(conditioned["fault_record_detection"]),
                        f"{conditioned['detected_first_window']}/{conditioned['detected_second_window_only']}/{conditioned['censored_beyond_0p4s']}",
                    ),
                ),
            )
            + "\n\n## S6.1 Topology-disjoint fold results\n\n"
            + md_table(
                ["Analysis", "Fold", "Threshold", "False alarms", "FAR", "Detected", "Detection"],
                (
                    (
                        label,
                        int(row["outer_fold"]) + 1,
                        f"{float(row['threshold']):.4f}",
                        row["pre_false_alarms"],
                        pct(row["pre_session_far"]),
                        row["fault_records_detected"],
                        pct(row["fault_record_detection"]),
                    )
                    for label, rows in (
                        ("Matched anchor", topology_folds),
                        ("Conditioned anchor", conditioned_folds),
                    )
                    for row in rows
                ),
            )
        ),
        (
            "# S7. Reproducibility and claim restrictions\n\n"
            "Run the feature/container audit, development benchmark, confirmation analysis, "
            "three session analyses, figure builder, and evidence validator in the order "
            "listed in `README_REPRODUCE.md`. The evidence validator checks seven immutable "
            "hashes, all headline numerators/denominators, the complete 3x3 condition grid, "
            "threshold instability, manuscript citations, and all ten figure files.\n\n"
            "The following restrictions apply to every table and figure:\n\n"
            "- two physical machines do not establish a fleet-population result;\n"
            "- the 216 PMSG files are sessions/conditions, not independent machines;\n"
            "- Wilson intervals are descriptive under dependence;\n"
            "- motor-to-generator, topology, acquisition, and laboratory changes are "
            "confounded;\n"
            "- post-reveal session repairs are internal mechanism analyses;\n"
            "- censoring beyond 0.4 s is not proof of no later alarm;\n"
            "- external abstention was zero, so context support did not detect conditional "
            "feature shift.\n\n"
            + md_table(
                ["File", "SHA-256"],
                (
                    (str(path.relative_to(ROOT)), f"`{sha256(path)}`")
                    for path in (
                        ROOT / "papers/paper3_calibration_transport/manuscript.md",
                        ROOT / "docs/paper3_reveal_log.md",
                        ROOT / "docs/paper3_literature_gap.md",
                        ROOT / "results/paper3_development/aggregate_summary.csv",
                        ROOT / "results/paper3_pmsg_confirmation/aggregate_summary.csv",
                        ROOT / "results/paper3_pmsg_session_anchor/summary.json",
                        ROOT / "results/paper3_pmsg_topology_crossfit/summary.json",
                        ROOT / "results/paper3_pmsg_conditioned_anchor/summary.json",
                    )
                ),
            )
        ),
    ]
    return "\n\n".join(sections).rstrip() + "\n"


def main() -> None:
    args = parse_args()
    output = args.output.resolve()
    content = build_content()
    if args.check:
        if not output.exists() or output.read_text(encoding="utf-8") != content:
            raise SystemExit(f"supplement is missing or stale: {output}")
        print(f"supplement is current: {output}")
        return
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(content, encoding="utf-8")
    print(f"wrote supplementary material to {output}")


if __name__ == "__main__":
    main()
