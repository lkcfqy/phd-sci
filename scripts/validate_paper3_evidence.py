"""Mechanically validate Paper 3 headline evidence and manuscript artifacts."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pandas as pd

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from audit_reference_metadata import cited_keys, parse_bibtex

ROOT = Path(__file__).resolve().parents[1]
FIGURE_STEMS = (
    "paper3_method_transport",
    "paper3_session_repair",
    "paper3_topology_fold_stability",
    "paper3_condition_heatmap",
    "paper3_first_alarm",
)
EXPECTED_HASHES = {
    "development_features": "c3e7e13919a8868580bd3af8c501d8f022600f5a2637460470479ad7faff4743",
    "development_protocol_json": "a37d38937aee35ae0ed44c5c139a4e0daf54cd85a03f1e105b8cc6ab5f071ec9",
    "development_selection": "1cccd12c8d7b8d4c6ad40b0a96ebd46ec839739b84b30512a8d4b7ca77324bf5",
    "confirmation_protocol": "4fc0d12e1e69c09776f8c0f691eddf38552bdf2f7512dc71c426103cc349bfd9",
    "confirmation_inventory": "4890f864e40fc3345f5af37364a6acf7d854af4ab94b57ebc73e2def94a36914",
    "confirmation_features": "78bbc520ada5bcfe6f3dc419968e64892aaba48743f5976443cdf4f136346040",
    "confirmation_primary": "f119fde0c7bc6625abc43d68769602305bf24e0e949a3f7c5e301b36634a63cb",
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=ROOT)
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("papers/paper3_calibration_transport/evidence_validation.json"),
    )
    return parser.parse_args()


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def assert_close(actual: float, expected: float, *, tolerance: float = 1e-12) -> None:
    if not math.isclose(actual, expected, rel_tol=0.0, abs_tol=tolerance):
        raise AssertionError(f"expected {expected}, got {actual}")


def nested_summary(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    summary = payload.get("summary", payload)
    if not isinstance(summary, dict):
        raise TypeError(f"{path} does not contain a summary object")
    return summary


def validate_hashes(root: Path) -> dict[str, str]:
    paths = {
        "development_features": root
        / "data/processed/paper3_development_features.csv.gz",
        "development_protocol_json": root / "results/paper3_development/protocol.json",
        "development_selection": root
        / "results/paper3_development/selected_method.json",
        "confirmation_protocol": root / "docs/paper3_confirmation_protocol.md",
        "confirmation_inventory": root
        / "results/paper3_confirmation_preregistration/metadata_inventory.csv",
        "confirmation_features": root
        / "data/processed/paper3_pmsg_confirmation_features.csv.gz",
        "confirmation_primary": root
        / "results/paper3_pmsg_confirmation/selected_method_primary.json",
    }
    observed = {name: sha256(path) for name, path in paths.items()}
    if observed != EXPECTED_HASHES:
        differences = {
            name: {"expected": EXPECTED_HASHES[name], "observed": observed[name]}
            for name in EXPECTED_HASHES
            if observed[name] != EXPECTED_HASHES[name]
        }
        raise AssertionError(f"Paper 3 frozen hash mismatch: {differences}")
    return observed


def validate_development(root: Path) -> dict[str, Any]:
    result_dir = root / "results/paper3_development"
    aggregate = pd.read_csv(result_dir / "aggregate_summary.csv")
    if len(aggregate) != 7 or aggregate["method"].nunique() != 7:
        raise AssertionError("development must contain seven unique methods")
    selected_payload = json.loads(
        (result_dir / "selected_method.json").read_text(encoding="utf-8")
    )
    if selected_payload["selected_method"] != "spline_residual":
        raise AssertionError("unexpected development-selected method")
    row = aggregate.loc[aggregate["method"].eq("spline_residual")]
    if len(row) != 1:
        raise AssertionError("missing spline development row")
    row = row.iloc[0]
    if int(row["primary_health_blocks"]) != 48:
        raise AssertionError("unexpected primary development health denominator")
    if int(row["primary_health_actionable_alarms"]) != 1:
        raise AssertionError("unexpected primary development health alarms")
    if int(row["primary_fault_blocks"]) != 288:
        raise AssertionError("unexpected primary development fault blocks")
    assert_close(float(row["primary_health_block_actionable_far"]), 1 / 48)
    assert_close(
        float(row["primary_record_macro_actionable_detection"]), 237 / 288
    )
    if not bool(row["selection_eligible"]):
        raise AssertionError("selected development method must be eligible")
    return {
        "methods": len(aggregate),
        "selected_method": "spline_residual",
        "primary_health_alarms": 1,
        "primary_health_blocks": 48,
        "primary_fault_detected_blocks": 237,
        "primary_fault_blocks": 288,
    }


def validate_confirmation(root: Path) -> dict[str, Any]:
    result_dir = root / "results/paper3_pmsg_confirmation"
    aggregate = pd.read_csv(result_dir / "aggregate_summary.csv")
    if len(aggregate) != 7 or aggregate["method"].nunique() != 7:
        raise AssertionError("confirmation must contain seven unique methods")
    selected = aggregate.loc[aggregate["method"].eq("spline_residual")]
    if len(selected) != 1:
        raise AssertionError("missing frozen spline confirmation row")
    selected = selected.iloc[0]
    exact = {
        "calibration_windows": 39,
        "pre_fault_records": 216,
        "pre_fault_sessions_with_alarm": 71,
        "fault_records": 216,
        "fault_records_detected": 156,
        "detected_by_first_window": 127,
        "detected_by_second_window_only": 29,
        "censored_beyond_0p4s": 60,
        "fault_records_abstained": 0,
    }
    for column, expected in exact.items():
        if int(selected[column]) != expected:
            raise AssertionError(f"confirmation {column}: expected {expected}")
    assert_close(float(selected["pre_fault_session_far"]), 71 / 216)
    assert_close(float(selected["fault_record_detection"]), 156 / 216)
    if bool(selected["confirmatory_gates_all_pass"]):
        raise AssertionError("failed independent confirmation cannot be marked as passing")
    if aggregate["pre_fault_session_far"].le(0.05).any():
        raise AssertionError("no frozen PMSG method should pass the 5% FAR gate")
    condition = pd.read_csv(result_dir / "selected_condition_summary.csv")
    grid = condition.loc[condition["facet"].eq("speed_by_torque")]
    if len(grid) != 9 or not grid["records"].eq(24).all():
        raise AssertionError("expected a complete 3x3 PMSG condition grid")
    return exact | {
        "pre_fault_session_far": float(selected["pre_fault_session_far"]),
        "fault_record_detection": float(selected["fault_record_detection"]),
        "all_frozen_methods_fail_far_gate": True,
    }


def validate_post_reveal(root: Path) -> dict[str, dict[str, int | float]]:
    specifications = {
        "session_anchor": (
            root / "results/paper3_pmsg_session_anchor/summary.json",
            "pre_fault_false_alarms",
            17,
            167,
        ),
        "matched_anchor": (
            root / "results/paper3_pmsg_topology_crossfit/summary.json",
            "pre_false_alarms",
            14,
            153,
        ),
        "conditioned_anchor": (
            root / "results/paper3_pmsg_conditioned_anchor/summary.json",
            "pre_false_alarms",
            18,
            154,
        ),
    }
    output: dict[str, dict[str, int | float]] = {}
    for label, (path, false_alarm_key, false_alarms, detected) in specifications.items():
        summary = nested_summary(path)
        records = int(summary.get("records", summary.get("fault_records", -1)))
        if records != 216:
            raise AssertionError(f"{label} must contain 216 records")
        if int(summary[false_alarm_key]) != false_alarms:
            raise AssertionError(f"unexpected {label} false-alarm count")
        if int(summary["fault_records_detected"]) != detected:
            raise AssertionError(f"unexpected {label} detection count")
        output[label] = {
            "records": records,
            "false_alarms": false_alarms,
            "far": false_alarms / records,
            "detected": detected,
            "detection": detected / records,
        }
    topology_folds = pd.read_csv(
        root / "results/paper3_pmsg_topology_crossfit/per_fold_summary.csv"
    )
    conditioned_folds = pd.read_csv(
        root / "results/paper3_pmsg_conditioned_anchor/per_fold_summary.csv"
    )
    if len(topology_folds) != 3 or len(conditioned_folds) != 3:
        raise AssertionError("topology cross-fit analyses require three folds")
    if topology_folds["threshold"].max() / topology_folds["threshold"].min() < 2.5:
        raise AssertionError("matched-anchor threshold instability was not reproduced")
    if conditioned_folds["threshold"].max() / conditioned_folds["threshold"].min() < 2.9:
        raise AssertionError("conditioned-anchor threshold instability was not reproduced")
    return output


def validate_manuscript(root: Path) -> dict[str, Any]:
    paper_dir = root / "papers/paper3_calibration_transport"
    manuscript = paper_dir / "manuscript.md"
    text = manuscript.read_text(encoding="utf-8")
    required_phrases = (
        "71/216",
        "156/216",
        "17/216",
        "14/216",
        "18/216",
        "signal-unrevealed metadata freeze",
        "post-reveal",
        "right-censored",
        "does not identify",
    )
    missing_phrases = [phrase for phrase in required_phrases if phrase not in text]
    if missing_phrases:
        raise AssertionError(f"manuscript missing evidence phrases: {missing_phrases}")
    if "preregistered" in text.lower():
        raise AssertionError("use protocol-frozen/predeclared, not public-preregistration wording")
    bibliography = parse_bibtex(root / "references/key_papers.bib")
    citations = cited_keys(manuscript)
    missing_citations = sorted(set(citations) - set(bibliography))
    if missing_citations:
        raise AssertionError(f"manuscript citations missing from BibTeX: {missing_citations}")
    figure_hashes: dict[str, dict[str, str]] = {}
    for stem in FIGURE_STEMS:
        paths = {
            suffix: paper_dir / "figures" / f"{stem}.{suffix}"
            for suffix in ("png", "pdf")
        }
        for path in paths.values():
            if not path.exists() or path.stat().st_size < 10_000:
                raise AssertionError(f"missing or undersized figure: {path}")
        figure_hashes[stem] = {suffix: sha256(path) for suffix, path in paths.items()}
    return {
        "word_count_approximate": len(text.split()),
        "citation_count": len(citations),
        "manuscript_sha256": sha256(manuscript),
        "figure_hashes": figure_hashes,
    }


def main() -> None:
    args = parse_args()
    root = args.root.resolve()
    output = args.output if args.output.is_absolute() else root / args.output
    payload = {
        "created_utc": datetime.now(UTC).isoformat(),
        "status": "pass",
        "frozen_hashes": validate_hashes(root),
        "development": validate_development(root),
        "independent_confirmation": validate_confirmation(root),
        "post_reveal": validate_post_reveal(root),
        "manuscript": validate_manuscript(root),
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    print(json.dumps(payload, indent=2))
    print(f"wrote validation report to {output}")


if __name__ == "__main__":
    main()
