"""Create publication figures for the Paper 2 torque-curve benchmark."""

from __future__ import annotations

import argparse
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from matplotlib.lines import Line2D

BLUE = "#2F6B9A"
ORANGE = "#D97732"
DARK = "#263238"
GREY = "#7A858B"
LIGHT_GREY = "#D9DEE1"
MODEL_MARKERS = {
    "poly2_ridge": "o",
    "rbf_kernel_ridge": "s",
    "ard_gaussian_process": "D",
    "extra_trees": "^",
}
MODEL_LABELS = {
    "poly2_ridge": "Poly2 ridge",
    "rbf_kernel_ridge": "RBF kernel ridge",
    "ard_gaussian_process": "ARD Gaussian process",
    "extra_trees": "Extra Trees",
}
DISTRIBUTION_LABELS = {
    "internal_uniform": "Fixed internal test (n=200)",
    "uq_uniform": "Large uniform test (n=11,250)",
    "uq_gauss_shift": "Gaussian density shift (n=10,000)",
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--benchmark-dir",
        type=Path,
        default=Path("results/paper2_torque_conformal"),
    )
    parser.add_argument(
        "--seed-dir",
        type=Path,
        default=Path("results/paper2_torque_seed_sensitivity"),
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("papers/paper2_torque_uq/figures"),
    )
    return parser.parse_args()


def publication_style() -> None:
    plt.rcParams.update(
        {
            "font.family": "DejaVu Sans",
            "font.size": 9,
            "axes.titlesize": 10,
            "axes.labelsize": 9,
            "axes.edgecolor": DARK,
            "axes.linewidth": 0.8,
            "xtick.color": DARK,
            "ytick.color": DARK,
            "text.color": DARK,
            "axes.labelcolor": DARK,
            "axes.facecolor": "white",
            "figure.facecolor": "white",
            "savefig.facecolor": "white",
            "pdf.fonttype": 42,
            "ps.fonttype": 42,
        }
    )


def require_columns(frame: pd.DataFrame, columns: set[str], *, label: str) -> None:
    missing = sorted(columns - set(frame.columns))
    if missing:
        raise ValueError(f"{label} missing columns: {missing}")


def save_figure(figure: plt.Figure, output_dir: Path, stem: str) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    figure.savefig(output_dir / f"{stem}.png", dpi=300, bbox_inches="tight")
    figure.savefig(output_dir / f"{stem}.pdf", bbox_inches="tight")
    plt.close(figure)


