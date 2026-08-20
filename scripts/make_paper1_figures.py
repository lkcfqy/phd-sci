"""Create publication-ready figures from the frozen Paper 1 pilot outputs."""

from __future__ import annotations

import argparse
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from matplotlib.patches import FancyArrowPatch, FancyBboxPatch, Rectangle

PROPOSED = "log_euclidean_entity_covariance"
METHOD_ORDER = (
    "target_ledoit",
    "target_sample_covariance",
    "source_covariance",
    "entity_balanced_covariance",
    PROPOSED,
)
METHOD_LABELS = {
    "target_ledoit": "Target LW",
    "target_sample_covariance": "Target sample",
    "source_covariance": "Source transfer",
    "entity_balanced_covariance": "Arithmetic entity",
    PROPOSED: "Log-Euclidean entity",
}
MOTOR_ORDER = ("1kW", "1.5kW", "3kW")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--results-dir",
        type=Path,
        default=Path("results/healthy_covariance_v0"),
    )
    parser.add_argument("--output-dir", type=Path, default=Path("paper/figures"))
    return parser.parse_args()


def configure_style() -> None:
    plt.rcParams.update(
        {
            "axes.spines.top": False,
            "axes.spines.right": False,
            "axes.grid": True,
            "axes.grid.axis": "y",
            "axes.axisbelow": True,
            "grid.alpha": 0.22,
            "font.size": 9,
            "figure.dpi": 160,
            "savefig.dpi": 300,
            "savefig.bbox": "tight",
        }
    )


def save_figure(figure: plt.Figure, output_dir: Path, stem: str) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    figure.savefig(
        output_dir / f"{stem}.pdf",
        metadata={"CreationDate": None, "ModDate": None},
    )
    figure.savefig(output_dir / f"{stem}.png")
    plt.close(figure)


def plot_method_performance(results_dir: Path, output_dir: Path) -> None:
    summary = pd.read_csv(results_dir / "summary.csv")
    summary = summary[summary["feature_arm"].eq("scale_free")]
    aggregate = pd.read_csv(results_dir / "aggregate_summary.csv")
    aggregate = aggregate[aggregate["feature_arm"].eq("scale_free")].set_index(
        "method"
    )

    figure, axes = plt.subplots(1, 2, figsize=(8.0, 3.1), constrained_layout=True)
    colors = plt.cm.Blues(np.linspace(0.35, 0.88, len(METHOD_ORDER)))
    x = np.arange(len(MOTOR_ORDER), dtype=float)
    width = 0.15
    for index, method in enumerate(METHOD_ORDER):
        values = (
            summary[summary["method"].eq(method)]
            .set_index("target_motor")
            .loc[list(MOTOR_ORDER), "detection_rate"]
            .to_numpy()
        )
        axes[0].bar(
            x + (index - 2) * width,
            values,
            width=width,
            label=METHOD_LABELS[method],
            color=colors[index],
        )
    axes[0].set_xticks(x, MOTOR_ORDER)
    axes[0].set_ylim(0.0, 1.015)
    axes[0].set_xlabel("Held-out target motor")
    axes[0].set_ylabel("Fault-block detection rate")
    axes[0].set_title("(a) Cross-machine detection")

    far = aggregate.loc[list(METHOD_ORDER), "pooled_false_alarm_rate"].to_numpy()
    lower = aggregate.loc[list(METHOD_ORDER), "pooled_far_wilson_lower"].to_numpy()
    upper = aggregate.loc[list(METHOD_ORDER), "pooled_far_wilson_upper"].to_numpy()
    y = np.arange(len(METHOD_ORDER))
    axes[1].errorbar(
        far,
        y,
        xerr=np.vstack([far - lower, upper - far]),
        fmt="o",
        color="#24548f",
        ecolor="#6f88a5",
        capsize=3,
    )
    axes[1].axvline(0.05, color="#555555", linestyle="--", linewidth=1, label="Nominal 5%")
    axes[1].axvline(0.12, color="#9a4b42", linestyle=":", linewidth=1, label="H1 upper limit")
    axes[1].set_yticks(y, [METHOD_LABELS[method] for method in METHOD_ORDER])
    axes[1].invert_yaxis()
    axes[1].set_xlim(-0.005, 0.135)
    axes[1].set_xlabel("Pooled healthy-block FAR (95% Wilson CI)")
    axes[1].set_title("(b) Empirical false-alarm risk")
    axes[1].legend(frameon=False, fontsize=8, loc="lower right")

    handles, labels = axes[0].get_legend_handles_labels()
    figure.legend(
        handles,
        labels,
        loc="outside lower center",
        ncol=3,
        frameon=False,
        fontsize=8,
    )
    save_figure(figure, output_dir, "method_performance")


