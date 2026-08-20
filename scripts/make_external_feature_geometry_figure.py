"""Plot post-reveal external feature discrimination versus frozen-score geometry.

Chart contract
--------------
Question: Do the features that separate health from fault also dominate the frozen
Log-Euclidean Mahalanobis score?

Takeaway: fundamental frequency contributes strongly despite chance-level class
separation, whereas the third-harmonic ratio separates the recorded conditions well
but contributes little to the frozen score.

The static two-panel figure reads completed feature-drift outputs only. It does not
refit a model, recompute a threshold, or use fault labels to alter the detector.
"""

from __future__ import annotations

import argparse
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from matplotlib.figure import Figure
from matplotlib.lines import Line2D
from matplotlib.ticker import PercentFormatter

EXPECTED_FEATURE_COUNT = 27
FOCAL_HARMONIC = "harmonic_3_ratio_max"
FOCAL_FREQUENCY = "fundamental_hz"
FEATURE_ORDER = (
    FOCAL_HARMONIC,
    "rms_ratio_a",
    "thd_2_to_5_mean",
    "sequence_unbalance",
    "phase_rms_cv",
    "zero_sequence_ratio",
    "clarke_radius_cv",
    "spectral_entropy",
    FOCAL_FREQUENCY,
)
FEATURE_LABELS = {
    FOCAL_HARMONIC: "3rd-harmonic ratio (max)",
    "rms_ratio_a": "Phase-A RMS ratio",
    "thd_2_to_5_mean": "THD, harmonics 2–5",
    "sequence_unbalance": "Sequence unbalance",
    "phase_rms_cv": "Phase RMS CV",
    "zero_sequence_ratio": "Zero-sequence ratio",
    "clarke_radius_cv": "Clarke-radius CV",
    "spectral_entropy": "Spectral entropy",
    FOCAL_FREQUENCY: "Fundamental frequency",
}

INK = "#24323F"
MUTED = "#667784"
GRID = "#D8E0E7"
BLUE = "#2F6B9A"
BLUE_LIGHT = "#C6DAE9"
ORANGE = "#C87919"
ORANGE_LIGHT = "#E9C99F"
NEUTRAL = "#AEB8C1"
NEUTRAL_DARK = "#56636E"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--summary",
        type=Path,
        default=Path("results/external_feature_drift/feature_diagnostic_summary.csv"),
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


def _require_columns(frame: pd.DataFrame, required: set[str]) -> None:
    missing = sorted(required - set(frame.columns))
    if missing:
        raise ValueError(f"Feature diagnostic summary is missing columns: {missing}")


def _boolean(values: pd.Series, *, name: str) -> pd.Series:
    if pd.api.types.is_bool_dtype(values):
        return values.astype(bool)
    normalized = values.astype(str).str.strip().str.lower()
    mapped = normalized.map({"true": True, "false": False, "1": True, "0": False})
    if mapped.isna().any():
        raise ValueError(f"{name} contains values that are not boolean")
    return mapped.astype(bool)