def make_coverage_width_figure(summary: pd.DataFrame, output_dir: Path) -> None:
    required = {
        "seed",
        "model",
        "distribution",
        "band",
        "alpha",
        "curvewise_coverage",
        "coverage_wilson_lower",
        "coverage_wilson_upper",
        "mean_half_width",
    }
    require_columns(summary, required, label="aggregate summary")
    selected = summary.loc[
        np.isclose(summary["alpha"], 0.1) & summary["seed"].eq(20260821)
    ].copy()
    expected_rows = len(MODEL_MARKERS) * len(DISTRIBUTION_LABELS) * 2
    if len(selected) != expected_rows:
        raise ValueError(f"expected {expected_rows} primary 90% rows, got {len(selected)}")

    width_min = float(selected["mean_half_width"].min())
    width_max = float(selected["mean_half_width"].max())
    width_padding = 0.08 * (width_max - width_min)
    x_lower = max(0.0, width_min - width_padding)
    x_upper = width_max + width_padding

    figure, axes = plt.subplots(1, 3, figsize=(10.8, 3.55), sharex=True, sharey=True)
    for axis, distribution in zip(axes, DISTRIBUTION_LABELS, strict=True):
        subset = selected.loc[selected["distribution"].eq(distribution)]
        axis.axhline(0.9, color=DARK, linewidth=1.0, linestyle="--", zorder=1)
        axis.text(
            x_upper - 0.02 * (x_upper - x_lower),
            0.902,
            "90% nominal",
            ha="right",
            va="bottom",
            fontsize=7.5,
            color=DARK,
        )
        for model, marker in MODEL_MARKERS.items():
            model_rows = subset.loc[subset["model"].eq(model)].set_index("band")
            if set(model_rows.index) != {"global", "geometry_scaled"}:
                raise ValueError(f"missing band for {distribution}/{model}")
            axis.plot(
                model_rows.loc[["global", "geometry_scaled"], "mean_half_width"],
                model_rows.loc[["global", "geometry_scaled"], "curvewise_coverage"],
                color=GREY,
                linewidth=0.9,
                zorder=2,
            )
            for band, color, fill in (
                ("global", BLUE, color_for_fill(BLUE)),
                ("geometry_scaled", ORANGE, "white"),
            ):
                row = model_rows.loc[band]
                lower = row["curvewise_coverage"] - row["coverage_wilson_lower"]
                upper = row["coverage_wilson_upper"] - row["curvewise_coverage"]
                axis.errorbar(
                    row["mean_half_width"],
                    row["curvewise_coverage"],
                    yerr=np.array([[lower], [upper]]),
                    fmt=marker,
                    markersize=6.2,
                    markerfacecolor=fill,
                    markeredgecolor=color,
                    markeredgewidth=1.3,
                    ecolor=color,
                    elinewidth=1.0,
                    capsize=2.5,
                    zorder=3,
                )
        axis.set_title(DISTRIBUTION_LABELS[distribution], pad=7)
        axis.set_xlim(x_lower, x_upper)
        axis.set_ylim(0.79, 1.005)
        axis.grid(axis="y", color=LIGHT_GREY, linewidth=0.6, alpha=0.8)
        axis.spines[["top", "right"]].set_visible(False)
        axis.set_xlabel("Mean simultaneous-band half-width (torque units)")
    axes[0].set_ylabel("Full-curve coverage")
    figure.suptitle(
        "Full-curve coverage and band width across response surfaces",
        y=1.02,
        fontsize=12,
    )
    figure.text(
        0.5,
        -0.03,
        "Points cover all 120 angles jointly; vertical bars are 95% Wilson intervals over independent simulated designs.",
        ha="center",
        fontsize=8,
        color=GREY,
    )
    legend_items = [
        Line2D([0], [0], marker="o", color="none", markerfacecolor=BLUE,
               markeredgecolor=BLUE, label="Global conformal", markersize=6),
        Line2D([0], [0], marker="o", color="none", markerfacecolor="white",
               markeredgecolor=ORANGE, label="Geometry-scaled", markersize=6),
    ] + [
        Line2D([0], [0], marker=marker, color=GREY, linestyle="none",
               markerfacecolor="white", markeredgecolor=GREY,
               label=MODEL_LABELS[model], markersize=6)
        for model, marker in MODEL_MARKERS.items()
    ]
    figure.legend(
        handles=legend_items,
        loc="upper center",
        bbox_to_anchor=(0.5, 0.96),
        ncol=6,
        frameon=False,
        fontsize=8,
    )
    figure.tight_layout(rect=(0.0, 0.06, 1.0, 0.86))
    save_figure(figure, output_dir, "paper2_coverage_width")


def color_for_fill(color: str) -> str:
    """Keep a named hook for filled versus open band markers."""

    return color