def plot_paired_differences(results_dir: Path, output_dir: Path) -> None:
    comparisons = pd.read_csv(results_dir / "paired_record_bootstrap.csv")
    comparisons = comparisons.set_index("comparator").loc[
        list(reversed(METHOD_ORDER[:-1]))
    ]
    estimates = comparisons["mean_detection_difference"].to_numpy()
    lower = comparisons["bootstrap_ci_lower"].to_numpy()
    upper = comparisons["bootstrap_ci_upper"].to_numpy()
    y = np.arange(len(comparisons))

    figure, axis = plt.subplots(figsize=(6.2, 2.5), constrained_layout=True)
    significant = lower > 0
    colors = np.where(significant, "#24548f", "#7c7c7c")
    for index in range(len(comparisons)):
        axis.errorbar(
            estimates[index],
            y[index],
            xerr=np.asarray(
                [[estimates[index] - lower[index]], [upper[index] - estimates[index]]]
            ),
            fmt="o",
            color=colors[index],
            ecolor=colors[index],
            capsize=3,
        )
    axis.axvline(0, color="#555555", linewidth=1)
    axis.set_yticks(
        y,
        [METHOD_LABELS[method] for method in comparisons.index],
    )
    axis.set_xlabel("Detection-rate difference: Log-Euclidean entity minus comparator")
    save_figure(figure, output_dir, "paired_detection_differences")


def plot_severity_detection(results_dir: Path, output_dir: Path) -> None:
    figure, axes = plt.subplots(
        2,
        3,
        figsize=(8.2, 4.8),
        constrained_layout=True,
        sharey=True,
    )
    family_order = ("interturn", "intercoil")
    family_labels = {"interturn": "Inter-turn", "intercoil": "Inter-coil"}
    for row, family in enumerate(family_order):
        for column, motor in enumerate(MOTOR_ORDER):
            path = (
                results_dir
                / f"target_{motor}"
                / "scale_free"
                / PROPOSED
                / "severity_detection.csv"
            )
            severity = pd.read_csv(path)
            severity = severity[severity["fault_family"].eq(family)].sort_values(
                "severity_percent"
            )
            axis = axes[row, column]
            axis.plot(
                severity["severity_percent"],
                severity["detection_rate"],
                marker="o",
                color="#24548f",
                linewidth=1.5,
            )
            axis.set_ylim(-0.03, 1.03)
            axis.set_title(f"{family_labels[family]} — {motor}")
            if row == 1:
                axis.set_xlabel("Nominal severity (%)")
            if column == 0:
                axis.set_ylabel("Fault-block detection rate")
    save_figure(figure, output_dir, "severity_detection")


def plot_budget_sensitivity(output_dir: Path) -> None:
    budget_dir = Path("results/calibration_budget_sensitivity")
    aggregate = pd.read_csv(budget_dir / "aggregate_summary.csv")
    feasibility = pd.read_csv(budget_dir / "conformal_calibration_feasibility.csv")
    feasibility = feasibility[feasibility["calibration_seconds"].isin([3, 6, 12, 24])]

    figure, axes = plt.subplots(1, 2, figsize=(7.5, 2.9), constrained_layout=True)
    style = {
        "fixed_horizon": ("Fixed evaluation horizon", "o", "#24548f"),
        "sequential": ("Sequential deployment", "s", "#b05a48"),
    }
    for design, group in aggregate.groupby("design", sort=True):
        group = group.sort_values("adaptation_seconds")
        label, marker, color = style[design]
        axes[0].plot(
            group["adaptation_seconds"],
            group["mean_detection_rate"],
            marker=marker,
            color=color,
            label=label,
        )
    axes[0].axvline(12, color="#555555", linestyle=":", linewidth=1)
    axes[0].text(12.4, 0.928, "frozen primary", fontsize=8, rotation=90, va="bottom")
    axes[0].set_ylim(0.92, 0.98)
    axes[0].set_xticks([3, 6, 12, 24])
    axes[0].set_xlabel("Target healthy adaptation (s)")
    axes[0].set_ylabel("Mean fault-block detection rate")
    axes[0].set_title("(a) Covariance adaptation budget")
    axes[0].legend(frameon=False, fontsize=8)

    axes[1].plot(
        feasibility["calibration_seconds"],
        feasibility["minimum_attainable_p_value"],
        marker="o",
        color="#24548f",
    )
    axes[1].axhline(0.05, color="#9a4b42", linestyle="--", linewidth=1)
    axes[1].text(3, 0.062, "alpha = 0.05", color="#9a4b42", fontsize=8)
    axes[1].set_xticks([3, 6, 12, 24])
    axes[1].set_xlabel("If used as conformal calibration (s)")
    axes[1].set_ylabel("Minimum attainable p-value")
    axes[1].set_title("(b) Why adaptation is not calibration")
    save_figure(figure, output_dir, "adaptation_budget")


