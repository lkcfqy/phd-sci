"""Create publication figures for the frozen external PMSM validation.

Chart contracts
---------------
1. Compare all methods on fault-block detection and held-out-health false alarms,
   retaining uncertainty and the two-part H1 decision.
2. Show how the proposed score and alarm rate drift across ordered 3 s blocks;
   block order is explicitly tied to increasing speed rather than treated as
   independent repetition.
3. Show the proposed eight-block detection rate for every fault-turn/load cell.

The script reads completed outputs only. It does not refit, retune, or alter any
data or model result.
"""

from __future__ import annotations

import argparse
from dataclasses import dataclass
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from matplotlib.colors import LinearSegmentedColormap
from matplotlib.figure import Figure
from matplotlib.lines import Line2D
from matplotlib.ticker import PercentFormatter

PROPOSED = "log_euclidean_entity_covariance"
H1_WILSON_UPPER_LIMIT = 0.12
H1_MAX_LOAD_FAR_LIMIT = 0.15
EXPECTED_BLOCKS = tuple(range(8))
EXPECTED_TURNS = tuple(range(1, 7))
EXPECTED_LOADS = tuple(range(0, 36, 5))

METHOD_LABELS = {
    "target_ledoit": "Target Ledoit–Wolf",
    "target_sample_covariance": "Target sample covariance",
    "source_covariance": "Source covariance transfer",
    "entity_balanced_covariance": "Arithmetic entity covariance",
    PROPOSED: "Proposed Log-Euclidean",
    "target_ocsvm_rbf": "Target OC-SVM (RBF)",
    "source_target_ocsvm_rbf": "Source + target OC-SVM",
    "target_isolation_forest": "Target Isolation Forest",
    "source_target_isolation_forest": "Source + target Isolation Forest",
    "target_min_cov_det": "Target MinCovDet",
    "source_target_min_cov_det": "Source + target MinCovDet",
}

INK = "#24323F"
MUTED = "#667784"
GRID = "#D8E0E7"
BLUE = "#2F6B9A"
BLUE_LIGHT = "#BFD4E5"
ORANGE = "#C87919"
GOLD = "#B58A2A"
NEUTRAL = "#AEB8C1"
NEUTRAL_DARK = "#56636E"


@dataclass(frozen=True)
class HeatmapData:
    turns: tuple[int, ...]
    loads: tuple[int, ...]
    phase_labels: tuple[str, ...]
    rates: np.ndarray


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--results-dir",
        type=Path,
        default=Path("results/external_pmsm_validation"),
    )
    parser.add_argument(
        "--speed-inventory",
        type=Path,
        default=Path("results/external_health_audit/block_inventory.csv"),
    )
    parser.add_argument("--output-dir", type=Path, default=Path("paper/figures"))
    return parser.parse_args()


def configure_style() -> None:
    plt.switch_backend("Agg")
    plt.rcParams.update(
        {
            "font.family": "DejaVu Sans",
            "font.size": 9,
            "axes.titlesize": 10,
            "axes.labelsize": 9,
            "axes.edgecolor": INK,
            "axes.labelcolor": INK,
            "axes.titlecolor": INK,
            "axes.spines.top": False,
            "axes.spines.right": False,
            "axes.linewidth": 0.8,
            "xtick.color": INK,
            "ytick.color": INK,
            "grid.color": GRID,
            "grid.linewidth": 0.7,
            "grid.alpha": 0.75,
            "legend.frameon": False,
            "figure.facecolor": "white",
            "axes.facecolor": "white",
            "savefig.facecolor": "white",
            "savefig.dpi": 300,
            "pdf.fonttype": 42,
            "ps.fonttype": 42,
        }
    )


def _require_columns(frame: pd.DataFrame, required: set[str], *, name: str) -> None:
    missing = sorted(required - set(frame.columns))
    if missing:
        raise ValueError(f"{name} is missing required columns: {missing}")