def prepare_feature_geometry(summary: pd.DataFrame) -> pd.DataFrame:
    """Validate frozen diagnostic grain and select the prespecified feature set."""

    required = {
        "scope",
        "feature",
        "block_id",
        "independent_motors",
        "healthy_units",
        "fault_units",
        "matched_fault_health_pairs",
        "raw_direction_free_auc",
        "matched_raw_dz",
        "auroc_inferential_claimed",
        "fault_absolute_contribution_share",
        "healthy_test_absolute_contribution_share",
    }
    _require_columns(summary, required)
    data = summary.copy()
    if len(data) != EXPECTED_FEATURE_COUNT or data["feature"].duplicated().any():
        raise ValueError("Expected one all-block diagnostic row for each of 27 features")
    if set(data["scope"]) != {"heldout_health_test_loads"} or not data[
        "block_id"
    ].eq(-1).all():
        raise ValueError("Figure requires the held-out-load, all-block diagnostic scope")
    if not data["independent_motors"].eq(1).all():
        raise ValueError("External feature diagnosis must remain single-motor conditional")
    if data[["healthy_units", "fault_units", "matched_fault_health_pairs"]].nunique().ne(
        1
    ).any():
        raise ValueError("Diagnostic unit counts must be consistent across features")
    claimed = _boolean(
        data["auroc_inferential_claimed"], name="auroc_inferential_claimed"
    )
    if claimed.any():
        raise ValueError("This post-reveal figure must not present inferential AUROC claims")

    numeric = [
        "raw_direction_free_auc",
        "matched_raw_dz",
        "fault_absolute_contribution_share",
        "healthy_test_absolute_contribution_share",
    ]
    for column in numeric:
        data[column] = pd.to_numeric(data[column], errors="raise")
    if not np.isfinite(data[numeric].to_numpy(dtype=float)).all():
        raise ValueError("Feature diagnostic metrics must be finite")
    if not data["raw_direction_free_auc"].between(0.5, 1.0).all():
        raise ValueError("Direction-free AUROC must lie in [0.5, 1.0]")
    for column in (
        "fault_absolute_contribution_share",
        "healthy_test_absolute_contribution_share",
    ):
        if not data[column].between(0, 1).all():
            raise ValueError(f"{column} must lie in [0, 1]")
        if not np.isclose(data[column].sum(), 1.0, rtol=0, atol=1e-9):
            raise ValueError(f"{column} must sum to one across all 27 features")

    missing_features = sorted(set(FEATURE_ORDER) - set(data["feature"]))
    if missing_features:
        raise ValueError(f"Prespecified figure features are missing: {missing_features}")
    selected = data.set_index("feature").loc[list(FEATURE_ORDER)].reset_index()
    selected["feature_label"] = selected["feature"].map(FEATURE_LABELS)
    selected["absolute_matched_dz"] = selected["matched_raw_dz"].abs()

    harmonic = selected.loc[selected["feature"].eq(FOCAL_HARMONIC)].iloc[0]
    frequency = selected.loc[selected["feature"].eq(FOCAL_FREQUENCY)].iloc[0]
    if not (
        harmonic["raw_direction_free_auc"] > frequency["raw_direction_free_auc"]
        and harmonic["fault_absolute_contribution_share"]
        < frequency["fault_absolute_contribution_share"]
    ):
        raise ValueError("Frozen focal-feature mismatch no longer supports the annotation")
    return selected


def _feature_color(feature: str) -> str:
    if feature == FOCAL_HARMONIC:
        return ORANGE
    if feature == FOCAL_FREQUENCY:
        return BLUE
    return NEUTRAL_DARK


def _save_pair(figure: Figure, output_dir: Path) -> tuple[Path, Path]:
    output_dir.mkdir(parents=True, exist_ok=True)
    png = output_dir / "external_feature_geometry.png"
    pdf = output_dir / "external_feature_geometry.pdf"
    figure.savefig(png, dpi=300, bbox_inches="tight", pad_inches=0.06)
    figure.savefig(
        pdf,
        bbox_inches="tight",
        pad_inches=0.06,
        metadata={"CreationDate": None, "ModDate": None},
    )
    plt.close(figure)
    return png, pdf


