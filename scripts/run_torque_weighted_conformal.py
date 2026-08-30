"""Run the Paper 2 weighted-conformal covariate-shift comparator."""

from __future__ import annotations

import argparse
import json
import platform
import sys
from datetime import UTC, datetime
from pathlib import Path

import numpy as np
import pandas as pd
import sklearn
from sklearn.metrics import roc_auc_score

from pmsm_sci.torque.conformal import (
    KnnGeometryScaler,
    conformal_quantile,
    curvewise_max_error,
    wilson_interval,
)
from pmsm_sci.torque.covariate_shift import (
    QuadraticLogisticDensityRatio,
    effective_sample_size,
    weighted_conformal_quantiles,
)
from pmsm_sci.torque.data import load_published_torque_data, sha256
from pmsm_sci.torque.models import FourierSurrogate, build_regressor
from pmsm_sci.torque.selection import select_hyperparameters
from pmsm_sci.torque.splits import make_primary_split

PRIMARY_SEED = 20260821
TARGETS = ("uq_uniform", "uq_gauss")


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
        default=Path("results/paper2_weighted_conformal"),
    )
    parser.add_argument("--seed", type=int, default=PRIMARY_SEED)
    parser.add_argument("--alpha", nargs="+", type=float, default=[0.1, 0.05])
    return parser.parse_args()


def normalize_from_development(
    development: np.ndarray,
    *arrays: np.ndarray,
) -> tuple[np.ndarray, ...]:
    """Apply the development-only range transform used by the main benchmark."""

    minimum = np.min(development, axis=0)
    span = np.ptp(development, axis=0)
    if np.any(span <= 0):
        raise ValueError("every design parameter must vary in development")
    return tuple((np.asarray(array, dtype=float) - minimum) / span for array in arrays)


def split_unlabeled_target(length: int, seed: int) -> tuple[np.ndarray, np.ndarray]:
    """Freeze disjoint target covariates for ratio fitting and band evaluation."""

    if length < 4:
        raise ValueError("target data must contain at least four designs")
    indices = np.random.default_rng(seed).permutation(length)
    cut = length // 2
    return np.sort(indices[:cut]), np.sort(indices[cut:])


def summarize_band(errors: np.ndarray, half_width: np.ndarray) -> dict[str, float | int]:
    """Summarize finite and vacuous bands without hiding infinite widths."""

    curve_error = np.asarray(errors, dtype=float)
    width = np.asarray(half_width, dtype=float)
    if curve_error.ndim != 1 or width.shape != curve_error.shape:
        raise ValueError("errors and half_width must be aligned vectors")
    finite = np.isfinite(width)
    covered = curve_error <= width
    lower, upper = wilson_interval(int(covered.sum()), len(covered))
    finite_coverage = float(np.mean(covered[finite])) if np.any(finite) else float("nan")
    return {
        "designs": len(curve_error),
        "finite_bands": int(finite.sum()),
        "finite_band_rate": float(np.mean(finite)),
        "vacuous_band_rate": float(np.mean(~finite)),
        "curvewise_coverage_including_vacuous": float(np.mean(covered)),
        "coverage_wilson_lower_including_vacuous": lower,
        "coverage_wilson_upper_including_vacuous": upper,
        "finite_band_curvewise_coverage": finite_coverage,
        "mean_finite_half_width": float(np.mean(width[finite])) if np.any(finite) else float("nan"),
        "p90_finite_half_width": (
            float(np.quantile(width[finite], 0.9)) if np.any(finite) else float("nan")
        ),
    }