def _boolean(values: pd.Series, *, name: str) -> pd.Series:
    if pd.api.types.is_bool_dtype(values):
        return values.astype(bool)
    normalized = values.astype(str).str.strip().str.lower()
    mapped = normalized.map({"true": True, "false": False, "1": True, "0": False})
    if mapped.isna().any():
        raise ValueError(f"{name} contains values that are not boolean")
    return mapped.astype(bool)


def prepare_method_performance(aggregate: pd.DataFrame) -> pd.DataFrame:
    required = {
        "method",
        "faults_available",
        "fault_records",
        "fault_blocks",
        "fault_block_detection_rate",
        "record_bootstrap_detection_ci_lower",
        "record_bootstrap_detection_ci_upper",
        "health_test_records",
        "health_test_blocks",
        "healthy_block_false_alarm_rate",
        "descriptive_wilson_lower",
        "descriptive_wilson_upper",
        "max_heldout_load_false_alarm_rate",
        "h1_empirical_pass",
    }
    _require_columns(aggregate, required, name="external aggregate summary")
    result = aggregate.copy()
    if result["method"].duplicated().any():
        raise ValueError("external aggregate summary has duplicate methods")
    result["faults_available"] = _boolean(
        result["faults_available"], name="faults_available"
    )
    result["h1_empirical_pass"] = _boolean(
        result["h1_empirical_pass"], name="h1_empirical_pass"
    )
    if not result["faults_available"].all():
        raise ValueError("External fault results are not available for every method")
    unknown = sorted(set(result["method"]) - set(METHOD_LABELS))
    if unknown:
        raise ValueError(f"No display labels declared for methods: {unknown}")

    rates = [
        "fault_block_detection_rate",
        "record_bootstrap_detection_ci_lower",
        "record_bootstrap_detection_ci_upper",
        "healthy_block_false_alarm_rate",
        "descriptive_wilson_lower",
        "descriptive_wilson_upper",
        "max_heldout_load_false_alarm_rate",
    ]
    for column in rates:
        result[column] = pd.to_numeric(result[column], errors="raise")
        if not result[column].between(0, 1).all():
            raise ValueError(f"{column} must lie in [0, 1]")
    detection = result["fault_block_detection_rate"]
    if not (
        (result["record_bootstrap_detection_ci_lower"] <= detection)
        & (detection <= result["record_bootstrap_detection_ci_upper"])
    ).all():
        raise ValueError("Detection estimates are outside their bootstrap intervals")
    far = result["healthy_block_false_alarm_rate"]
    if not (
        (result["descriptive_wilson_lower"] <= far)
        & (far <= result["descriptive_wilson_upper"])
    ).all():
        raise ValueError("FAR estimates are outside their Wilson intervals")

    expected_h1 = (
        result["descriptive_wilson_upper"] <= H1_WILSON_UPPER_LIMIT + 1e-12
    ) & (
        result["max_heldout_load_false_alarm_rate"]
        <= H1_MAX_LOAD_FAR_LIMIT + 1e-12
    )
    if not expected_h1.equals(result["h1_empirical_pass"]):
        raise ValueError("Stored H1 decisions do not match the frozen two-part rule")

    result["method_label"] = result["method"].map(METHOD_LABELS)
    return result.sort_values(
        ["fault_block_detection_rate", "method_label"],
        ascending=[False, True],
        kind="stable",
    ).reset_index(drop=True)