def plot_feature_geometry(data: pd.DataFrame, output_dir: Path) -> tuple[Path, Path]:
    """Render the two-panel discrimination/attribution comparison."""

    y = np.arange(len(data), dtype=float)
    colors = [_feature_color(feature) for feature in data["feature"]]
    auc = data["raw_direction_free_auc"].to_numpy(dtype=float)
    absolute_dz = data["absolute_matched_dz"].to_numpy(dtype=float)

    figure, (axis_discrimination, axis_contribution) = plt.subplots(
        1,
        2,
        figsize=(11.3, 5.6),
        sharey=True,
        gridspec_kw={"width_ratios": [1.04, 1.0]},
    )

    axis_discrimination.axvline(0.5, color=INK, linestyle=":", linewidth=1.0, zorder=1)
    for row, value, color in zip(y, auc, colors, strict=True):
        axis_discrimination.hlines(row, 0.5, value, color=color, linewidth=3.3, zorder=2)
    axis_discrimination.scatter(
        auc,
        y,
        s=38,
        color=colors,
        edgecolor=INK,
        linewidth=0.55,
        zorder=4,
    )
    axis_discrimination.set_xlim(0.48, 1.015)
    axis_discrimination.set_xticks(np.arange(0.5, 1.01, 0.1))
    axis_discrimination.set_xlabel("Direction-free single-feature AUROC")
    axis_discrimination.set_yticks(y, data["feature_label"])
    axis_discrimination.invert_yaxis()
    axis_discrimination.set_title(
        "(a) Same-block discrimination", loc="left", fontweight="bold"
    )
    axis_discrimination.grid(axis="x")
    axis_discrimination.text(
        0.503,
        len(data) - 0.62,
        "chance",
        rotation=90,
        va="bottom",
        ha="left",
        fontsize=7.4,
        color=MUTED,
    )

    effect_axis = axis_discrimination.twiny()
    effect_axis.scatter(
        absolute_dz,
        y,
        s=36,
        marker="D",
        facecolor="white",
        edgecolor=colors,
        linewidth=1.25,
        zorder=5,
    )
    effect_axis.set_xlim(0, 1.4)
    effect_axis.set_xticks(np.arange(0, 1.41, 0.2))
    effect_axis.set_xlabel(r"Matched effect magnitude, $|d_z|$")
    effect_axis.spines["top"].set_visible(True)
    effect_axis.spines["top"].set_color(INK)
    effect_axis.tick_params(axis="x", labelsize=8)
    effect_axis.patch.set_alpha(0)

    for label, feature in zip(
        axis_discrimination.get_yticklabels(), data["feature"], strict=True
    ):
        if feature in {FOCAL_HARMONIC, FOCAL_FREQUENCY}:
            label.set_color(_feature_color(feature))
            label.set_fontweight("bold")

    fault_share = data["fault_absolute_contribution_share"].to_numpy(dtype=float)
    health_share = data[
        "healthy_test_absolute_contribution_share"
    ].to_numpy(dtype=float)
    height = 0.30
    fault_bars = axis_contribution.barh(
        y - height / 2,
        fault_share,
        height=height,
        color=ORANGE_LIGHT,
        edgecolor=ORANGE,
        linewidth=0.85,
        label="Fault (48 records)",
    )
    health_bars = axis_contribution.barh(
        y + height / 2,
        health_share,
        height=height,
        color="white",
        edgecolor=BLUE,
        linewidth=1.05,
        hatch="///",
        label="Held-out health (4 records)",
    )
    for bars, values in ((fault_bars, fault_share), (health_bars, health_share)):
        for bar, value in zip(bars, values, strict=True):
            axis_contribution.text(
                value + 0.006,
                bar.get_y() + bar.get_height() / 2,
                f"{value:.1%}",
                va="center",
                fontsize=7.2,
                color=INK,
            )
    axis_contribution.set_xlim(0, 0.44)
    axis_contribution.set_xticks(np.arange(0, 0.41, 0.1))
    axis_contribution.xaxis.set_major_formatter(PercentFormatter(1.0, decimals=0))
    axis_contribution.set_xlabel("Mean absolute Mahalanobis contribution share")
    axis_contribution.set_title(
        "(b) Frozen-score attribution", loc="left", fontweight="bold"
    )
    axis_contribution.grid(axis="x")
    axis_contribution.tick_params(axis="y", left=False, labelleft=False)
    axis_contribution.legend(loc="upper right", fontsize=8)

    marker_legend = [
        Line2D(
            [0],
            [0],
            marker="o",
            color="none",
            markerfacecolor=NEUTRAL_DARK,
            markeredgecolor=INK,
            markersize=5.5,
            label="Direction-free AUROC (bottom axis)",
        ),
        Line2D(
            [0],
            [0],
            marker="D",
            color="none",
            markerfacecolor="white",
            markeredgecolor=NEUTRAL_DARK,
            markersize=5,
            label=r"$|d_z|$ from matched differences (top axis)",
        ),
    ]
    axis_discrimination.legend(
        handles=marker_legend,
        loc="lower right",
        fontsize=7.6,
        handletextpad=0.6,
    )

    figure.subplots_adjust(left=0.205, right=0.985, top=0.86, bottom=0.13, wspace=0.20)
    return _save_pair(figure, output_dir)


def main() -> None:
    args = parse_args()
    configure_style()
    prepared = prepare_feature_geometry(pd.read_csv(args.summary))
    outputs = plot_feature_geometry(prepared, args.output_dir)
    print("Saved external feature-geometry figure:")
    for output in outputs:
        print(f"  {output.resolve()}")


if __name__ == "__main__":
    main()
