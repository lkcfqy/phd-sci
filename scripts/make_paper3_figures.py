"""Create publication figures for the Paper 3 calibration-transport study."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from matplotlib.patches import Rectangle

from pmsm_sci.faults.statistics import wilson_interval

BLUE = "#2F6B9A"
RED = "#B6403A"
ORANGE = "#D97732"
PURPLE = "#7A5195"
GREEN = "#4C956C"
DARK = "#263238"
GREY = "#7A858B"
LIGHT_GREY = "#D9DEE1"

METHOD_LABELS = {
    "unconditioned_residual": "Unconditioned",
    "linear_residual": "Linear residual",
    "quadratic_residual": "Quadratic residual",
    "spline_residual": "Spline residual",
    "spline_local_scale": "Spline + local scale",
    "isolation_forest": "Isolation Forest",
    "min_cov_det": "MinCovDet",
}
DEVELOPMENT_LABEL_OFFSETS = {
    "unconditioned_residual": (5, 5),
    "linear_residual": (5, 5),
    "quadratic_residual": (5, 12),
    "spline_residual": (5, 2),
    "spline_local_scale": (5, 5),
    "isolation_forest": (5, 5),
    "min_cov_det": (5, 5),
}
CONFIRMATION_LABEL_OFFSETS = {
    "unconditioned_residual": (5, 6),
    "linear_residual": (5, 2),
    "quadratic_residual": (5, 6),
    "spline_residual": (5, 7),
    "spline_local_scale": (5, -19),
    "isolation_forest": (5, 4),
    "min_cov_det": (5, 5),
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--development-dir",
        type=Path,
        default=Path("results/paper3_development"),
    )
    parser.add_argument(
        "--confirmation-dir",
        type=Path,
        default=Path("results/paper3_pmsg_confirmation"),
    )
    parser.add_argument(
        "--session-dir",
        type=Path,
        default=Path("results/paper3_pmsg_session_anchor"),
    )
    parser.add_argument(
        "--topology-dir",
        type=Path,
        default=Path("results/paper3_pmsg_topology_crossfit"),
    )
    parser.add_argument(
        "--conditioned-dir",
        type=Path,
        default=Path("results/paper3_pmsg_conditioned_anchor"),
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("papers/paper3_calibration_transport/figures"),
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


def read_summary(path: Path) -> dict[str, object]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    summary = payload.get("summary", payload)
    if not isinstance(summary, dict):
        raise TypeError(f"{path} does not contain a summary object")
    return summary


def save_figure(figure: plt.Figure, output_dir: Path, stem: str) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    figure.savefig(output_dir / f"{stem}.png", dpi=300, bbox_inches="tight")
    figure.savefig(output_dir / f"{stem}.pdf", bbox_inches="tight")
    plt.close(figure)


def _gate_region(axis: plt.Axes) -> None:
    axis.add_patch(
        Rectangle(
            (0.0, 0.75),
            0.05,
            0.25,
            facecolor=GREEN,
            edgecolor="none",
            alpha=0.12,
            zorder=0,
        )
    )
    axis.axvline(0.05, color=GREEN, linestyle="--", linewidth=0.9)
    axis.axhline(0.75, color=GREEN, linestyle="--", linewidth=0.9)


def make_method_transport_figure(
    development: pd.DataFrame,
    confirmation: pd.DataFrame,
    output_dir: Path,
) -> None:
    require_columns(
        development,
        {
            "method",
            "primary_health_block_actionable_far",
            "primary_record_macro_actionable_detection",
            "selection_eligible",
        },
        label="development aggregate",
    )
    require_columns(
        confirmation,
        {
            "method",
            "pre_fault_session_far",
            "fault_record_detection",
            "pre_fault_session_far_wilson_lower",
            "pre_fault_session_far_wilson_upper",
            "fault_record_detection_wilson_lower",
            "fault_record_detection_wilson_upper",
        },
        label="confirmation aggregate",
    )
    if set(development["method"]) != set(confirmation["method"]):
        raise ValueError("development and confirmation method inventories differ")

    figure, axes = plt.subplots(1, 2, figsize=(9.6, 4.15), sharey=True)
    for method in development["method"]:
        row = development.loc[development["method"].eq(method)].iloc[0]
        selected = method == "spline_residual"
        axes[0].scatter(
            row["primary_health_block_actionable_far"],
            row["primary_record_macro_actionable_detection"],
            s=60 if selected else 34,
            color=BLUE if selected else (ORANGE if not row["selection_eligible"] else GREY),
            marker="*" if selected else "o",
            zorder=3,
        )
        axes[0].annotate(
            METHOD_LABELS[method],
            (
                row["primary_health_block_actionable_far"],
                row["primary_record_macro_actionable_detection"],
            ),
            xytext=DEVELOPMENT_LABEL_OFFSETS[method],
            textcoords="offset points",
            fontsize=7.2,
        )

    for method in confirmation["method"]:
        row = confirmation.loc[confirmation["method"].eq(method)].iloc[0]
        selected = method == "spline_residual"
        x = float(row["pre_fault_session_far"])
        y = float(row["fault_record_detection"])
        xerr = np.array(
            [[x - row["pre_fault_session_far_wilson_lower"]],
             [row["pre_fault_session_far_wilson_upper"] - x]]
        )
        yerr = np.array(
            [[y - row["fault_record_detection_wilson_lower"]],
             [row["fault_record_detection_wilson_upper"] - y]]
        )
        color = BLUE if selected else GREY
        axes[1].errorbar(
            x,
            y,
            xerr=xerr,
            yerr=yerr,
            fmt="*" if selected else "o",
            markersize=9 if selected else 5,
            color=color,
            ecolor=color,
            elinewidth=0.8,
            capsize=2,
            zorder=3,
        )
        axes[1].annotate(
            METHOD_LABELS[method],
            (x, y),
            xytext=CONFIRMATION_LABEL_OFFSETS[method],
            textcoords="offset points",
            fontsize=7.2,
        )

    titles = (
        "(a) Development PMSM: label-revealed selection",
        "(b) Independent PMSG: frozen confirmation",
    )
    xlabels = (
        "Healthy block FAR (interior loads)",
        "Pre-fault session FAR",
    )
    xlimits = ((-0.01, 0.24), (-0.02, 0.58))
    for axis, title, xlabel, xlim in zip(axes, titles, xlabels, xlimits, strict=True):
        _gate_region(axis)
        axis.set_title(title, pad=8)
        axis.set_xlabel(xlabel)
        axis.set_xlim(*xlim)
        axis.set_ylim(0.0, 1.01)
        axis.grid(color=LIGHT_GREY, linewidth=0.55, alpha=0.75)
        axis.spines[["top", "right"]].set_visible(False)
    axes[0].set_ylabel("Fault detection")
    figure.suptitle("Method ranking and alarm calibration did not transport", fontsize=12)
    figure.text(
        0.5,
        -0.025,
        "Green region: predeclared FAR <= 5% and detection >= 75%. Confirmation bars are descriptive 95% Wilson intervals over 216 sessions.",
        ha="center",
        fontsize=7.8,
        color=GREY,
    )
    save_figure(figure, output_dir, "paper3_method_transport")


def _variant_table(
    confirmation: pd.DataFrame,
    session_summary: dict[str, object],
    topology_summary: dict[str, object],
    conditioned_summary: dict[str, object],
) -> pd.DataFrame:
    selected = confirmation.loc[confirmation["method"].eq("spline_residual")]
    if len(selected) != 1:
        raise ValueError("expected one selected confirmation row")
    selected = selected.iloc[0]
    rows = [
        {
            "label": "Frozen spline\n(independent confirmation)",
            "status": "confirmatory",
            "false_alarms": int(selected["pre_fault_sessions_with_alarm"]),
            "detected": int(selected["fault_records_detected"]),
            "records": int(selected["fault_records"]),
        },
        {
            "label": "Session anchor\n(post-reveal)",
            "status": "post-reveal",
            "false_alarms": int(session_summary["pre_fault_false_alarms"]),
            "detected": int(session_summary["fault_records_detected"]),
            "records": int(session_summary["fault_records"]),
        },
        {
            "label": "Matched-session anchor\n(topology cross-fit)",
            "status": "post-reveal",
            "false_alarms": int(topology_summary["pre_false_alarms"]),
            "detected": int(topology_summary["fault_records_detected"]),
            "records": int(topology_summary["records"]),
        },
        {
            "label": "Conditioned anchor\n(topology cross-fit)",
            "status": "post-reveal",
            "false_alarms": int(conditioned_summary["pre_false_alarms"]),
            "detected": int(conditioned_summary["fault_records_detected"]),
            "records": int(conditioned_summary["records"]),
        },
    ]
    table = pd.DataFrame(rows)
    if not table["records"].eq(216).all():
        raise ValueError("all PMSG variants must contain 216 sessions")
    table["far"] = table["false_alarms"] / table["records"]
    table["detection"] = table["detected"] / table["records"]
    far_intervals = [
        wilson_interval(int(row.false_alarms), int(row.records))
        for row in table.itertuples(index=False)
    ]
    detection_intervals = [
        wilson_interval(int(row.detected), int(row.records))
        for row in table.itertuples(index=False)
    ]
    table[["far_lower", "far_upper"]] = far_intervals
    table[["detection_lower", "detection_upper"]] = detection_intervals
    return table


def make_repair_tradeoff_figure(variants: pd.DataFrame, output_dir: Path) -> None:
    colors = [RED, ORANGE, GREY, PURPLE]
    markers = ["X", "o", "s", "D"]
    figure, axis = plt.subplots(figsize=(6.9, 4.8))
    _gate_region(axis)
    for index, row in variants.iterrows():
        x = float(row["far"])
        y = float(row["detection"])
        axis.errorbar(
            x,
            y,
            xerr=np.array([[x - row["far_lower"]], [row["far_upper"] - x]]),
            yerr=np.array(
                [[y - row["detection_lower"]], [row["detection_upper"] - y]]
            ),
            fmt=markers[index],
            markersize=7.5,
            color=colors[index],
            ecolor=colors[index],
            capsize=3,
            elinewidth=1.1,
            label=row["label"].replace("\n", " "),
            zorder=3,
        )
        axis.annotate(
            f"{100 * x:.1f}% FAR\n{100 * y:.1f}% detection",
            (x, y),
            xytext=(7, 6 if index != 2 else -28),
            textcoords="offset points",
            fontsize=7.5,
        )
    axis.set_xlim(-0.01, 0.41)
    axis.set_ylim(0.48, 0.86)
    axis.set_xlabel("Pre-fault session false-alarm rate")
    axis.set_ylabel("Fault-record detection within 0.4 s")
    axis.set_title("Session-local repair reduced but did not eliminate calibration failure")
    axis.grid(color=LIGHT_GREY, linewidth=0.55, alpha=0.75)
    axis.spines[["top", "right"]].set_visible(False)
    axis.legend(loc="lower right", frameon=False, fontsize=7.5)
    figure.text(
        0.5,
        -0.015,
        "All error bars are descriptive 95% Wilson intervals. Only the red point is preregistered independent confirmation; the other analyses are post-reveal.",
        ha="center",
        fontsize=7.7,
        color=GREY,
    )
    save_figure(figure, output_dir, "paper3_session_repair")


def make_fold_stability_figure(
    topology_folds: pd.DataFrame,
    conditioned_folds: pd.DataFrame,
    output_dir: Path,
) -> None:
    required = {
        "outer_fold",
        "threshold",
        "pre_session_far",
        "fault_record_detection",
    }
    require_columns(topology_folds, required, label="matched-anchor fold summary")
    require_columns(conditioned_folds, required, label="conditioned-anchor fold summary")
    if len(topology_folds) != 3 or len(conditioned_folds) != 3:
        raise ValueError("each topology analysis must have three folds")

    figure, axes = plt.subplots(1, 2, figsize=(9.2, 3.9))
    x = np.arange(3)
    width = 0.34
    axes[0].bar(
        x - width / 2,
        topology_folds.sort_values("outer_fold")["threshold"],
        width,
        label="Matched anchor",
        color=GREY,
    )
    axes[0].bar(
        x + width / 2,
        conditioned_folds.sort_values("outer_fold")["threshold"],
        width,
        label="Conditioned anchor",
        color=PURPLE,
    )
    axes[0].set_xticks(x, ["Fold 1", "Fold 2", "Fold 3"])
    axes[0].set_ylabel("Healthy calibration threshold")
    axes[0].set_title("(a) Thresholds varied 2.5--2.9x across folds")
    axes[0].legend(frameon=False, fontsize=8)

    for frame, label, color, marker in (
        (topology_folds, "Matched anchor", GREY, "s"),
        (conditioned_folds, "Conditioned anchor", PURPLE, "D"),
    ):
        ordered = frame.sort_values("outer_fold")
        axes[1].plot(
            ordered["pre_session_far"],
            ordered["fault_record_detection"],
            marker=marker,
            color=color,
            linewidth=1.2,
            label=label,
        )
        for _index, row in ordered.iterrows():
            y_offset = 6 if label == "Matched anchor" else -17
            axes[1].annotate(
                f"F{int(row['outer_fold']) + 1}",
                (row["pre_session_far"], row["fault_record_detection"]),
                xytext=(5, y_offset),
                textcoords="offset points",
                fontsize=7.5,
            )
    _gate_region(axes[1])
    axes[1].set_xlim(-0.01, 0.18)
    axes[1].set_ylim(0.48, 0.94)
    axes[1].set_xlabel("Pre-fault session FAR")
    axes[1].set_ylabel("Fault-record detection")
    axes[1].set_title("(b) Fold-level operating points")
    axes[1].legend(frameon=False, fontsize=8)
    for axis in axes:
        axis.grid(axis="y", color=LIGHT_GREY, linewidth=0.55, alpha=0.75)
        axis.spines[["top", "right"]].set_visible(False)
    figure.suptitle("Topology-disjoint calibration was not stable", fontsize=12)
    figure.text(
        0.5,
        -0.015,
        "Each test fold contains eight unseen fault topologies and 72 operating-condition sessions; all results are post-reveal internal validation.",
        ha="center",
        fontsize=7.7,
        color=GREY,
    )
    save_figure(figure, output_dir, "paper3_topology_fold_stability")


def make_condition_heatmap(condition_summary: pd.DataFrame, output_dir: Path) -> None:
    required = {
        "facet",
        "level",
        "records",
        "record_detection",
        "pre_session_far",
    }
    require_columns(condition_summary, required, label="condition summary")
    selected = condition_summary.loc[condition_summary["facet"].eq("speed_by_torque")]
    if len(selected) != 9 or not selected["records"].eq(24).all():
        raise ValueError("expected nine speed-by-torque cells with 24 records each")
    parsed = selected["level"].str.extract(r"(?P<speed>\d+) / (?P<torque>\d+)")
    selected = selected.assign(
        speed=parsed["speed"].astype(int),
        torque=parsed["torque"].astype(int),
    )
    speeds = sorted(selected["speed"].unique())
    torques = sorted(selected["torque"].unique())
    detection = selected.pivot(index="speed", columns="torque", values="record_detection")
    far = selected.pivot(index="speed", columns="torque", values="pre_session_far")

    figure, axes = plt.subplots(1, 2, figsize=(7.7, 3.55), constrained_layout=True)
    for axis, matrix, title, cmap in (
        (axes[0], detection, "(a) Fault-record detection", "Blues"),
        (axes[1], far, "(b) Pre-fault session FAR", "Oranges"),
    ):
        values = matrix.loc[speeds, torques].to_numpy()
        image = axis.imshow(values, vmin=0.0, vmax=1.0, cmap=cmap, aspect="auto")
        for row in range(values.shape[0]):
            for column in range(values.shape[1]):
                color = "white" if values[row, column] >= 0.55 else DARK
                axis.text(
                    column,
                    row,
                    f"{100 * values[row, column]:.1f}%",
                    ha="center",
                    va="center",
                    color=color,
                    fontsize=8.5,
                )
        axis.set_xticks(np.arange(len(torques)), [str(value) for value in torques])
        axis.set_yticks(np.arange(len(speeds)), [str(value) for value in speeds])
        axis.set_xlabel("Torque setting code")
        axis.set_ylabel("Commanded speed (r/min)")
        axis.set_title(title)
        figure.colorbar(image, ax=axis, fraction=0.046, pad=0.04)
    figure.suptitle("The frozen detector confused operating condition with health", fontsize=12)
    figure.text(
        0.5,
        -0.035,
        "Independent PMSG confirmation; 24 sessions per cell. Torque values are dataset setting codes, not verified N m.",
        ha="center",
        fontsize=7.8,
        color=GREY,
    )
    save_figure(figure, output_dir, "paper3_condition_heatmap")


def make_first_alarm_figure(variants: pd.DataFrame, output_dir: Path) -> None:
    stage_counts = pd.DataFrame(
        {
            "0.2 s": [127, 149, 133, 136],
            "0.4 s": [29, 18, 20, 18],
            ">0.4 s / censored": [60, 49, 63, 62],
        },
        index=variants["label"].str.replace("\n", " ", regex=False),
    )
    if not stage_counts.sum(axis=1).eq(216).all():
        raise ValueError("first-alarm counts must sum to 216 sessions")
    figure, axis = plt.subplots(figsize=(8.4, 3.8))
    left = np.zeros(len(stage_counts))
    colors = [BLUE, ORANGE, LIGHT_GREY]
    for column, color in zip(stage_counts.columns, colors, strict=True):
        values = stage_counts[column].to_numpy()
        axis.barh(stage_counts.index, values, left=left, color=color, label=column)
        for index, value in enumerate(values):
            if value >= 15:
                axis.text(
                    left[index] + value / 2,
                    index,
                    str(value),
                    ha="center",
                    va="center",
                    fontsize=8,
                    color="white" if column != ">0.4 s / censored" else DARK,
                )
        left += values
    axis.set_xlim(0, 216)
    axis.set_xlabel("Fault sessions")
    axis.set_title("First actionable alarm after the commanded fault")
    axis.legend(loc="upper center", bbox_to_anchor=(0.5, 1.02), ncol=3, frameon=False)
    axis.grid(axis="x", color=LIGHT_GREY, linewidth=0.55, alpha=0.75)
    axis.spines[["top", "right", "left"]].set_visible(False)
    figure.text(
        0.5,
        -0.02,
        "Censoring at 0.4 s reflects the two frozen active-fault windows; it is not evidence of no later detection.",
        ha="center",
        fontsize=7.8,
        color=GREY,
    )
    save_figure(figure, output_dir, "paper3_first_alarm")


def main() -> None:
    args = parse_args()
    publication_style()
    development = pd.read_csv(args.development_dir / "aggregate_summary.csv")
    confirmation = pd.read_csv(args.confirmation_dir / "aggregate_summary.csv")
    session_summary = read_summary(args.session_dir / "summary.json")
    topology_summary = read_summary(args.topology_dir / "summary.json")
    conditioned_summary = read_summary(args.conditioned_dir / "summary.json")
    variants = _variant_table(
        confirmation,
        session_summary,
        topology_summary,
        conditioned_summary,
    )
    make_method_transport_figure(development, confirmation, args.output_dir)
    make_repair_tradeoff_figure(variants, args.output_dir)
    make_fold_stability_figure(
        pd.read_csv(args.topology_dir / "per_fold_summary.csv"),
        pd.read_csv(args.conditioned_dir / "per_fold_summary.csv"),
        args.output_dir,
    )
    make_condition_heatmap(
        pd.read_csv(args.confirmation_dir / "selected_condition_summary.csv"),
        args.output_dir,
    )
    make_first_alarm_figure(variants, args.output_dir)
    print(f"wrote Paper 3 figures to {args.output_dir.resolve()}")


if __name__ == "__main__":
    main()