def summarize_condition_drift(predictions: pd.DataFrame) -> pd.DataFrame:
    required = {
        "record_id",
        "block_id",
        "score",
        "is_healthy",
        "role",
        "alarm",
        "method",
    }
    _require_columns(predictions, required, name="proposed system-block predictions")
    data = predictions.copy()
    if set(data["method"]) != {PROPOSED}:
        raise ValueError("Condition-drift input must contain only the proposed method")
    data["is_healthy"] = _boolean(data["is_healthy"], name="is_healthy")
    data["alarm"] = _boolean(data["alarm"], name="alarm")
    fault = data.loc[~data["is_healthy"]].copy()
    health = data.loc[data["is_healthy"] & data["role"].eq("health_test")].copy()
    if fault.empty or health.empty:
        raise ValueError("Both fault and held-out-health blocks are required")
    fault["condition"] = "Fault"
    health["condition"] = "Held-out health"
    selected = pd.concat([fault, health], ignore_index=True)
    if (selected["score"] <= 0).any():
        raise ValueError("Scores must be positive for the logarithmic drift figure")

    blocks_by_condition = selected.groupby("condition", observed=True)["block_id"].apply(
        lambda values: tuple(sorted(values.unique()))
    )
    if any(blocks != EXPECTED_BLOCKS for blocks in blocks_by_condition):
        raise ValueError("Each condition must contain external analysis blocks 0..7")
    summary = (
        selected.groupby(["condition", "block_id"], observed=True, sort=True)
        .agg(
            records=("record_id", "nunique"),
            observations=("score", "size"),
            score_median=("score", "median"),
            score_q25=("score", lambda values: values.quantile(0.25)),
            score_q75=("score", lambda values: values.quantile(0.75)),
            alarm_rate=("alarm", "mean"),
        )
        .reset_index()
    )
    for condition, group in summary.groupby("condition", observed=True):
        if group["records"].nunique() != 1 or group["observations"].nunique() != 1:
            raise ValueError(f"{condition} has inconsistent record counts across blocks")
    return summary


def analysis_speed_by_block(inventory: pd.DataFrame) -> pd.Series:
    required = {
        "block_id",
        "speed_rpm_median",
        "inside_frozen_12_36s_segment",
    }
    _require_columns(inventory, required, name="external health block inventory")
    inside = _boolean(
        inventory["inside_frozen_12_36s_segment"],
        name="inside_frozen_12_36s_segment",
    )
    frozen = inventory.loc[inside].copy()
    speed = frozen.groupby("block_id", sort=True)["speed_rpm_median"].median()
    if len(speed) != len(EXPECTED_BLOCKS):
        raise ValueError("Speed inventory must contain eight frozen analysis blocks")
    speed.index = pd.Index(EXPECTED_BLOCKS, name="analysis_block_id")
    if not np.all(np.diff(speed.to_numpy()) > 0):
        raise ValueError("Median speed must increase monotonically across analysis blocks")
    return speed


def prepare_proposed_heatmap(records: pd.DataFrame) -> HeatmapData:
    required = {
        "record_id",
        "load_nm",
        "fault_turns",
        "fault_phase",
        "blocks",
        "alarms",
        "block_alarm_rate",
    }
    _require_columns(records, required, name="proposed fault-record summary")
    data = records.copy()
    if data.duplicated(["fault_turns", "load_nm"]).any():
        raise ValueError("Expected one proposed fault record per turns/load cell")
    if not data["blocks"].eq(8).all():
        raise ValueError("Every fault record must contain exactly eight macroblocks")
    expected_rates = data["alarms"] / data["blocks"]
    if not np.allclose(data["block_alarm_rate"], expected_rates, atol=1e-12):
        raise ValueError("Fault-record alarm rates do not match alarms / eight blocks")
    turns = tuple(sorted(data["fault_turns"].astype(int).unique()))
    loads = tuple(sorted(data["load_nm"].astype(int).unique()))
    if turns != EXPECTED_TURNS or loads != EXPECTED_LOADS:
        raise ValueError("Turns/load heatmap must be the complete 6 × 8 external grid")

    phase_labels: list[str] = []
    for turns_value in turns:
        phases = data.loc[data["fault_turns"].eq(turns_value), "fault_phase"].dropna().unique()
        if len(phases) != 1 or phases[0] not in {"u", "v"}:
            raise ValueError(f"Fault turn {turns_value} must map to one phase u or v")
        phase_labels.append(f"{turns_value} ({phases[0]})")
    rates = (
        data.pivot(index="fault_turns", columns="load_nm", values="block_alarm_rate")
        .loc[list(turns), list(loads)]
        .to_numpy(dtype=float)
    )
    if not np.isfinite(rates).all():
        raise ValueError("Turns/load heatmap contains a missing cell")
    return HeatmapData(turns, loads, tuple(phase_labels), rates)


