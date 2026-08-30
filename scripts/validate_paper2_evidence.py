"""Mechanically validate Paper 2 headline evidence and submission artifacts."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import sys
from pathlib import Path
from typing import Any

import pandas as pd

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from audit_reference_metadata import cited_keys, parse_bibtex

ROOT = Path(__file__).resolve().parents[1]
PRIMARY_MODEL = "ard_gaussian_process"
PRIMARY_SEED = 20260821
EXPECTED_DESIGNS = {
    "internal_uniform": 200,
    "uq_uniform": 11_250,
    "uq_gauss_shift": 10_000,
}
FIGURE_STEMS = (
    "paper2_protocol_workflow",
    "paper2_coverage_width",
    "paper2_distance_conditioning",
    "paper2_seed_sensitivity",
    "paper2_representative_curves",
)


def _assert_close(actual: float, expected: float, *, tolerance: float = 1e-12) -> None:
    if not math.isclose(actual, expected, rel_tol=0.0, abs_tol=tolerance):
        raise AssertionError(f"Expected {expected}, got {actual}")


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _primary_aggregate(root: Path) -> pd.DataFrame:
    aggregate = pd.read_csv(
        root / "results" / "paper2_torque_conformal" / "aggregate_summary.csv"
    )
    return aggregate.loc[
        aggregate["model"].eq(PRIMARY_MODEL)
        & aggregate["seed"].astype(int).eq(PRIMARY_SEED)
    ].copy()


def recompute_primary(root: Path) -> dict[str, Any]:
    result_dir = root / "results" / "paper2_torque_conformal"
    per_design = pd.read_csv(result_dir / "primary_per_design_scores.csv.gz")
    aggregate = _primary_aggregate(root)
    expected_rows = 2 * sum(EXPECTED_DESIGNS.values())
    if len(per_design) != expected_rows:
        raise AssertionError(f"Expected {expected_rows} primary rows, got {len(per_design)}")

    summaries: dict[str, dict[str, dict[str, float | int]]] = {}
    for distribution, designs in EXPECTED_DESIGNS.items():
        summaries[distribution] = {}
        for band in ("global", "geometry_scaled"):
            group = per_design.loc[
                per_design["distribution"].eq(distribution)
                & per_design["band"].eq(band)
            ].copy()
            if len(group) != designs or group["row_index"].nunique() != designs:
                raise AssertionError(f"Unexpected inventory for {distribution}/{band}")
            accepted = group.loc[~group["support_rejected"].astype(bool)]
            summary = {
                "designs": len(group),
                "covered_designs": int(group["covered"].sum()),
                "coverage": float(group["covered"].mean()),
                "mean_half_width": float(group["half_width"].mean()),
                "support_rejected": int(group["support_rejected"].sum()),
                "support_rejection_rate": float(group["support_rejected"].mean()),
                "accepted_coverage": float(accepted["covered"].mean()),
            }
            row = aggregate.loc[
                aggregate["distribution"].eq(distribution)
                & aggregate["band"].eq(band)
                & aggregate["alpha"].eq(0.10)
            ]
            if len(row) != 1:
                raise AssertionError(f"Missing aggregate row for {distribution}/{band}")
            row = row.iloc[0]
            _assert_close(summary["coverage"], float(row["curvewise_coverage"]))
            _assert_close(summary["mean_half_width"], float(row["mean_half_width"]))
            _assert_close(
                summary["support_rejection_rate"], float(row["support_rejection_rate"])
            )
            _assert_close(
                summary["accepted_coverage"], float(row["accepted_curvewise_coverage"])
            )
            summaries[distribution][band] = summary

    global_rows = per_design.loc[per_design["band"].eq("global")].copy()
    scaled_widths = per_design.loc[
        per_design["band"].eq("geometry_scaled"),
        ["distribution", "row_index", "half_width", "covered"],
    ].rename(
        columns={
            "half_width": "scaled_half_width",
            "covered": "scaled_covered",
        }
    )
    global_rows = global_rows.merge(
        scaled_widths,
        on=["distribution", "row_index"],
        how="inner",
        validate="one_to_one",
    )
    quintile_parts: list[pd.DataFrame] = []
    bin_rows: list[dict[str, float | int | str]] = []
    for distribution, group in global_rows.groupby("distribution", sort=True):
        group = group.copy()
        labels, bins = pd.qcut(
            group["geometry_scale"], 5, labels=False, retbins=True
        )
        group["distance_quintile"] = labels + 1
        quintile_parts.append(group)
        bin_rows.extend(
            {
                "distribution": distribution,
                "distance_quintile": quintile + 1,
                "scale_lower": float(bins[quintile]),
                "scale_upper": float(bins[quintile + 1]),
            }
            for quintile in range(5)
        )
    global_rows = pd.concat(quintile_parts, ignore_index=True)
    computed_quintiles = (
        global_rows.groupby(["distribution", "distance_quintile"], sort=True)
        .agg(
            designs=("row_index", "size"),
            mean_curve_max_error=("curve_max_error", "mean"),
            global_coverage=("covered", "mean"),
            geometry_scaled_coverage=("scaled_covered", "mean"),
            mean_geometry_scaled_half_width=("scaled_half_width", "mean"),
        )
        .reset_index()
    )
    computed_quintiles = computed_quintiles.merge(
        pd.DataFrame(bin_rows),
        on=["distribution", "distance_quintile"],
        validate="one_to_one",
    )
    frozen_quintiles = pd.read_csv(result_dir / "primary_distance_quintiles.csv")
    merged = computed_quintiles.merge(
        frozen_quintiles,
        on=["distribution", "distance_quintile"],
        suffixes=("_computed", "_frozen"),
        validate="one_to_one",
    )
    if len(merged) != 15:
        raise AssertionError("Expected three distributions by five distance quintiles")
    for column in (
        "designs",
        "scale_lower",
        "scale_upper",
        "mean_curve_max_error",
        "global_coverage",
        "geometry_scaled_coverage",
        "mean_geometry_scaled_half_width",
    ):
        differences = (
            merged[f"{column}_computed"].astype(float)
            - merged[f"{column}_frozen"].astype(float)
        ).abs()
        if float(differences.max()) > 1e-12:
            raise AssertionError(f"Distance-quintile drift in {column}")

    uniform_q5 = computed_quintiles.loc[
        computed_quintiles["distribution"].eq("uq_uniform")
        & computed_quintiles["distance_quintile"].eq(5)
    ].iloc[0]
    _assert_close(float(uniform_q5["global_coverage"]), 0.7613333333333333)
    _assert_close(float(uniform_q5["geometry_scaled_coverage"]), 0.7831111111111111)
    _assert_close(summaries["uq_uniform"]["global"]["coverage"], 0.9029333333333334)
    _assert_close(
        summaries["uq_uniform"]["geometry_scaled"]["coverage"],
        0.8996444444444445,
    )
    _assert_close(summaries["uq_gauss_shift"]["global"]["coverage"], 1.0)

    seed_frame = pd.read_csv(
        root / "results" / "paper2_torque_seed_sensitivity" / "aggregate_summary.csv"
    )
    seed_frame = seed_frame.loc[
        seed_frame["model"].eq(PRIMARY_MODEL) & seed_frame["alpha"].eq(0.10)
    ].copy()
    if seed_frame["seed"].nunique() != 5:
        raise AssertionError("Paper 2 seed sensitivity must contain exactly five seeds")
    seed_ranges: dict[str, dict[str, float]] = {}
    for distribution in EXPECTED_DESIGNS:
        for band in ("global", "geometry_scaled"):
            group = seed_frame.loc[
                seed_frame["distribution"].eq(distribution)
                & seed_frame["band"].eq(band)
            ]
            key = f"{distribution}/{band}"
            seed_ranges[key] = {
                "coverage_min": float(group["curvewise_coverage"].min()),
                "coverage_mean": float(group["curvewise_coverage"].mean()),
                "coverage_max": float(group["curvewise_coverage"].max()),
                "width_min": float(group["mean_half_width"].min()),
                "width_max": float(group["mean_half_width"].max()),
            }
    _assert_close(seed_ranges["uq_uniform/global"]["coverage_min"], 0.8799111111111111)
    _assert_close(seed_ranges["uq_uniform/global"]["coverage_max"], 0.9108444444444445)

    return {
        "aggregate": summaries,
        "uniform_sparse_quintile": {
            key: float(uniform_q5[key])
            for key in (
                "designs",
                "mean_curve_max_error",
                "global_coverage",
                "geometry_scaled_coverage",
                "mean_geometry_scaled_half_width",
            )
        },
        "seed_ranges": seed_ranges,
    }


def recompute_weighted(root: Path) -> dict[str, Any]:
    result_dir = root / "results" / "paper2_weighted_conformal"
    per_design = pd.read_csv(result_dir / "weighted_per_design.csv.gz")
    comparison = pd.read_csv(result_dir / "comparison_summary.csv")
    density = pd.read_csv(result_dir / "density_ratio_diagnostics.csv")
    output: dict[str, Any] = {}

    for target, designs in (("uq_uniform", 5_625), ("uq_gauss", 5_000)):
        rows = per_design.loc[
            per_design["target_distribution"].eq(target)
            & per_design["alpha"].eq(0.10)
        ].copy()
        if len(rows) != designs:
            raise AssertionError(f"Unexpected weighted inventory for {target}")
        finite = rows["weighted_band_finite"].astype(bool)
        finite_rows = rows.loc[finite]
        comparison_row = comparison.loc[
            comparison["target_distribution"].eq(target)
            & comparison["method"].eq("estimated_weighted_split_conformal")
            & comparison["alpha"].eq(0.10)
        ]
        if len(comparison_row) != 1:
            raise AssertionError(f"Missing weighted comparison row for {target}")
        comparison_row = comparison_row.iloc[0]
        source_weights = density.loc[
            density["target_distribution"].eq(target)
            & density["role"].eq("source_calibration")
        ]
        if len(source_weights) != 1:
            raise AssertionError(f"Missing source weight diagnostics for {target}")
        source_weights = source_weights.iloc[0]
        summary = {
            "designs": len(rows),
            "finite_bands": int(finite.sum()),
            "coverage_including_vacuous": float(
                rows["weighted_band_covered_including_vacuous"].mean()
            ),
            "finite_band_coverage": (
                float(finite_rows["weighted_band_covered_including_vacuous"].mean())
                if len(finite_rows)
                else None
            ),
            "mean_finite_half_width": (
                float(finite_rows["weighted_half_width"].mean())
                if len(finite_rows)
                else None
            ),
            "heldout_domain_auc": float(source_weights["heldout_domain_auc"]),
            "calibration_weight_ess": float(source_weights["effective_sample_size"]),
            "max_normalized_calibration_weight": float(
                source_weights["max_normalized_weight"]
            ),
        }
        if summary["finite_bands"] != int(comparison_row["finite_bands"]):
            raise AssertionError(f"Weighted finite-band mismatch for {target}")
        _assert_close(
            summary["coverage_including_vacuous"],
            float(comparison_row["curvewise_coverage_including_vacuous"]),
        )
        if summary["mean_finite_half_width"] is not None:
            _assert_close(
                summary["mean_finite_half_width"],
                float(comparison_row["mean_finite_half_width"]),
            )
        output[target] = summary

    _assert_close(output["uq_uniform"]["calibration_weight_ess"], 516.5040316436168)
    _assert_close(output["uq_uniform"]["finite_band_coverage"], 0.9198222222222222)
    _assert_close(output["uq_gauss"]["heldout_domain_auc"], 1.0)
    _assert_close(output["uq_gauss"]["calibration_weight_ess"], 4.3063191510830485)
    if output["uq_gauss"]["finite_bands"] != 0:
        raise AssertionError("Gaussian weighted bands are expected to remain fully vacuous")
    return output


def validate_manuscript_and_artifacts(root: Path) -> dict[str, Any]:
    manuscript = root / "papers" / "paper2_torque_uq" / "manuscript.md"
    text = manuscript.read_text(encoding="utf-8")
    normalized_text = " ".join(text.split())
    required_phrases = (
        "11,250 independent uniform designs",
        "90.293% coverage",
        "76.13% in the sparsest",
        "78.31%",
        "0 / 5,000",
        "ESS 4.31",
        "21.4%",
        "not an exact reproduction",
        "It is not evidence of cross-machine",
        "simulator model-form error",
    )
    missing = [phrase for phrase in required_phrases if phrase not in normalized_text]
    if missing:
        raise AssertionError(f"Required Paper 2 manuscript evidence missing: {missing}")

    bibliography = root / "references" / "key_papers.bib"
    records = parse_bibtex(bibliography)
    citations = cited_keys(manuscript)
    undefined = sorted(set(citations) - set(records))
    if undefined:
        raise AssertionError(f"Undefined Paper 2 citations: {undefined}")

    figures_dir = root / "papers" / "paper2_torque_uq" / "figures"
    figure_files = [
        figures_dir / f"{stem}.{suffix}"
        for stem in FIGURE_STEMS
        for suffix in ("png", "pdf")
    ]
    missing_figures = [str(path) for path in figure_files if not path.is_file()]
    if missing_figures:
        raise AssertionError(f"Missing Paper 2 figures: {missing_figures}")
    empty_figures = [str(path) for path in figure_files if path.stat().st_size < 1_000]
    if empty_figures:
        raise AssertionError(f"Unexpectedly small Paper 2 figures: {empty_figures}")

    return {
        "manuscript_words": len(text.split()),
        "citation_keys": list(citations),
        "citation_count": len(citations),
        "required_phrases": list(required_phrases),
        "figure_files": [str(path.relative_to(root)) for path in figure_files],
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=ROOT)
    parser.add_argument(
        "--output",
        type=Path,
        default=ROOT / "results" / "paper2_evidence_validation" / "evidence.json",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    inputs = (
        args.root / "results" / "paper2_torque_conformal" / "aggregate_summary.csv",
        args.root
        / "results"
        / "paper2_torque_conformal"
        / "primary_per_design_scores.csv.gz",
        args.root / "results" / "paper2_weighted_conformal" / "comparison_summary.csv",
        args.root
        / "results"
        / "paper2_weighted_conformal"
        / "weighted_per_design.csv.gz",
        args.root / "papers" / "paper2_torque_uq" / "manuscript.md",
    )
    evidence = {
        "status": "pass",
        "primary": recompute_primary(args.root),
        "weighted": recompute_weighted(args.root),
        "artifacts": validate_manuscript_and_artifacts(args.root),
        "input_sha256": {
            str(path.relative_to(args.root)): _sha256(path) for path in inputs
        },
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(evidence, indent=2, sort_keys=True), encoding="utf-8")
    print(json.dumps({"status": "pass", "output": str(args.output), "checks": 4}))


if __name__ == "__main__":
    main()