def make_distance_figure(quintiles: pd.DataFrame, output_dir: Path) -> None:
    required = {
        "distribution",
        "distance_quintile",
        "designs",
        "mean_curve_max_error",
        "global_coverage",
        "geometry_scaled_coverage",
        "mean_geometry_scaled_half_width",
    }
    require_columns(quintiles, required, label="distance quintiles")
    distributions = ["uq_uniform", "uq_gauss_shift"]
    figure, axes = plt.subplots(2, 2, figsize=(8.0, 6.0), sharex="col", sharey="row")
    for column, distribution in enumerate(distributions):
        subset = quintiles.loc[quintiles["distribution"].eq(distribution)].sort_values(
            "distance_quintile"
        )
        if len(subset) != 5:
            raise ValueError(f"expected five quintiles for {distribution}")
        x = subset["distance_quintile"].to_numpy()

        top = axes[0, column]
        top.axhline(0.9, color=DARK, linewidth=1.0, linestyle="--", label="90% nominal")
        top.plot(
            x,
            subset["global_coverage"],
            color=BLUE,
            marker="o",
            markerfacecolor=BLUE,
            linewidth=1.5,
            label="Global conformal",
        )
        top.plot(
            x,
            subset["geometry_scaled_coverage"],
            color=ORANGE,
            marker="o",
            markerfacecolor="white",
            markeredgewidth=1.3,
            linewidth=1.5,
            label="Geometry-scaled",
        )
        # Keep the sparse-tail failures fully visible; the primary ARD-GP
        # reaches 0.761/0.783 coverage in the fifth uniform quintile.
        top.set_ylim(0.74, 1.005)
        top.set_title(DISTRIBUTION_LABELS[distribution])
        top.set_ylabel("Full-curve coverage" if column == 0 else "")
        top.grid(axis="y", color=LIGHT_GREY, linewidth=0.6)
        top.spines[["top", "right"]].set_visible(False)

        bottom = axes[1, column]
        bottom.plot(
            x,
            subset["mean_curve_max_error"],
            color=DARK,
            marker="s",
            linewidth=1.5,
            label="Mean curve max error",
        )
        bottom.plot(
            x,
            subset["mean_geometry_scaled_half_width"],
            color=ORANGE,
            marker="o",
            markerfacecolor="white",
            markeredgewidth=1.3,
            linewidth=1.5,
            label="Mean scaled half-width",
        )
        bottom.set_xlabel("Geometry-distance quintile (1=dense, 5=sparse)")
        bottom.set_ylabel("Torque units" if column == 0 else "")
        bottom.grid(axis="y", color=LIGHT_GREY, linewidth=0.6)
        bottom.spines[["top", "right"]].set_visible(False)
        bottom.set_xticks(x)

    axes[0, 0].legend(loc="lower left", frameon=False, fontsize=8)
    axes[1, 0].legend(loc="upper left", frameon=False, fontsize=8)
    figure.suptitle("Full-curve coverage by geometry-distance quintile", y=0.995, fontsize=12)
    figure.text(
        0.5,
        0.015,
        "Each uniform quintile contains 2,250 designs and each Gaussian quintile 2,000; all are simulations of one PMSM model.",
        ha="center",
        fontsize=8,
        color=GREY,
    )
    figure.tight_layout(rect=(0.0, 0.045, 1.0, 0.96))
    save_figure(figure, output_dir, "paper2_distance_conditioning")


