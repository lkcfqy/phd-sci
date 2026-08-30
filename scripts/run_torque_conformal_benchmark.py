"""Run the Paper 2 curvewise conformal torque-surrogate benchmark."""

from __future__ import annotations

import argparse
import json
import platform
import sys
import time
from datetime import UTC, datetime
from pathlib import Path

import numpy as np
import pandas as pd
import sklearn

from pmsm_sci.torque.conformal import (
    KnnGeometryScaler,
    conformal_quantile,
    curvewise_max_error,
    support_p_values,
    wilson_interval,
)
from pmsm_sci.torque.data import load_published_torque_data, sha256
from pmsm_sci.torque.models import FourierSurrogate, build_regressor
from pmsm_sci.torque.selection import select_hyperparameters
from pmsm_sci.torque.splits import make_primary_split

PRIMARY_SEED = 20260821
PRIMARY_FOCUS_MODEL = "ard_gaussian_process"
DEFAULT_MODELS = [
    "poly2_ridge",
    "rbf_kernel_ridge",
    "ard_gaussian_process",
    "extra_trees",
]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--data-root",
        type=Path,
        default=Path("data/raw/PMSM_torque_data"),
    )
    parser.add_argument(
        "--results-dir",
        type=Path,
        default=Path("results/paper2_torque_conformal"),
    )
    parser.add_argument("--models", nargs="+", choices=DEFAULT_MODELS, default=DEFAULT_MODELS)
    parser.add_argument("--seeds", nargs="+", type=int, default=[PRIMARY_SEED])
    parser.add_argument("--alpha", nargs="+", type=float, default=[0.1, 0.05])
    parser.add_argument("--support-alpha", type=float, default=0.05)
    return parser.parse_args()


def normalize_with_development(
    development: np.ndarray,
    *arrays: np.ndarray,
) -> tuple[np.ndarray, ...]:
    minimum = development.min(axis=0)
    span = np.ptp(development, axis=0)
    if np.any(span <= 0):
        raise ValueError("every design parameter must vary in the development pool")
    return tuple((np.asarray(array, dtype=float) - minimum) / span for array in arrays)


def prediction_metrics(truth: np.ndarray, prediction: np.ndarray) -> dict[str, float]:
    absolute = np.abs(truth - prediction)
    true_ripple = np.ptp(truth, axis=1)
    predicted_ripple = np.ptp(prediction, axis=1)
    return {
        "waveform_mae": float(np.mean(absolute)),
        "waveform_rmse": float(np.sqrt(np.mean((truth - prediction) ** 2))),
        "waveform_mape_percent": float(np.mean(absolute / np.abs(truth)) * 100.0),
        "mean_curve_max_error": float(np.mean(np.max(absolute, axis=1))),
        "mean_torque_mae": float(np.mean(np.abs(truth.mean(axis=1) - prediction.mean(axis=1)))),
        "torque_ripple_mae": float(np.mean(np.abs(true_ripple - predicted_ripple))),
    }


def evaluate_band(
    *,
    truth: np.ndarray,
    prediction: np.ndarray,
    half_width: np.ndarray,
    support_p: np.ndarray,
    support_alpha: float,
) -> tuple[dict[str, float | int], np.ndarray]:
    errors = np.abs(truth - prediction)
    curve_errors = errors.max(axis=1)
    width = np.asarray(half_width, dtype=float)
    if width.ndim == 0:
        width = np.full(len(truth), float(width))
    covered = curve_errors <= width
    lower, upper = wilson_interval(int(covered.sum()), len(covered))
    accepted = support_p > support_alpha
    accepted_coverage = float(np.mean(covered[accepted])) if np.any(accepted) else float("nan")
    metrics: dict[str, float | int] = {
        "designs": len(truth),
        "covered_designs": int(covered.sum()),
        "curvewise_coverage": float(np.mean(covered)),
        "coverage_wilson_lower": lower,
        "coverage_wilson_upper": upper,
        "pointwise_coverage": float(np.mean(errors <= width[:, None])),
        "mean_half_width": float(np.mean(width)),
        "p90_half_width": float(np.quantile(width, 0.9)),
        "support_rejected_designs": int((~accepted).sum()),
        "support_rejection_rate": float(np.mean(~accepted)),
        "accepted_curvewise_coverage": accepted_coverage,
    }
    return metrics, covered