def main() -> None:
    args = parse_args()
    if any(not 0.0 < alpha < 1.0 for alpha in args.alpha):
        raise ValueError("all alpha values must lie strictly between zero and one")

    data = load_published_torque_data(args.data_root)
    development = data["train_test"]
    x_all = development.parameters.to_numpy(dtype=float)
    y_all = development.torque
    raw_targets = [data[name].parameters.to_numpy(dtype=float) for name in TARGETS]
    normalized = normalize_from_development(x_all[:1800], x_all, *raw_targets)
    x_normalized = normalized[0]
    target_parameters = dict(zip(TARGETS, normalized[1:], strict=True))
    split = make_primary_split(seed=args.seed)

    settings, _ = select_hyperparameters(
        "poly2_ridge",
        x_normalized[split.fit],
        y_all[split.fit],
        seed=args.seed,
    )
    surrogate = FourierSurrogate(
        build_regressor("poly2_ridge", seed=args.seed, parameters=settings)
    ).fit(x_normalized[split.fit], y_all[split.fit])
    calibration_error = curvewise_max_error(
        y_all[split.calibration],
        surrogate.predict(x_normalized[split.calibration]),
    )
    geometry = KnnGeometryScaler(neighbours=5, floor=0.25).fit(x_normalized[split.fit])
    calibration_scale = geometry.scale(x_normalized[split.calibration])

    summary_rows: list[dict[str, object]] = []
    diagnostic_rows: list[dict[str, object]] = []
    design_rows: list[dict[str, object]] = []
    target_partitions: dict[str, dict[str, list[int]]] = {}

    for target_offset, target_name in enumerate(TARGETS):
        x_target = target_parameters[target_name]
        y_target = data[target_name].torque
        ratio_fit, evaluation = split_unlabeled_target(
            len(x_target),
            args.seed + target_offset,
        )
        target_partitions[target_name] = {
            "density_ratio_fit": ratio_fit.tolist(),
            "band_evaluation": evaluation.tolist(),
        }
        estimator = QuadraticLogisticDensityRatio(seed=args.seed).fit(
            x_normalized[split.fit],
            x_target[ratio_fit],
        )
        calibration_weight = estimator.ratio(x_normalized[split.calibration])
        test_weight = estimator.ratio(x_target[evaluation])
        domain_truth = np.concatenate(
            (np.zeros(len(split.calibration)), np.ones(len(evaluation)))
        )
        domain_score = np.concatenate(
            (
                estimator.log_ratio(x_normalized[split.calibration]),
                estimator.log_ratio(x_target[evaluation]),
            )
        )
        domain_auc = float(roc_auc_score(domain_truth, domain_score))
        prediction = surrogate.predict(x_target[evaluation])
        test_error = curvewise_max_error(y_target[evaluation], prediction)
        test_scale = geometry.scale(x_target[evaluation])

        for role, weights in (
            ("source_calibration", calibration_weight),
            ("target_evaluation", test_weight),
        ):
            quantiles = np.quantile(weights, [0.0, 0.1, 0.5, 0.9, 0.99, 1.0])
            diagnostic_rows.append(
                {
                    "target_distribution": target_name,
                    "role": role,
                    "designs": len(weights),
                    "weight_sum": float(weights.sum()),
                    "effective_sample_size": effective_sample_size(weights),
                    "max_normalized_weight": float(weights.max() / weights.sum()),
                    "weight_min": quantiles[0],
                    "weight_p10": quantiles[1],
                    "weight_median": quantiles[2],
                    "weight_p90": quantiles[3],
                    "weight_p99": quantiles[4],
                    "weight_max": quantiles[5],
                    "selected_logistic_c": estimator.selected_c,
                    "heldout_domain_auc": domain_auc,
                }
            )

        for alpha in args.alpha:
            global_width = np.full(
                len(evaluation),
                conformal_quantile(calibration_error, alpha),
            )
            scaled_quantile = conformal_quantile(
                calibration_error / calibration_scale,
                alpha,
            )
            scaled_width = scaled_quantile * test_scale
            weighted_width = weighted_conformal_quantiles(
                calibration_error,
                calibration_weight,
                test_weight,
                alpha,
            )
            for method, width in (
                ("global_split_conformal", global_width),
                ("geometry_scaled_split_conformal", scaled_width),
                ("estimated_weighted_split_conformal", weighted_width),
            ):
                summary_rows.append(
                    {
                        "target_distribution": target_name,
                        "method": method,
                        "alpha": alpha,
                        "nominal_curvewise_coverage": 1.0 - alpha,
                        "source_fit_designs": len(split.fit),
                        "source_calibration_designs": len(split.calibration),
                        "target_density_ratio_fit_designs": len(ratio_fit),
                        "target_band_evaluation_designs": len(evaluation),
                        "selected_surrogate_parameters": repr(settings),
                        "selected_logistic_c": estimator.selected_c,
                        "heldout_domain_auc": domain_auc,
                        "calibration_weight_sum": float(calibration_weight.sum()),
                        "calibration_weight_ess": effective_sample_size(calibration_weight),
                        "calibration_max_normalized_weight": float(
                            calibration_weight.max() / calibration_weight.sum()
                        ),
                        **summarize_band(test_error, width),
                    }
                )

            for local_index, published_index in enumerate(evaluation):
                design_rows.append(
                    {
                        "target_distribution": target_name,
                        "published_row_index": int(published_index),
                        "alpha": alpha,
                        "curve_max_error": test_error[local_index],
                        "density_ratio_weight": test_weight[local_index],
                        "weighted_half_width": weighted_width[local_index],
                        "weighted_band_finite": int(np.isfinite(weighted_width[local_index])),
                        "weighted_band_covered_including_vacuous": int(
                            test_error[local_index] <= weighted_width[local_index]
                        ),
                    }
                )

    args.results_dir.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(summary_rows).to_csv(args.results_dir / "comparison_summary.csv", index=False)
    pd.DataFrame(diagnostic_rows).to_csv(
        args.results_dir / "density_ratio_diagnostics.csv",
        index=False,
    )
    pd.DataFrame(design_rows).to_csv(
        args.results_dir / "weighted_per_design.csv.gz",
        index=False,
        compression="gzip",
    )
    input_manifest = []
    for dataset in data.values():
        for path in (dataset.parameter_path, dataset.torque_path):
            input_manifest.append(
                {
                    "file": path.name,
                    "bytes": path.stat().st_size,
                    "sha256": sha256(path),
                }
            )
    metadata = {
        "created_utc": datetime.now(UTC).isoformat(),
        "protocol": "paper2_estimated_weighted_conformal_v1",
        "source_doi": "10.5281/zenodo.15688397",
        "source_article_doi": "10.1007/s00366-025-02123-1",
        "seed": args.seed,
        "alpha": args.alpha,
        "surrogate": "Fourier-11 + quadratic ridge selected on source fit only",
        "density_ratio": (
            "quadratic logistic domain classifier with balanced class weights; "
            "regularization selected by three-fold domain-label log loss"
        ),
        "target_partition_contract": (
            "one disjoint half of each target parameter table fits the density ratio; "
            "the other half evaluates bands; target torque is not used by the ratio estimator"
        ),
        "weighted_quantile_contract": (
            "each test weight is a point mass at positive infinity; infinite bands are retained"
        ),
        "target_partitions": target_partitions,
        "input_files": input_manifest,
        "software": {
            "python": sys.version,
            "platform": platform.platform(),
            "numpy": np.__version__,
            "pandas": pd.__version__,
            "scikit_learn": sklearn.__version__,
        },
    }
    (args.results_dir / "run_metadata.json").write_text(
        json.dumps(metadata, indent=2),
        encoding="utf-8",
    )
    print(pd.DataFrame(summary_rows).to_string(index=False))


if __name__ == "__main__":
    main()
