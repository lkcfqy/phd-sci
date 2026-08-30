"""Create the Paper 2 protocol workflow and representative torque-band figures."""

from __future__ import annotations

import argparse
import ast
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from matplotlib.lines import Line2D
from matplotlib.patches import FancyArrowPatch, FancyBboxPatch

from pmsm_sci.torque.conformal import KnnGeometryScaler, conformal_quantile, curvewise_max_error
from pmsm_sci.torque.data import load_published_torque_data
from pmsm_sci.torque.models import FourierSurrogate, build_regressor
from pmsm_sci.torque.splits import make_primary_split

BLUE = "#2F6B9A"
ORANGE = "#D97732"
DARK = "#263238"
GREY = "#7A858B"
LIGHT_GREY = "#D9DEE1"
PALE_BLUE = "#E8F0F6"
PALE_ORANGE = "#FBEFE6"
PALE_GREY = "#F1F3F4"
PRIMARY_SEED = 20260821
PRIMARY_MODEL = "ard_gaussian_process"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--data-root",
        type=Path,
        default=Path("data/raw/PMSM_torque_data"),
    )
    parser.add_argument(
        "--benchmark-dir",
        type=Path,
        default=Path("results/paper2_torque_conformal"),
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("papers/paper2_torque_uq/figures"),
    )
    parser.add_argument(
        "--selection-dir",
        type=Path,
        default=Path("results/paper2_representative_curves"),
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


def save_figure(figure: plt.Figure, output_dir: Path, stem: str) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    figure.savefig(output_dir / f"{stem}.png", dpi=300, bbox_inches="tight")
    figure.savefig(output_dir / f"{stem}.pdf", bbox_inches="tight")
    plt.close(figure)


def add_box(
    axis: plt.Axes,
    xy: tuple[float, float],
    width: float,
    height: float,
    text: str,
    *,
    facecolor: str,
    edgecolor: str = GREY,
    linestyle: str = "-",
    fontsize: float = 8.3,
) -> None:
    box = FancyBboxPatch(
        xy,
        width,
        height,
        boxstyle="round,pad=0.012,rounding_size=0.015",
        linewidth=1.0,
        edgecolor=edgecolor,
        facecolor=facecolor,
        linestyle=linestyle,
        transform=axis.transAxes,
    )
    axis.add_patch(box)
    axis.text(
        xy[0] + width / 2,
        xy[1] + height / 2,
        text,
        transform=axis.transAxes,
        ha="center",
        va="center",
        fontsize=fontsize,
        color=DARK,
    )


def add_arrow(
    axis: plt.Axes,
    start: tuple[float, float],
    end: tuple[float, float],
    *,
    color: str = GREY,
    linestyle: str = "-",
) -> None:
    axis.add_patch(
        FancyArrowPatch(
            start,
            end,
            transform=axis.transAxes,
            arrowstyle="-|>",
            mutation_scale=10,
            linewidth=1.1,
            color=color,
            linestyle=linestyle,
            connectionstyle="arc3,rad=0",
        )
    )


def make_protocol_workflow(output_dir: Path) -> None:
    figure, axis = plt.subplots(figsize=(11.0, 4.8))
    axis.set_axis_off()
    axis.set_xlim(0, 1)
    axis.set_ylim(0, 1)

    axis.text(0.05, 0.94, "Published data roles", fontsize=10, fontweight="normal")
    axis.text(0.38, 0.94, "Fit and calibrate", fontsize=10, fontweight="normal")
    axis.text(0.73, 0.94, "Evaluate complete torque curves", fontsize=10, fontweight="normal")
    axis.plot([0.33, 0.33], [0.08, 0.91], color=LIGHT_GREY, linewidth=1.0)
    axis.plot([0.68, 0.68], [0.08, 0.91], color=LIGHT_GREY, linewidth=1.0)

    add_box(
        axis,
        (0.04, 0.69),
        0.23,
        0.12,
        "train_test: 2,000 uniform designs\nfirst 1,800 development | final 200 fixed test",
        facecolor=PALE_GREY,
        fontsize=7.9,
    )
    add_box(axis, (0.04, 0.47), 0.23, 0.12, "uq_uniform: 11,250 designs", facecolor=PALE_GREY)
    add_box(axis, (0.04, 0.25), 0.23, 0.12, "uq_gauss: 10,000 designs", facecolor=PALE_GREY)

    add_box(axis, (0.38, 0.73), 0.12, 0.11, "Fit\n1,200", facecolor=PALE_BLUE, edgecolor=BLUE)
    add_box(axis, (0.54, 0.73), 0.11, 0.11, "Fourier-11\nsurrogate", facecolor=PALE_BLUE, edgecolor=BLUE)
    add_box(axis, (0.38, 0.54), 0.12, 0.11, "Calibration\n600", facecolor=PALE_ORANGE, edgecolor=ORANGE)
    add_box(axis, (0.54, 0.54), 0.11, 0.11, "Max curve error\n+ geometry scale", facecolor=PALE_ORANGE, edgecolor=ORANGE, fontsize=7.8)
    add_box(
        axis,
        (0.49, 0.35),
        0.16,
        0.11,
        "Evaluation curves\nfixed 200 + target halves",
        facecolor=PALE_GREY,
        fontsize=7.8,
    )
    add_box(
        axis,
        (0.38, 0.14),
        0.27,
        0.11,
        "Post-primary: target-X half-split\nquadratic density-ratio fit",
        facecolor="white",
        edgecolor=GREY,
        linestyle="--",
        fontsize=7.8,
    )

    add_box(axis, (0.73, 0.69), 0.22, 0.14, "Global and geometry-scaled\nsimultaneous bands", facecolor=PALE_ORANGE, edgecolor=ORANGE)
    add_box(axis, (0.73, 0.47), 0.22, 0.12, "Full-curve coverage, width,\nand torque functionals", facecolor=PALE_BLUE, edgecolor=BLUE)
    add_box(axis, (0.73, 0.29), 0.22, 0.10, "Geometry-only support p-value", facecolor=PALE_GREY)
    add_box(
        axis,
        (0.73, 0.11),
        0.22,
        0.10,
        "Weighted conformal: finite or vacuous",
        facecolor="white",
        edgecolor=GREY,
        linestyle="--",
        fontsize=7.8,
    )

    add_arrow(axis, (0.27, 0.75), (0.38, 0.785), color=BLUE)
    add_arrow(axis, (0.27, 0.75), (0.38, 0.595), color=ORANGE)
    add_arrow(axis, (0.50, 0.785), (0.54, 0.785), color=BLUE)
    add_arrow(axis, (0.50, 0.595), (0.54, 0.595), color=ORANGE)
    add_arrow(axis, (0.65, 0.785), (0.73, 0.76), color=BLUE)
    add_arrow(axis, (0.65, 0.595), (0.73, 0.76), color=ORANGE)
    add_arrow(axis, (0.27, 0.53), (0.49, 0.41), color=BLUE)
    add_arrow(axis, (0.27, 0.31), (0.49, 0.39), color=BLUE)
    add_arrow(axis, (0.65, 0.405), (0.73, 0.53), color=BLUE)
    add_arrow(axis, (0.65, 0.395), (0.73, 0.34), color=GREY)
    add_arrow(axis, (0.65, 0.415), (0.73, 0.72), color=ORANGE)
    add_arrow(axis, (0.27, 0.53), (0.38, 0.195), color=GREY, linestyle="--")
    add_arrow(axis, (0.27, 0.31), (0.38, 0.195), color=GREY, linestyle="--")
    add_arrow(axis, (0.65, 0.195), (0.73, 0.16), color=GREY, linestyle="--")

    figure.suptitle(
        "Data separation and curvewise uncertainty workflow",
        y=0.995,
        fontsize=12,
    )
    figure.text(
        0.5,
        0.015,
        "Torque labels from calibration and evaluation never select surrogate hyperparameters; dashed elements are post-primary diagnostics.",
        ha="center",
        fontsize=8,
        color=GREY,
    )
    figure.tight_layout(rect=(0.0, 0.04, 1.0, 0.96))
    save_figure(figure, output_dir, "paper2_protocol_workflow")


def normalize_from_development(
    development: np.ndarray,
    *arrays: np.ndarray,
) -> tuple[np.ndarray, ...]:
    minimum = development.min(axis=0)
    span = np.ptp(development, axis=0)
    if np.any(span <= 0):
        raise ValueError("every design parameter must vary in development")
    return tuple((np.asarray(array, dtype=float) - minimum) / span for array in arrays)


def choose_median_error(mask: np.ndarray, errors: np.ndarray) -> int:
    candidates = np.flatnonzero(mask)
    if len(candidates) == 0:
        raise ValueError("selection rule produced no candidate designs")
    candidate_errors = errors[candidates]
    target = np.median(candidate_errors)
    distances = np.abs(candidate_errors - target)
    return int(candidates[np.flatnonzero(distances == distances.min())[0]])


def select_representative_indices(
    *,
    uniform_error: np.ndarray,
    uniform_scale: np.ndarray,
    uniform_global_width: float,
    uniform_scaled_width: np.ndarray,
    gauss_error: np.ndarray,
    gauss_scale: np.ndarray,
    gauss_global_width: float,
    gauss_scaled_width: np.ndarray,
) -> list[tuple[str, str, int]]:
    uniform_cuts = np.quantile(uniform_scale, np.linspace(0.0, 1.0, 6))
    uniform_dense = uniform_scale < uniform_cuts[1]
    uniform_sparse = uniform_scale >= uniform_cuts[4]
    uniform_global_covered = uniform_error <= uniform_global_width
    uniform_scaled_covered = uniform_error <= uniform_scaled_width

    dense_index = choose_median_error(
        uniform_dense & uniform_global_covered & uniform_scaled_covered,
        uniform_error,
    )
    rescued_index = choose_median_error(
        uniform_sparse & ~uniform_global_covered & uniform_scaled_covered,
        uniform_error,
    )
    missed_index = choose_median_error(
        uniform_sparse & ~uniform_global_covered & ~uniform_scaled_covered,
        uniform_error,
    )

    gauss_cuts = np.quantile(gauss_scale, np.linspace(0.0, 1.0, 6))
    gauss_middle = (gauss_scale >= gauss_cuts[2]) & (gauss_scale < gauss_cuts[3])
    gauss_covered = (gauss_error <= gauss_global_width) & (gauss_error <= gauss_scaled_width)
    gauss_index = choose_median_error(gauss_middle & gauss_covered, gauss_error)
    return [
        ("uq_uniform", "dense_both_covered", dense_index),
        ("uq_uniform", "sparse_scaled_rescue", rescued_index),
        ("uq_uniform", "sparse_both_missed", missed_index),
        ("uq_gauss", "gaussian_middle_both_covered", gauss_index),
    ]


def make_representative_curves(
    data_root: Path,
    benchmark_dir: Path,
    output_dir: Path,
    selection_dir: Path,
) -> None:
    data = load_published_torque_data(data_root)
    development = data["train_test"]
    x_all = development.parameters.to_numpy(dtype=float)
    x_uniform = data["uq_uniform"].parameters.to_numpy(dtype=float)
    x_gauss = data["uq_gauss"].parameters.to_numpy(dtype=float)
    x_normalized, uniform_normalized, gauss_normalized = normalize_from_development(
        x_all[:1800],
        x_all,
        x_uniform,
        x_gauss,
    )
    summary = pd.read_csv(benchmark_dir / "aggregate_summary.csv")
    selection_row = summary.loc[
        summary["seed"].eq(PRIMARY_SEED)
        & summary["model"].eq(PRIMARY_MODEL)
        & summary["distribution"].eq("uq_uniform")
        & summary["band"].eq("global")
        & np.isclose(summary["alpha"], 0.1)
    ]
    if len(selection_row) != 1:
        raise ValueError("primary surrogate selection row is missing or duplicated")
    settings = ast.literal_eval(str(selection_row.iloc[0]["selected_parameters"]))
    split = make_primary_split(seed=PRIMARY_SEED)
    surrogate = FourierSurrogate(
        build_regressor(PRIMARY_MODEL, seed=PRIMARY_SEED, parameters=settings)
    ).fit(x_normalized[split.fit], development.torque[split.fit])
    calibration_prediction = surrogate.predict(x_normalized[split.calibration])
    calibration_error = curvewise_max_error(
        development.torque[split.calibration],
        calibration_prediction,
    )
    geometry = KnnGeometryScaler(neighbours=5, floor=0.25).fit(x_normalized[split.fit])
    calibration_scale = geometry.scale(x_normalized[split.calibration])
    global_width = conformal_quantile(calibration_error, 0.1)
    scaled_quantile = conformal_quantile(calibration_error / calibration_scale, 0.1)

    predictions = {
        "uq_uniform": surrogate.predict(uniform_normalized),
        "uq_gauss": surrogate.predict(gauss_normalized),
    }
    normalized_parameters = {
        "uq_uniform": uniform_normalized,
        "uq_gauss": gauss_normalized,
    }
    errors = {
        name: curvewise_max_error(data[name].torque, predictions[name])
        for name in predictions
    }
    scales = {name: geometry.scale(values) for name, values in normalized_parameters.items()}
    scaled_widths = {name: scaled_quantile * values for name, values in scales.items()}
    selected = select_representative_indices(
        uniform_error=errors["uq_uniform"],
        uniform_scale=scales["uq_uniform"],
        uniform_global_width=global_width,
        uniform_scaled_width=scaled_widths["uq_uniform"],
        gauss_error=errors["uq_gauss"],
        gauss_scale=scales["uq_gauss"],
        gauss_global_width=global_width,
        gauss_scaled_width=scaled_widths["uq_gauss"],
    )

    manifest_rows: list[dict[str, object]] = []
    panel_data: list[dict[str, object]] = []
    for distribution, role, index in selected:
        error = errors[distribution][index]
        local_width = scaled_widths[distribution][index]
        manifest_rows.append(
            {
                "distribution": distribution,
                "selection_role": role,
                "published_row_index": index,
                "selection_rule": "median curve-max error within the predeclared role subset",
                "curve_max_error": error,
                "global_half_width": global_width,
                "geometry_scaled_half_width": local_width,
                "geometry_scale": scales[distribution][index],
                "global_covered": int(error <= global_width),
                "geometry_scaled_covered": int(error <= local_width),
            }
        )
        panel_data.append(
            {
                "distribution": distribution,
                "role": role,
                "index": index,
                "truth": data[distribution].torque[index],
                "prediction": predictions[distribution][index],
                "local_width": local_width,
                "error": error,
            }
        )
    selection_dir.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(manifest_rows).to_csv(selection_dir / "selection_manifest.csv", index=False)

    figure, axes = plt.subplots(2, 2, figsize=(9.2, 6.4), sharex=True, sharey=True)
    labels = {
        "dense_both_covered": "Dense uniform: both cover",
        "sparse_scaled_rescue": "Sparse uniform: scaled band rescues",
        "sparse_both_missed": "Sparse uniform: both miss",
        "gaussian_middle_both_covered": "Gaussian middle-density: both cover",
    }
    angles = development.angles_deg
    all_values: list[np.ndarray] = []
    for item in panel_data:
        prediction = np.asarray(item["prediction"])
        local_width = float(item["local_width"])
        all_values.extend(
            [
                np.asarray(item["truth"]),
                prediction - max(global_width, local_width),
                prediction + max(global_width, local_width),
            ]
        )
    value_min = min(float(np.min(values)) for values in all_values)
    value_max = max(float(np.max(values)) for values in all_values)
    padding = 0.06 * (value_max - value_min)

    for panel, (axis, item) in enumerate(zip(axes.flat, panel_data, strict=True)):
        truth = np.asarray(item["truth"])
        prediction = np.asarray(item["prediction"])
        local_width = float(item["local_width"])
        axis.fill_between(
            angles,
            prediction - local_width,
            prediction + local_width,
            color=ORANGE,
            alpha=0.18,
            linewidth=0,
            zorder=1,
        )
        axis.plot(
            angles,
            prediction - local_width,
            color=ORANGE,
            linewidth=0.9,
            zorder=2,
        )
        axis.plot(
            angles,
            prediction + local_width,
            color=ORANGE,
            linewidth=0.9,
            zorder=2,
        )
        axis.plot(
            angles,
            prediction - global_width,
            color=BLUE,
            linewidth=0.9,
            linestyle="--",
            zorder=2,
        )
        axis.plot(
            angles,
            prediction + global_width,
            color=BLUE,
            linewidth=0.9,
            linestyle="--",
            zorder=2,
        )
        axis.plot(angles, prediction, color=BLUE, linewidth=1.2, zorder=3)
        axis.plot(angles, truth, color=DARK, linewidth=1.35, zorder=4)
        role = str(item["role"])
        axis.set_title(f"({chr(97 + panel)}) {labels[role]}", loc="left", pad=6)
        axis.text(
            0.02,
            0.04,
            (
                f"row {item['index']}  |  max error {float(item['error']):.4f}\n"
                f"global {global_width:.4f}  |  scaled {local_width:.4f}"
            ),
            transform=axis.transAxes,
            ha="left",
            va="bottom",
            fontsize=7.4,
            color=GREY,
        )
        axis.set_xlim(float(angles.min()), float(angles.max()))
        axis.set_ylim(value_min - padding, value_max + padding)
        axis.grid(axis="y", color=LIGHT_GREY, linewidth=0.55)
        axis.spines[["top", "right"]].set_visible(False)
        if panel >= 2:
            axis.set_xlabel("Mechanical angle (degrees)")
        if panel % 2 == 0:
            axis.set_ylabel("Torque (source-archive units)")

    legend = [
        Line2D([0], [0], color=DARK, linewidth=1.4, label="High-fidelity torque"),
        Line2D([0], [0], color=BLUE, linewidth=1.2, label="Fourier surrogate"),
        Line2D([0], [0], color=BLUE, linewidth=0.9, linestyle="--", label="Global boundaries"),
        Line2D([0], [0], color=ORANGE, linewidth=1.0, label="Geometry-scaled band"),
    ]
    figure.legend(
        handles=legend,
        loc="upper center",
        bbox_to_anchor=(0.5, 0.945),
        frameon=False,
        ncol=4,
        fontsize=8,
    )
    figure.suptitle("Representative 90% simultaneous torque bands", y=0.995, fontsize=12)
    figure.text(
        0.5,
        0.012,
        "Examples are selected by deterministic role and median-error rules; bands cover a design only when all 120 angles lie inside.",
        ha="center",
        fontsize=8,
        color=GREY,
    )
    figure.tight_layout(rect=(0.0, 0.045, 1.0, 0.89))
    save_figure(figure, output_dir, "paper2_representative_curves")


def main() -> None:
    args = parse_args()
    publication_style()
    make_protocol_workflow(args.output_dir)
    make_representative_curves(
        args.data_root,
        args.benchmark_dir,
        args.output_dir,
        args.selection_dir,
    )
    print(f"Wrote four figure files to {args.output_dir.resolve()}")


if __name__ == "__main__":
    main()