def main() -> None:
    args = parse_args()
    if any(not 0.0 < alpha < 1.0 for alpha in args.alpha):
        raise ValueError("all alpha values must lie strictly between zero and one")
    datasets = load_published_torque_data(args.data_root)
    development = datasets["train_test"]
    x_all = development.parameters.to_numpy(dtype=float)
    y_all = development.torque
    test_sets = {
        "internal_uniform": (x_all[1800:], y_all[1800:]),
        "uq_uniform": (
            datasets["uq_uniform"].parameters.to_numpy(dtype=float),
            datasets["uq_uniform"].torque,
        ),
        "uq_gauss_shift": (
            datasets["uq_gauss"].parameters.to_numpy(dtype=float),
            datasets["uq_gauss"].torque,
        ),
    }
    normalized = normalize_with_development(
        x_all[:1800],
        x_all,
        *(item[0] for item in test_sets.values()),
    )
    x_normalized = normalized[0]
    normalized_tests = {
        name: (normalized[index + 1], test_sets[name][1])
        for index, name in enumerate(test_sets)
    }

    args.results_dir.mkdir(parents=True, exist_ok=True)
    summary_rows: list[dict[str, object]] = []
    selection_rows: list[dict[str, object]] = []
    design_rows: list[dict[str, object]] = []
    quintile_rows: list[dict[str, object]] = []
    timings: list[dict[str, object]] = []
    for seed in args.seeds:
        split = make_primary_split(seed=seed)
        for model_name in args.models:
            started = time.perf_counter()
            settings, model_selection = select_hyperparameters(
                model_name,
                x_normalized[split.fit],
                y_all[split.fit],
                seed=seed,
            )
            for row in model_selection:
                selection_rows.append({"seed": seed, **row})
            surrogate = FourierSurrogate(
                build_regressor(model_name, seed=seed, parameters=settings)
            ).fit(x_normalized[split.fit], y_all[split.fit])
            fit_seconds = time.perf_counter() - started

            calibration_prediction = surrogate.predict(x_normalized[split.calibration])
            calibration_error = curvewise_max_error(
                y_all[split.calibration],
                calibration_prediction,
            )
            scaler = KnnGeometryScaler(neighbours=5, floor=0.25).fit(
                x_normalized[split.fit]
            )
            calibration_scale = scaler.scale(x_normalized[split.calibration])
            calibration_distance = scaler.distance(x_normalized[split.calibration])

            for distribution, (x_test, y_test) in normalized_tests.items():
                prediction_started = time.perf_counter()
                prediction = surrogate.predict(x_test)
                prediction_seconds = time.perf_counter() - prediction_started
                base_metrics = prediction_metrics(y_test, prediction)
                geometry_scale = scaler.scale(x_test)
                geometry_distance = scaler.distance(x_test)
                support_p = support_p_values(calibration_distance, geometry_distance)
                curve_error = curvewise_max_error(y_test, prediction)

                for alpha in args.alpha:
                    global_quantile = conformal_quantile(calibration_error, alpha)
                    local_quantile = conformal_quantile(
                        calibration_error / calibration_scale,
                        alpha,
                    )
                    for band, quantile, half_width in (
                        ("global", global_quantile, np.full(len(y_test), global_quantile)),
                        ("geometry_scaled", local_quantile, local_quantile * geometry_scale),
                    ):
                        band_metrics, covered = evaluate_band(
                            truth=y_test,
                            prediction=prediction,
                            half_width=half_width,
                            support_p=support_p,
                            support_alpha=args.support_alpha,
                        )
                        summary_rows.append(
                            {
                                "seed": seed,
                                "model": model_name,
                                "selected_parameters": repr(settings),
                                "distribution": distribution,
                                "band": band,
                                "alpha": alpha,
                                "nominal_curvewise_coverage": 1.0 - alpha,
                                "calibration_designs": len(split.calibration),
                                "conformal_quantile": quantile,
                                **base_metrics,
                                **band_metrics,
                            }
                        )
                        if (
                            seed == PRIMARY_SEED
                            and model_name == PRIMARY_FOCUS_MODEL
                            and alpha == 0.1
                        ):
                            for row_index in range(len(y_test)):
                                design_rows.append(
                                    {
                                        "distribution": distribution,
                                        "row_index": row_index,
                                        "band": band,
                                        "curve_max_error": curve_error[row_index],
                                        "half_width": half_width[row_index],
                                        "covered": int(covered[row_index]),
                                        "geometry_distance": geometry_distance[row_index],
                                        "geometry_scale": geometry_scale[row_index],
                                        "support_p_value": support_p[row_index],
                                        "support_rejected": int(
                                            support_p[row_index] <= args.support_alpha
                                        ),
                                    }
                                )

                    if (
                        seed == PRIMARY_SEED
                        and model_name == PRIMARY_FOCUS_MODEL
                        and alpha == 0.1
                    ):
                        cut_points = np.quantile(geometry_scale, np.linspace(0.0, 1.0, 6))
                        local_width = local_quantile * geometry_scale
                        for quintile in range(5):
                            if quintile < 4:
                                selected = (geometry_scale >= cut_points[quintile]) & (
                                    geometry_scale < cut_points[quintile + 1]
                                )
                            else:
                                selected = (geometry_scale >= cut_points[quintile]) & (
                                    geometry_scale <= cut_points[quintile + 1]
                                )
                            quintile_rows.append(
                                {
                                    "distribution": distribution,
                                    "distance_quintile": quintile + 1,
                                    "designs": int(selected.sum()),
                                    "scale_lower": cut_points[quintile],
                                    "scale_upper": cut_points[quintile + 1],
                                    "mean_curve_max_error": float(np.mean(curve_error[selected])),
                                    "global_coverage": float(
                                        np.mean(curve_error[selected] <= global_quantile)
                                    ),
                                    "geometry_scaled_coverage": float(
                                        np.mean(curve_error[selected] <= local_width[selected])
                                    ),
                                    "mean_geometry_scaled_half_width": float(
                                        np.mean(local_width[selected])
                                    ),
                                }
                            )
                timings.append(
                    {
                        "seed": seed,
                        "model": model_name,
                        "distribution": distribution,
                        "fit_and_select_seconds": fit_seconds,
                        "prediction_seconds": prediction_seconds,
                        "designs": len(y_test),
                    }
                )

    pd.DataFrame(summary_rows).to_csv(args.results_dir / "aggregate_summary.csv", index=False)
    pd.DataFrame(selection_rows).to_csv(
        args.results_dir / "source_only_hyperparameter_selection.csv",
        index=False,
    )
    pd.DataFrame(design_rows).to_csv(
        args.results_dir / "primary_per_design_scores.csv.gz",
        index=False,
        compression="gzip",
    )
    pd.DataFrame(quintile_rows).to_csv(
        args.results_dir / "primary_distance_quintiles.csv",
        index=False,
    )
    pd.DataFrame(timings).to_csv(args.results_dir / "timings.csv", index=False)

    input_files: list[dict[str, object]] = []
    for dataset in datasets.values():
        for path in (dataset.parameter_path, dataset.torque_path):
            input_files.append(
                {
                    "file": path.name,
                    "bytes": path.stat().st_size,
                    "sha256": sha256(path),
                }
            )
    metadata = {
        "created_utc": datetime.now(UTC).isoformat(),
        "protocol": "paper2_curvewise_conformal_v1",
        "source_doi": "10.5281/zenodo.15688397",
        "source_article_doi": "10.1007/s00366-025-02123-1",
        "models": args.models,
        "primary_focus_model": PRIMARY_FOCUS_MODEL,
        "seeds": args.seeds,
        "alpha": args.alpha,
        "support_alpha": args.support_alpha,
        "development_roles": {"fit": 1200, "calibration": 600, "internal_test": 200},
        "retained_fourier_components": 11,
        "curve_points": 120,
        "hyperparameter_selection": "three-fold fit-only waveform MAE",
        "python": sys.version,
        "platform": platform.platform(),
        "numpy": np.__version__,
        "pandas": pd.__version__,
        "scikit_learn": sklearn.__version__,
        "input_files": input_files,
        "scope_limit": (
            "All confirmation tables originate from the same published two-dimensional "
            "quarter-symmetry PMSM simulator and are not hardware or cross-topology validation."
        ),
    }
    (args.results_dir / "run_metadata.json").write_text(
        json.dumps(metadata, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    print(
        f"Wrote {len(summary_rows)} aggregate rows for {len(args.models)} models "
        f"and {len(args.seeds)} seeds to {args.results_dir.resolve()}"
    )


if __name__ == "__main__":
    main()