def make_seed_figure(seed_summary: pd.DataFrame, output_dir: Path) -> None:
    required = {
        "seed",
        "distribution",
        "band",
        "alpha",
        "curvewise_coverage",
        "mean_half_width",
    }
    require_columns(seed_summary, required, label="seed summary")
    selected = seed_summary.loc[np.isclose(seed_summary["alpha"], 0.1)].copy()
    models = selected["model"].unique()
    if len(models) != 1:
        raise ValueError(f"seed figure requires one model, got {models.tolist()}")
    model_name = str(models[0])
    distributions = list(DISTRIBUTION_LABELS)
    figure, axes = plt.subplots(1, 2, figsize=(8.6, 3.8))
    positions = np.arange(len(distributions), dtype=float)
    offsets = {"global": -0.12, "geometry_scaled": 0.12}
    colors = {"global": BLUE, "geometry_scaled": ORANGE}
    labels = {"global": "Global conformal", "geometry_scaled": "Geometry-scaled"}

    for band in ("global", "geometry_scaled"):
        for index, distribution in enumerate(distributions):
            values = selected.loc[
                selected["band"].eq(band) & selected["distribution"].eq(distribution),
                "curvewise_coverage",
            ].to_numpy()
            if len(values) != 5:
                raise ValueError(f"expected five seeds for {distribution}/{band}")
            x = positions[index] + offsets[band]
            axes[0].plot([x, x], [values.min(), values.max()], color=colors[band], linewidth=2)
            axes[0].scatter(
                np.full(len(values), x),
                values,
                s=24,
                facecolors=colors[band] if band == "global" else "white",
                edgecolors=colors[band],
                linewidths=1.0,
                zorder=3,
            )
            axes[0].scatter([x], [values.mean()], marker="_", s=120, color=DARK, zorder=4)
    axes[0].axhline(0.9, color=DARK, linestyle="--", linewidth=1.0)
    axes[0].set_ylim(0.84, 1.005)
    axes[0].set_ylabel("Full-curve coverage")
    axes[0].set_title("Coverage across five fit/calibration seeds")
    axes[0].set_xticks(positions, ["Internal", "Uniform", "Gaussian"])
    axes[0].grid(axis="y", color=LIGHT_GREY, linewidth=0.6)
    axes[0].spines[["top", "right"]].set_visible(False)

    width_rows: list[dict[str, float | str]] = []
    for distribution in distributions:
        pivot = selected.loc[selected["distribution"].eq(distribution)].pivot(
            index="seed", columns="band", values="mean_half_width"
        )
        reduction = 100.0 * (pivot["global"] - pivot["geometry_scaled"]) / pivot["global"]
        for value in reduction:
            width_rows.append({"distribution": distribution, "reduction": float(value)})
    width_frame = pd.DataFrame(width_rows)
    for index, distribution in enumerate(distributions):
        values = width_frame.loc[
            width_frame["distribution"].eq(distribution), "reduction"
        ].to_numpy()
        axes[1].plot([index, index], [values.min(), values.max()], color=ORANGE, linewidth=2)
        axes[1].scatter(
            np.full(len(values), index),
            values,
            s=26,
            facecolors="white",
            edgecolors=ORANGE,
            linewidths=1.1,
            zorder=3,
        )
        axes[1].scatter([index], [values.mean()], marker="_", s=130, color=DARK, zorder=4)
    axes[1].axhline(0.0, color=DARK, linewidth=0.8)
    axes[1].set_ylabel("Mean half-width reduction (%)")
    axes[1].set_title("Width change from geometry scaling")
    axes[1].set_xticks(positions, ["Internal", "Uniform", "Gaussian"])
    axes[1].grid(axis="y", color=LIGHT_GREY, linewidth=0.6)
    axes[1].spines[["top", "right"]].set_visible(False)

    legend = [
        Line2D([0], [0], marker="o", color=BLUE, markerfacecolor=BLUE,
               label=labels["global"], markersize=5),
        Line2D([0], [0], marker="o", color=ORANGE, markerfacecolor="white",
               label=labels["geometry_scaled"], markersize=5),
    ]
    figure.legend(handles=legend, loc="upper center", bbox_to_anchor=(0.5, 0.96),
                  frameon=False, ncol=2, fontsize=8)
    figure.suptitle(
        f"Five-seed sensitivity of the {MODEL_LABELS[model_name]}",
        y=1.02,
        fontsize=12,
    )
    figure.text(
        0.5,
        0.01,
        "Dots are deterministic split seeds; horizontal ticks are seed means and vertical strokes show ranges.",
        ha="center",
        fontsize=8,
        color=GREY,
    )
    figure.tight_layout(rect=(0.0, 0.055, 1.0, 0.88))
    save_figure(figure, output_dir, "paper2_seed_sensitivity")


def main() -> None:
    args = parse_args()
    publication_style()
    summary = pd.read_csv(args.benchmark_dir / "aggregate_summary.csv")
    quintiles = pd.read_csv(args.benchmark_dir / "primary_distance_quintiles.csv")
    seed_summary = pd.read_csv(args.seed_dir / "aggregate_summary.csv")
    make_coverage_width_figure(summary, args.output_dir)
    make_distance_figure(quintiles, args.output_dir)
    make_seed_figure(seed_summary, args.output_dir)
    print(f"Wrote six figure files to {args.output_dir.resolve()}")


if __name__ == "__main__":
    main()