def _method_color(method: str, *, leader: str) -> str:
    if method == leader:
        return GOLD
    if method == PROPOSED:
        return BLUE
    return NEUTRAL


def _save_pair(figure: Figure, output_dir: Path, stem: str) -> tuple[Path, Path]:
    output_dir.mkdir(parents=True, exist_ok=True)
    png = output_dir / f"{stem}.png"
    pdf = output_dir / f"{stem}.pdf"
    figure.savefig(png, dpi=300, bbox_inches="tight", pad_inches=0.06)
    figure.savefig(pdf, bbox_inches="tight", pad_inches=0.06)
    plt.close(figure)
    return png, pdf


def plot_method_performance(
    performance: pd.DataFrame, output_dir: Path
) -> tuple[Path, Path]:
    leader = str(performance.iloc[0]["method"])
    y = np.arange(len(performance), dtype=float)
    colors = [_method_color(method, leader=leader) for method in performance["method"]]
    detection = performance["fault_block_detection_rate"].to_numpy()
    detection_lower = performance["record_bootstrap_detection_ci_lower"].to_numpy()
    detection_upper = performance["record_bootstrap_detection_ci_upper"].to_numpy()

    figure, (axis_detection, axis_far) = plt.subplots(
        1,
        2,
        figsize=(11.2, 6.2),
        sharey=True,
        gridspec_kw={"width_ratios": [1.12, 1.0]},
    )
    figure.suptitle(
        "External validation performance by method",
        x=0.055,
        y=0.975,
        ha="left",
        fontsize=14,
        fontweight="bold",
        color=INK,
    )
    figure.text(
        0.055,
        0.932,
        "48 fault records (384 blocks); four held-out healthy loads (32 blocks). "
        "Intervals are descriptive at the recorded-data level.",
        ha="left",
        color=MUTED,
        fontsize=9,
    )

    bars = axis_detection.barh(
        y,
        detection,
        color=colors,
        edgecolor=INK,
        linewidth=0.55,
        height=0.62,
    )
    for bar, method in zip(bars, performance["method"], strict=True):
        if method == PROPOSED:
            bar.set_hatch("///")
    axis_detection.errorbar(
        detection,
        y,
        xerr=np.vstack([detection - detection_lower, detection_upper - detection]),
        fmt="none",
        ecolor=INK,
        elinewidth=0.9,
        capsize=2.5,
        capthick=0.9,
        zorder=4,
    )
    for index, value in enumerate(detection):
        suffix = "  highest" if index == 0 else ""
        axis_detection.text(
            min(detection_upper[index] + 0.018, 0.94),
            y[index],
            f"{value:.3f}{suffix}",
            va="center",
            fontsize=8,
            color=INK,
        )
    axis_detection.set_yticks(y, performance["method_label"])
    axis_detection.invert_yaxis()
    axis_detection.set_xlim(0, max(0.90, float(detection_upper.max()) + 0.13))
    axis_detection.set_xlabel("Fault-block detection rate (95% record-bootstrap CI)")
    axis_detection.set_title("(a) Fault detection", loc="left", fontweight="bold")
    axis_detection.grid(axis="x")
    axis_detection.xaxis.set_major_formatter(PercentFormatter(1.0, decimals=0))
    for label, method in zip(
        axis_detection.get_yticklabels(), performance["method"], strict=True
    ):
        if method == PROPOSED:
            label.set_color(BLUE)
            label.set_fontweight("bold")
        elif method == leader:
            label.set_color("#7B5A12")
            label.set_fontweight("bold")

    pooled_far = performance["healthy_block_false_alarm_rate"].to_numpy()
    wilson_lower = performance["descriptive_wilson_lower"].to_numpy()
    wilson_upper = performance["descriptive_wilson_upper"].to_numpy()
    max_load_far = performance["max_heldout_load_false_alarm_rate"].to_numpy()
    for index, method in enumerate(performance["method"]):
        color = _method_color(method, leader=leader)
        axis_far.errorbar(
            pooled_far[index],
            y[index],
            xerr=np.asarray(
                [
                    [pooled_far[index] - wilson_lower[index]],
                    [wilson_upper[index] - pooled_far[index]],
                ]
            ),
            fmt="o",
            markersize=5,
            markerfacecolor=color,
            markeredgecolor=INK,
            markeredgewidth=0.6,
            color=INK,
            ecolor=NEUTRAL_DARK,
            capsize=2.5,
            zorder=4,
        )
        axis_far.plot(
            max_load_far[index],
            y[index],
            marker="s",
            markersize=5,
            markerfacecolor="white",
            markeredgecolor=color if method in {leader, PROPOSED} else NEUTRAL_DARK,
            markeredgewidth=1.1,
            linestyle="none",
            zorder=5,
        )
    axis_far.axvline(
        H1_WILSON_UPPER_LIMIT,
        color=INK,
        linestyle="--",
        linewidth=0.9,
        zorder=1,
    )
    axis_far.axvline(
        H1_MAX_LOAD_FAR_LIMIT,
        color=MUTED,
        linestyle=":",
        linewidth=1.0,
        zorder=1,
    )
    x_max = max(0.28, float(wilson_upper.max()) + 0.045)
    axis_far.set_xlim(-0.008, x_max)
    for index, passed in enumerate(performance["h1_empirical_pass"]):
        axis_far.text(
            x_max - 0.004,
            y[index],
            "H1 PASS" if passed else "H1 fail",
            ha="right",
            va="center",
            fontsize=7.5,
            fontweight="bold" if passed else "normal",
            color=INK if passed else MUTED,
        )
    axis_far.tick_params(axis="y", left=False, labelleft=False)
    axis_far.set_xlabel("Held-out healthy-block false-alarm rate")
    axis_far.set_title("(b) Healthy false alarms and H1", loc="left", fontweight="bold")
    axis_far.grid(axis="x")
    axis_far.xaxis.set_major_formatter(PercentFormatter(1.0, decimals=0))
    legend_handles = [
        Line2D(
            [0],
            [0],
            marker="o",
            color=NEUTRAL_DARK,
            markerfacecolor=NEUTRAL,
            markersize=5,
            label="Pooled FAR (95% Wilson CI)",
        ),
        Line2D(
            [0],
            [0],
            marker="s",
            color="none",
            markeredgecolor=NEUTRAL_DARK,
            markerfacecolor="white",
            markersize=5,
            label="Maximum load-specific FAR",
        ),
        Line2D(
            [0],
            [0],
            color=INK,
            linestyle="--",
            linewidth=0.9,
            label="Wilson-upper limit: 12%",
        ),
        Line2D(
            [0],
            [0],
            color=MUTED,
            linestyle=":",
            linewidth=1.0,
            label="Max-load limit: 15%",
        ),
    ]
    axis_far.legend(
        handles=legend_handles,
        loc="upper center",
        bbox_to_anchor=(0.5, -0.12),
        ncol=2,
        columnspacing=1.3,
        handletextpad=0.6,
        fontsize=7.4,
    )
    figure.text(
        0.055,
        0.035,
        "H1 passes only when the pooled Wilson upper bound ≤ 12% and the maximum "
        "held-out-load FAR ≤ 15%. Gold marks the observed detection leader; hatched blue "
        "marks the proposed method.",
        ha="left",
        color=MUTED,
        fontsize=8,
    )
    figure.subplots_adjust(left=0.29, right=0.985, top=0.86, bottom=0.24, wspace=0.12)
    return _save_pair(figure, output_dir, "external_method_performance")