def _flow_box(axis, x: float, y: float, width: float, height: float, text: str, color: str):
    patch = FancyBboxPatch(
        (x, y),
        width,
        height,
        boxstyle="round,pad=0.012,rounding_size=0.015",
        facecolor=color,
        edgecolor="#4d4d4d",
        linewidth=0.8,
    )
    axis.add_patch(patch)
    axis.text(x + width / 2, y + height / 2, text, ha="center", va="center", fontsize=8)


def plot_protocol_overview(output_dir: Path) -> None:
    figure, axis = plt.subplots(figsize=(8.3, 4.2), constrained_layout=True)
    axis.set_xlim(0, 1)
    axis.set_ylim(0, 1)
    axis.axis("off")

    axis.text(0.01, 0.96, "(a) Three-fold motor-level holdout", fontsize=10, weight="bold")
    fold_labels = (
        "Sources: 1.5 + 3 kW   →   Target: 1 kW",
        "Sources: 1 + 3 kW     →   Target: 1.5 kW",
        "Sources: 1 + 1.5 kW   →   Target: 3 kW",
    )
    for index, label in enumerate(fold_labels):
        x = 0.015 + index * 0.33
        _flow_box(axis, x, 0.82, 0.30, 0.085, label, "#e7f0f8")
    axis.text(
        0.5,
        0.775,
        "No target-fault label enters fitting, selection, adaptation, or calibration",
        ha="center",
        va="center",
        fontsize=8,
        color="#8b3f35",
    )

    axis.text(0.01, 0.70, "(b) Ordered target-health deployment record", fontsize=10, weight="bold")
    regions = (
        (0, 4, "Adapt\n12 s", "#8fc1e3"),
        (4, 1, "G", "#bcbcbc"),
        (5, 20, "Calibration 60 s", "#95c99f"),
        (25, 1, "G", "#bcbcbc"),
        (26, 14, "Later-time healthy test 42 s", "#e5b77a"),
    )
    timeline_x, timeline_y, timeline_w, timeline_h = 0.02, 0.57, 0.96, 0.075
    for start, length, label, color in regions:
        x = timeline_x + timeline_w * start / 40
        width = timeline_w * length / 40
        axis.add_patch(
            Rectangle(
                (x, timeline_y),
                width,
                timeline_h,
                facecolor=color,
                edgecolor="#4d4d4d",
                linewidth=0.7,
            )
        )
        axis.text(x + width / 2, timeline_y + timeline_h / 2, label, ha="center", va="center", fontsize=7)
    axis.text(timeline_x, 0.545, "block 0", fontsize=7, ha="left")
    axis.text(timeline_x + timeline_w, 0.545, "block 39", fontsize=7, ha="right")

    axis.text(0.01, 0.46, "(c) Healthy-only motor-balanced scoring and alarm calibration", fontsize=10, weight="bold")
    labels = (
        "Scale-free\ncurrent features",
        "Per-motor robust\nmedian / MAD",
        "One healthy\ncovariance / motor",
        "Equal-motor\nLog-Euclidean mean",
        "Target-centered\nMahalanobis score",
        "3-s block max +\nhealthy p-value",
    )
    colors = ("#e7f0f8", "#e7f0f8", "#dcebdc", "#dcebdc", "#f2e4cd", "#f2e4cd")
    width, height, y = 0.135, 0.15, 0.20
    xs = np.linspace(0.015, 0.85, len(labels))
    for index, (x, label, color) in enumerate(zip(xs, labels, colors, strict=True)):
        _flow_box(axis, float(x), y, width, height, label, color)
        if index < len(labels) - 1:
            axis.add_patch(
                FancyArrowPatch(
                    (x + width + 0.004, y + height / 2),
                    (xs[index + 1] - 0.004, y + height / 2),
                    arrowstyle="-|>",
                    mutation_scale=9,
                    linewidth=0.8,
                    color="#4d4d4d",
                )
            )
    axis.text(
        0.5,
        0.10,
        "20 target healthy calibration blocks  →  alarm when upper-tail p ≤ 0.05",
        ha="center",
        va="center",
        fontsize=8,
    )
    save_figure(figure, output_dir, "protocol_overview")


