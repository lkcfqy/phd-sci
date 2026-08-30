"""Build the evidence-backed supplementary material for Paper 2."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
from collections.abc import Iterable, Sequence
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "papers" / "paper2_torque_uq" / "supplementary_material.md"
RESULTS = ROOT / "results"


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


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


def decimal(value: str | float, digits: int = 6) -> str:
    return f"{float(value):.{digits}f}"


def build_content() -> str:
    audit_dir = RESULTS / "paper2_torque_data_audit"
    conformal_dir = RESULTS / "paper2_torque_conformal"
    seed_dir = RESULTS / "paper2_torque_seed_sensitivity"
    weighted_dir = RESULTS / "paper2_weighted_conformal"

    datasets = read_csv(audit_dir / "dataset_summary.csv")
    files = read_csv(audit_dir / "file_manifest.csv")
    overlaps = read_csv(audit_dir / "cross_table_overlap.csv")
    aggregate = read_csv(conformal_dir / "aggregate_summary.csv")
    quintiles = read_csv(conformal_dir / "primary_distance_quintiles.csv")
    selection = read_csv(conformal_dir / "source_only_hyperparameter_selection.csv")
    timings = read_csv(conformal_dir / "timings.csv")
    seeds = read_csv(seed_dir / "aggregate_summary.csv")
    weighted = read_csv(weighted_dir / "comparison_summary.csv")
    density = read_csv(weighted_dir / "density_ratio_diagnostics.csv")
    representatives = read_csv(
        RESULTS / "paper2_representative_curves" / "selection_manifest.csv"
    )
    evidence = json.loads(
        (RESULTS / "paper2_evidence_validation" / "evidence.json").read_text(
            encoding="utf-8"
        )
    )

    primary = [
        row
        for row in aggregate
        if row["model"] == "ard_gaussian_process"
        and row["distribution"]
        in {"internal_uniform", "uq_uniform", "uq_gauss_shift"}
    ]
    primary.sort(
        key=lambda row: (
            {"internal_uniform": 0, "uq_uniform": 1, "uq_gauss_shift": 2}[
                row["distribution"]
            ],
            float(row["alpha"]),
            {"global": 0, "geometry_scaled": 1}[row["band"]],
        )
    )
    distance_rows = [
        row
        for row in quintiles
        if row["distribution"] in {"uq_uniform", "uq_gauss_shift"}
    ]
    distance_rows.sort(
        key=lambda row: (
            {"uq_uniform": 0, "uq_gauss_shift": 1}[row["distribution"]],
            int(row["distance_quintile"]),
        )
    )
    seed_rows = [
        row
        for row in seeds
        if row["model"] == "ard_gaussian_process" and float(row["alpha"]) == 0.1
    ]
    seed_rows.sort(
        key=lambda row: (
            [20260821, 1201, 2402, 3603, 4804].index(int(row["seed"])),
            {"internal_uniform": 0, "uq_uniform": 1, "uq_gauss_shift": 2}[
                row["distribution"]
            ],
            {"global": 0, "geometry_scaled": 1}[row["band"]],
        )
    )

    assert evidence["status"] == "pass"
    assert len(datasets) == 3 and sum(int(row["designs"]) for row in datasets) == 23250
    assert len(files) == 6 and all(int(row["bytes"]) > 0 for row in files)
    assert len(overlaps) == 3 and all(
        int(row["exact_parameter_row_overlap"]) == 0 for row in overlaps
    )
    assert len(primary) == 12
    assert len(distance_rows) == 10
    assert len(seed_rows) == 30
    assert len(weighted) == 12
    assert len(density) == 4
    assert len(representatives) == 4
    sparse = next(
        row
        for row in distance_rows
        if row["distribution"] == "uq_uniform"
        and row["distance_quintile"] == "5"
    )
    assert abs(float(sparse["global_coverage"]) - 0.7613333333333333) < 1e-12
    assert abs(float(sparse["geometry_scaled_coverage"]) - 0.7831111111111111) < 1e-12
    gaussian_weighted = next(
        row
        for row in weighted
        if row["target_distribution"] == "uq_gauss"
        and row["method"] == "estimated_weighted_split_conformal"
        and float(row["alpha"]) == 0.1
    )
    assert int(gaussian_weighted["finite_bands"]) == 0

    dataset_names = {
        "train_test": "development/internal",
        "uq_uniform": "large uniform evaluation",
        "uq_gauss": "Gaussian-shift evaluation",
    }
    distribution_names = {
        "internal_uniform": "fixed internal uniform",
        "uq_uniform": "large uniform",
        "uq_gauss_shift": "Gaussian density shift",
        "uq_gauss": "Gaussian density shift",
    }
    band_names = {"global": "global", "geometry_scaled": "geometry-scaled"}
    method_names = {
        "global_split_conformal": "global",
        "geometry_scaled_split_conformal": "geometry-scaled",
        "estimated_weighted_split_conformal": "estimated weighted",
    }

    selected_models = [row for row in selection if row["selected"] == "1"]
    selected_models.sort(
        key=lambda row: [
            "poly2_ridge",
            "rbf_kernel_ridge",
            "ard_gaussian_process",
            "extra_trees",
        ].index(row["model"])
    )

    sections: list[str] = [
        (
            "---\n"
            'title: "Supplementary Material: Curvewise Conformal Prediction Bands for Periodic PMSM Torque Surrogates"\n'
            'author: "Anonymous review version"\n'
            "---\n"
        ),
        "# S1. Data inventory and integrity audit\n\n"
        "The released archive (DOI `10.5281/zenodo.15688397`) contains 23,250 "
        "independent simulated geometries from one two-dimensional, quarter-symmetry PMSM "
        "model. Each geometry has 20 inputs and a 120-angle torque period. The archive is "
        "licensed GPL-3.0-or-later. These are simulator rows, not independent machines or "
        "hardware measurements.\n\n"
        + md_table(
            [
                "Published table",
                "Study role",
                "Designs",
                "Torque range",
                "Median retained Fourier energy",
            ],
            (
                (
                    row["dataset"],
                    dataset_names[row["dataset"]],
                    f"{int(row['designs']):,}",
                    f"{float(row['torque_min']):.6f}-{float(row['torque_max']):.6f}",
                    f"{100 * float(row['retained_energy_median']):.7f}%",
                )
                for row in datasets
            ),
        )
        + "\n\nAll values were finite. The audit found no duplicate parameter rows, no "
        "duplicate torque rows, and zero exact parameter-row overlap in each of the three "
        "pairwise table comparisons. All files shared the 0-29.75 degree grid at 0.25-degree "
        "increments. The audit establishes row integrity and absence of exact reuse; it does "
        "not establish fidelity beyond the source simulator.\n\n"
        + md_table(
            ["Dataset", "Role", "File", "Bytes", "SHA-256"],
            (
                (
                    row["dataset"],
                    row["role"],
                    row["file"],
                    f"{int(row['bytes']):,}",
                    f"`{row['sha256']}`",
                )
                for row in files
            ),
        ),
        (
            "# S2. Frozen roles, splits, and endpoints\n\n"
            "Rows 1-1,800 of `train_test` form the development pool. Seed 20260821 selects "
            "1,200 fit rows and 600 calibration rows; the final 200 rows remain an internal "
            "evaluation set. The 11,250 uniform and 10,000 Gaussian rows never select a model or "
            "hyperparameter. Four additional deterministic seeds (1201, 2402, 3603, and 4804) "
            "repeat only the fit/calibration split.\n\n"
            "The primary endpoint is simultaneous full-curve coverage at nominal 90% "
            "(`alpha=0.10`); 95% is a frozen sensitivity analysis. A design is covered only when "
            "all 120 torque angles fall inside its band. The nonconformity score is the maximum "
            "absolute error across the period. Wilson intervals treat independently simulated "
            "design rows as binomial units; they do not represent physical-machine variation.\n\n"
            "The geometry scale uses the fifth-nearest fit-design distance after range "
            "normalization, divided by the median fit leave-one-out fifth-neighbour distance and "
            "floored at 0.25. The support warning compares an evaluation distance with the 600 "
            "calibration distances and flags an upper-tail p-value below 0.05. Neither diagnostic "
            "uses evaluation torque labels."
        ),
        "# S3. Response surfaces and source-only selection\n\n"
        "All methods predict the same 21 real coordinates corresponding to 11 retained DFT "
        "components and reconstruct all 120 angles. Candidate settings for ridge, kernel "
        "ridge, and Extra Trees were selected by three-fold waveform-MAE cross-validation "
        "using only the 1,200 fit designs. The ARD Gaussian process optimized a shared "
        "20-dimensional RBF kernel by fit-only log marginal likelihood with length-scale "
        "bounds 0.03-10, numerical noise `1e-8`, and no restarts. It is source-style, not an "
        "exact reproduction of the source article's coordinate-wise GP/CMA-ES workflow.\n\n"
        + md_table(
            ["Model", "Selected parameters", "Selection basis"],
            (
                (
                    row["model"],
                    f"`{row['parameters']}`",
                    row["selection_basis"] or "three-fold fit-only waveform MAE",
                )
                for row in selected_models
            ),
        ),
        "# S4. Complete primary ARD Gaussian-process results\n\n"
        "The table reports both frozen nominal levels. Widths are half-widths in the units "
        "stored by the source archive. Accepted-set coverage is descriptive because support "
        "screening changes the evaluated population.\n\n"
        + md_table(
            [
                "Evaluation",
                "Band",
                "Nominal",
                "n",
                "Full-curve coverage",
                "95% Wilson interval",
                "Mean half-width",
                "Support rejected",
                "Accepted-set coverage",
            ],
            (
                (
                    distribution_names[row["distribution"]],
                    band_names[row["band"]],
                    pct(1 - float(row["alpha"]), 0),
                    f"{int(row['designs']):,}",
                    pct(row["curvewise_coverage"]),
                    f"{pct(row['coverage_wilson_lower'])}-{pct(row['coverage_wilson_upper'])}",
                    decimal(row["mean_half_width"]),
                    pct(row["support_rejection_rate"], 3),
                    pct(row["accepted_curvewise_coverage"]),
                )
                for row in primary
            ),
        ),
        "# S5. Geometry-distance conditioning\n\n"
        "Each uniform quintile contains 2,250 independent simulations and each Gaussian "
        "quintile 2,000. Geometry-distance quintiles are descriptive conditional audits, not "
        "additional calibration groups. The primary failure is visible in uniform quintile "
        "5: global coverage is 76.13% and scaled coverage 78.31%, despite near-nominal "
        "aggregate coverage.\n\n"
        + md_table(
            [
                "Evaluation",
                "Distance quintile",
                "n",
                "Mean max error",
                "Global coverage",
                "Scaled coverage",
                "Mean scaled half-width",
            ],
            (
                (
                    distribution_names[row["distribution"]],
                    row["distance_quintile"],
                    f"{int(row['designs']):,}",
                    decimal(row["mean_curve_max_error"]),
                    pct(row["global_coverage"]),
                    pct(row["geometry_scaled_coverage"]),
                    decimal(row["mean_geometry_scaled_half_width"]),
                )
                for row in distance_rows
            ),
        ),
        "# S6. Five-seed sensitivity\n\n"
        "No seed was selected from target performance. The table retains all 30 primary "
        "ARD rows (five seeds by three evaluations by two bands). Uniform global coverage "
        "ranges from 87.99% to 91.08%; scaled coverage ranges from 88.93% to 91.31%. The "
        "sparse-tail limitation remains because every split samples the same simulator and "
        "released design mechanism.\n\n"
        + md_table(
            ["Seed", "Evaluation", "Band", "Coverage", "Mean half-width"],
            (
                (
                    row["seed"],
                    distribution_names[row["distribution"]],
                    band_names[row["band"]],
                    pct(row["curvewise_coverage"]),
                    decimal(row["mean_half_width"]),
                )
                for row in seed_rows
            ),
        ),
        "# S7. Post-primary estimated weighted-conformal diagnostic\n\n"
        "This analysis was added after inspecting the primary aggregate results and uses "
        "the degree-two ridge surrogate. Each target table is split in half: one half fits a "
        "quadratic logistic domain classifier from geometry alone, and the other evaluates "
        "bands. The test weight is retained as point mass at positive infinity; an infinite "
        "quantile is not clipped. Coverage 'including vacuous' is set-theoretic and has no "
        "engineering utility when the finite-band rate is zero.\n\n"
        + md_table(
            [
                "Target",
                "Method",
                "Nominal",
                "n",
                "Finite-band rate",
                "Coverage incl. vacuous",
                "Finite-band coverage",
                "Mean finite half-width",
            ],
            (
                (
                    distribution_names[row["target_distribution"]],
                    method_names[row["method"]],
                    pct(1 - float(row["alpha"]), 0),
                    f"{int(row['designs']):,}",
                    pct(row["finite_band_rate"]),
                    pct(row["curvewise_coverage_including_vacuous"]),
                    pct(row["finite_band_curvewise_coverage"])
                    if row["finite_band_curvewise_coverage"]
                    else "not defined",
                    decimal(row["mean_finite_half_width"])
                    if row["mean_finite_half_width"]
                    else "not defined",
                )
                for row in weighted
            ),
        )
        + "\n\n"
        + md_table(
            [
                "Target",
                "Weight role",
                "Designs",
                "ESS",
                "Maximum normalized mass",
                "Held-out domain AUC",
            ],
            (
                (
                    distribution_names[row["target_distribution"]],
                    row["role"],
                    f"{int(row['designs']):,}",
                    f"{float(row['effective_sample_size']):.2f}",
                    pct(row["max_normalized_weight"], 3),
                    f"{float(row['heldout_domain_auc']):.4f}",
                )
                for row in density
            ),
        )
        + "\n\nFor the uniform half-split, domain AUC was 0.5059, calibration ESS "
        "516.50/600, and all 5,625 primary 90% weighted bands were finite. For the Gaussian "
        "half-split, domain AUC was 1.0000, calibration ESS 4.31/600, one source row carried "
        "39.70% of normalized mass, and 0/5,000 weighted bands were finite at either nominal "
        "level. This is retained as an overlap failure, not repaired.",
        "# S8. Timing and deterministic representative curves\n\n"
        "Timings are workstation-specific and exclude high-fidelity simulation. The ARD "
        "model's 41.0 s figure includes fitting and fit-only hyperparameter optimization; "
        "predicting 11,250 uniform designs required 0.317 s.\n\n"
        + md_table(
            ["Model", "Evaluation", "Fit/select seconds", "Predict seconds", "Designs"],
            (
                (
                    row["model"],
                    distribution_names[row["distribution"]],
                    f"{float(row['fit_and_select_seconds']):.3f}",
                    f"{float(row['prediction_seconds']):.3f}",
                    f"{int(row['designs']):,}",
                )
                for row in timings
            ),
        )
        + "\n\nRepresentative curves were selected mechanically by frozen role and median-error "
        "rules rather than by visual preference.\n\n"
        + md_table(
            [
                "Distribution",
                "Role",
                "Published row",
                "Max error",
                "Global width",
                "Scaled width",
                "Global covered",
                "Scaled covered",
            ],
            (
                (
                    row["distribution"],
                    row["selection_role"],
                    row["published_row_index"],
                    decimal(row["curve_max_error"]),
                    decimal(row["global_half_width"]),
                    decimal(row["geometry_scaled_half_width"]),
                    row["global_covered"],
                    row["geometry_scaled_covered"],
                )
                for row in representatives
            ),
        ),
        "# S9. Reproducibility boundary and evidence hashes\n\n"
        "The companion bundle includes the analysis modules, deterministic scripts, tests, "
        "frozen aggregate and per-design results, figures, manuscript sources, and SHA-256 "
        "manifest. Raw public data are omitted from the bundle to avoid redistribution and "
        "must be downloaded from the source DOI. The main evidence validator recomputes "
        "claims from 42,900 primary per-design rows and the disjoint weighted diagnostic.\n\n"
        "The evidential scope is one public two-dimensional PMSM simulator. The study does "
        "not quantify simulator model-form discrepancy, three-dimensional effects, "
        "manufacturing variation, another topology, another machine, or hardware "
        "uncertainty. Several ARD length scales reached the optimization upper bound. The "
        "weighted ratio is estimated, not known, and the diagnostic is explicitly "
        "post-primary.\n\n"
        + md_table(
            ["Frozen evidence file", "SHA-256"],
            (
                (
                    str(path.relative_to(ROOT)).replace("\\", "/"),
                    f"`{sha256(path)}`",
                )
                for path in [
                    ROOT / "papers" / "paper2_torque_uq" / "manuscript.md",
                    conformal_dir / "aggregate_summary.csv",
                    conformal_dir / "primary_per_design_scores.csv.gz",
                    seed_dir / "aggregate_summary.csv",
                    weighted_dir / "comparison_summary.csv",
                    weighted_dir / "weighted_per_design.csv.gz",
                    RESULTS / "paper2_evidence_validation" / "evidence.json",
                ]
            ),
        ),
    ]
    return "\n\n".join(sections).rstrip() + "\n"


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    content = build_content()
    if args.check:
        if not OUTPUT.is_file() or OUTPUT.read_text(encoding="utf-8") != content:
            raise SystemExit("supplementary material is stale; rebuild it")
        print(json.dumps({"status": "pass", "path": str(OUTPUT.relative_to(ROOT))}))
        return
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(content, encoding="utf-8", newline="\n")
    print(
        json.dumps(
            {
                "status": "built",
                "path": str(OUTPUT.relative_to(ROOT)),
                "sha256": sha256(OUTPUT),
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