def plot_condition_drift(
    summary: pd.DataFrame,
    *,
    threshold: float,
    speed_by_block: pd.Series,
    output_dir: Path,
) -> tuple[Path, Path]:
    if threshold <= 0:
        raise ValueError("Proposed threshold must be positive")
    if tuple(speed_by_block.index) != EXPECTED_BLOCKS:
        raise ValueError("Speed series must use analysis block IDs 0..7")
    styles = {
        "Fault": {"color": ORANGE, "marker": "o", "linestyle": "-"},
        "Held-out health": {"color": BLUE, "marker": "s", "linestyle": "--"},
    }
    figure, axes = plt.subplots(
        2,
        1,
        figsize=(8.4, 6.5),
        sharex=True,
        gridspec_kw={"height_ratios": [1.55, 1.0]},
    )
    figure.suptitle(
        "Proposed score and alarm drift across analysis blocks",
        x=0.09,
        y=0.975,
        ha="left",
        fontsize=14,
        fontweight="bold",
        color=INK,
    )
    figure.text(
        0.09,
        0.936,
        "Log-Euclidean detector; fault n = 48 records/block, held-out health n = 4 "
        "records/block. Lines show medians; bands show interquartile ranges.",
        ha="left",
        color=MUTED,
        fontsize=9,
    )
    for condition in ("Fault", "Held-out health"):
        group = summary.loc[summary["condition"].eq(condition)].sort_values("block_id")
        blocks = group["block_id"].to_numpy(dtype=float)
        style = styles[condition]
        lower = group["score_q25"].to_numpy() / threshold
        upper = group["score_q75"].to_numpy() / threshold
        median = group["score_median"].to_numpy() / threshold
        axes[0].fill_between(
            blocks,
            lower,
            upper,
            color=style["color"],
            alpha=0.16,
            linewidth=0,
        )
        axes[0].plot(
            blocks,
            median,
            color=style["color"],
            marker=style["marker"],
            linestyle=style["linestyle"],
            linewidth=1.7,
            markersize=4.5,
            label=condition,
        )
        axes[1].plot(
            blocks,
            group["alarm_rate"],
            color=style["color"],
            marker=style["marker"],
            linestyle=style["linestyle"],
            linewidth=1.7,
            markersize=4.5,
            label=condition,
        )
    axes[0].axhline(1.0, color=INK, linestyle=":", linewidth=1.0, label="Alarm threshold")
    axes[0].set_yscale("log")
    axes[0].set_ylabel("Block score / conformal threshold (log scale)")
    axes[0].set_title("(a) Threshold-normalized anomaly score", loc="left", fontweight="bold")
    axes[0].grid(axis="y", which="major")
    axes[0].legend(ncol=3, fontsize=8, loc="upper left")

    speed_axis = axes[0].secondary_xaxis("top")
    speed_axis.set_xticks(
        list(EXPECTED_BLOCKS),
        [f"{value:,.0f}" for value in speed_by_block.to_numpy()],
    )
    speed_axis.set_xlabel("Approximate median speed (rpm)")
    speed_axis.spines["top"].set_visible(True)
    speed_axis.spines["top"].set_color(INK)

    axes[1].set_ylim(-0.035, 1.04)
    axes[1].set_yticks(np.linspace(0, 1, 5))
    axes[1].yaxis.set_major_formatter(PercentFormatter(1.0, decimals=0))
    axes[1].set_ylabel("Alarmed blocks")
    axes[1].set_xlabel("Analysis block ID (3 s each)")
    axes[1].set_xticks(EXPECTED_BLOCKS)
    axes[1].set_title("(b) Empirical block alarm rate", loc="left", fontweight="bold")
    axes[1].grid(axis="y")
    figure.text(
        0.09,
        0.028,
        f"Block is an ordered operating point, not an independent repeat: median speed rises "
        f"from ≈{speed_by_block.iloc[0]:,.0f} to {speed_by_block.iloc[-1]:,.0f} rpm. "
        "Score and alarm drift are therefore confounded with speed.",
        ha="left",
        color=MUTED,
        fontsize=8,
    )
    figure.subplots_adjust(left=0.12, right=0.98, top=0.84, bottom=0.14, hspace=0.28)
    return _save_pair(figure, output_dir, "external_condition_drift")