def plot_block_sensitivity(output_dir: Path) -> None:
    sensitivity = pd.read_csv("results/block_sensitivity/aggregate_summary.csv")
    figure, axes = plt.subplots(1, 2, figsize=(7.4, 2.9), constrained_layout=True)
    styles = {
        "max": ("Block maximum", "o", "#24548f"),
        "q90": ("Block 90th percentile", "s", "#b05a48"),
    }
    for aggregation, group in sensitivity.groupby("aggregation", sort=True):
        group = group.sort_values("block_seconds")
        label, marker, color = styles[aggregation]
        axes[0].plot(
            group["block_seconds"],
            group["mean_motor_block_detection_rate"],
            marker=marker,
            color=color,
            label=label,
        )
        axes[1].errorbar(
            group["block_seconds"],
            group["pooled_false_alarm_rate"],
            yerr=np.vstack(
                [
                    np.maximum(
                        group["pooled_false_alarm_rate"]
                        - group["pooled_far_wilson_lower_descriptive"],
                        0,
                    ),
                    np.maximum(
                        group["pooled_far_wilson_upper_descriptive"]
                        - group["pooled_false_alarm_rate"],
                        0,
                    ),
                ]
            ),
            marker=marker,
            color=color,
            capsize=3,
            label=label,
        )
    for axis in axes:
        axis.axvline(3, color="#555555", linestyle=":", linewidth=1)
        axis.set_xticks([1, 2, 3])
        axis.set_xlabel("Macroblock duration (s)")
    axes[0].set_ylim(0.92, 0.98)
    axes[0].set_ylabel("Mean fault-block detection rate")
    axes[0].set_title("(a) Detection sensitivity")
    axes[0].legend(frameon=False, fontsize=8)
    axes[1].axhline(0.05, color="#555555", linestyle="--", linewidth=1)
    axes[1].axhline(0.12, color="#9a4b42", linestyle="--", linewidth=1)
    axes[1].set_ylim(-0.005, 0.13)
    axes[1].set_ylabel("Healthy-block FAR (descriptive 95% Wilson CI)")
    axes[1].set_title("(b) False-alarm sensitivity")
    save_figure(figure, output_dir, "block_sensitivity")


def plot_oneclass_comparisons(output_dir: Path) -> None:
    comparisons = pd.read_csv("results/oneclass_baselines/comparison_to_proposed.csv")
    labels = {
        "target_ocsvm_rbf": "Target OCSVM (0 FA)",
        "source_target_ocsvm_rbf": "Balanced OCSVM (0 FA)",
        "target_isolation_forest": "Target IsolationForest (1 FA)",
        "source_target_isolation_forest": "Balanced IsolationForest (0 FA)",
        "target_min_cov_det": "Target MinCovDet (1 FA)",
        "source_target_min_cov_det": "Balanced MinCovDet (1 FA)",
    }
    order = [
        "target_ocsvm_rbf",
        "source_target_ocsvm_rbf",
        "target_isolation_forest",
        "source_target_isolation_forest",
        "target_min_cov_det",
        "source_target_min_cov_det",
    ]
    comparisons = comparisons.set_index("baseline").loc[order].reset_index()
    estimates = comparisons["proposed_minus_baseline_detection"].to_numpy()
    lower = comparisons["paired_record_bootstrap_ci_lower"].to_numpy()
    upper = comparisons["paired_record_bootstrap_ci_upper"].to_numpy()
    y = np.arange(len(comparisons))

    figure, axis = plt.subplots(figsize=(6.8, 3.0), constrained_layout=True)
    for index in range(len(comparisons)):
        supported = lower[index] > 0
        color = "#24548f" if supported else "#7c7c7c"
        axis.errorbar(
            estimates[index],
            y[index],
            xerr=np.asarray(
                [[estimates[index] - lower[index]], [upper[index] - estimates[index]]]
            ),
            fmt="o",
            color=color,
            ecolor=color,
            capsize=3,
        )
    axis.axvline(0, color="#555555", linewidth=1)
    axis.set_yticks(y, [labels[item] for item in order])
    axis.invert_yaxis()
    axis.set_xlabel("Detection-rate difference: proposed minus one-class baseline")
    save_figure(figure, output_dir, "oneclass_detection_differences")


def main() -> None:
    args = parse_args()
    configure_style()
    plot_method_performance(args.results_dir, args.output_dir)
    plot_paired_differences(args.results_dir, args.output_dir)
    plot_severity_detection(args.results_dir, args.output_dir)
    plot_budget_sensitivity(args.output_dir)
    plot_protocol_overview(args.output_dir)
    plot_block_sensitivity(args.output_dir)
    plot_oneclass_comparisons(args.output_dir)
    print(f"Saved Paper 1 figures to {args.output_dir.resolve()}")


if __name__ == "__main__":
    main()