def _rate_label(value: float) -> str:
    percent = value * 100
    return f"{percent:.0f}%" if float(percent).is_integer() else f"{percent:.1f}%"


def plot_proposed_heatmap(
    heatmap: HeatmapData, output_dir: Path
) -> tuple[Path, Path]:
    color_map = LinearSegmentedColormap.from_list(
        "paper_blue",
        ["#F4F7FA", "#C7DAE9", "#73A2C6", "#2F6B9A", "#1D4668"],
    )
    figure, axis = plt.subplots(figsize=(8.4, 5.1))
    figure.suptitle(
        "Proposed fault-record detection across turn-phase conditions and load",
        x=0.08,
        y=0.965,
        ha="left",
        fontsize=13.5,
        fontweight="bold",
        color=INK,
    )
    figure.text(
        0.08,
        0.91,
        "Each cell is the fraction of eight ordered 3 s macroblocks alarmed within one "
        "dual-three-phase fault record.",
        ha="left",
        color=MUTED,
        fontsize=9,
    )
    image = axis.imshow(
        heatmap.rates,
        cmap=color_map,
        vmin=0,
        vmax=1,
        aspect="auto",
        interpolation="nearest",
    )
    axis.set_xticks(np.arange(len(heatmap.loads)), [str(load) for load in heatmap.loads])
    axis.set_yticks(np.arange(len(heatmap.turns)), heatmap.phase_labels)
    axis.set_xlabel("Load (N·m)")
    axis.set_ylabel("Faulted turns (phase)")
    axis.spines.top.set_visible(True)
    axis.spines.right.set_visible(True)
    axis.spines.bottom.set_visible(True)
    axis.spines.left.set_visible(True)
    axis.set_xticks(np.arange(-0.5, len(heatmap.loads), 1), minor=True)
    axis.set_yticks(np.arange(-0.5, len(heatmap.turns), 1), minor=True)
    axis.grid(which="minor", color="white", linewidth=1.4)
    axis.tick_params(which="minor", bottom=False, left=False)
    for row in range(heatmap.rates.shape[0]):
        for column in range(heatmap.rates.shape[1]):
            value = float(heatmap.rates[row, column])
            axis.text(
                column,
                row,
                _rate_label(value),
                ha="center",
                va="center",
                color="white" if value >= 0.55 else INK,
                fontsize=8,
                fontweight="bold" if value >= 0.5 else "normal",
            )
    colorbar = figure.colorbar(image, ax=axis, fraction=0.042, pad=0.025)
    colorbar.set_label("Detected macroblocks")
    colorbar.ax.yaxis.set_major_formatter(PercentFormatter(1.0, decimals=0))
    figure.text(
        0.08,
        0.035,
        "12.5% = 1/8 blocks. Phase is fixed by turn count (U: 1, 3, 5, 6; V: 2, 4), "
        "so turn and phase effects are not separable.\n"
        "Blocks within a record are ordered operating points, not independent repetitions.",
        ha="left",
        color=MUTED,
        fontsize=8,
    )
    figure.subplots_adjust(left=0.13, right=0.91, top=0.84, bottom=0.22)
    return _save_pair(figure, output_dir, "external_proposed_heatmap")


def main() -> None:
    args = parse_args()
    configure_style()
    aggregate = pd.read_csv(args.results_dir / "aggregate_summary.csv")
    performance = prepare_method_performance(aggregate)
    predictions = pd.read_csv(
        args.results_dir / PROPOSED / "system_block_predictions.csv"
    )
    drift = summarize_condition_drift(predictions)
    proposed_row = performance.loc[performance["method"].eq(PROPOSED)]
    if len(proposed_row) != 1:
        raise ValueError("External aggregate summary must contain the proposed method once")
    threshold = float(
        aggregate.loc[aggregate["method"].eq(PROPOSED), "threshold"].iloc[0]
    )
    speed = analysis_speed_by_block(pd.read_csv(args.speed_inventory))
    fault_records = pd.read_csv(
        args.results_dir / PROPOSED / "fault_record_summary.csv"
    )
    heatmap = prepare_proposed_heatmap(fault_records)

    outputs = [
        *plot_method_performance(performance, args.output_dir),
        *plot_condition_drift(
            drift,
            threshold=threshold,
            speed_by_block=speed,
            output_dir=args.output_dir,
        ),
        *plot_proposed_heatmap(heatmap, args.output_dir),
    ]
    print("Saved external-validation figures:")
    for output in outputs:
        print(f"  {output.resolve()}")


if __name__ == "__main__":
    main()
