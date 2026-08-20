"""Command-line entry point for the first leakage-free baseline experiment."""

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

from .constants import GROUP_COLUMN, TARGETS
from .data import discover_dataset, downsample_profiles, load_dataset
from .features import add_physics_features, feature_columns
from .metrics import per_profile_rmse, regression_metrics
from .models import build_model
from .splits import make_grouped_split, split_manifest


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data-dir", type=Path, default=Path("data/raw"))
    parser.add_argument("--results-dir", type=Path, default=Path("results/baseline_v0"))
    parser.add_argument("--stride", type=int, default=20)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument(
        "--models",
        nargs="+",
        default=["dummy", "ridge", "hist_gbr"],
        choices=["dummy", "ridge", "hist_gbr"],
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    dataset_path = discover_dataset(args.data_dir)
    frame = downsample_profiles(load_dataset(dataset_path), args.stride)
    frame = add_physics_features(frame)
    split = make_grouped_split(frame[GROUP_COLUMN], seed=args.seed)

    args.results_dir.mkdir(parents=True, exist_ok=True)
    split_manifest(frame[GROUP_COLUMN], split).to_csv(
        args.results_dir / "split_manifest.csv", index=False
    )

    run_metadata = {
        "created_utc": datetime.now(UTC).isoformat(),
        "dataset": str(dataset_path.resolve()),
        "rows_after_downsampling": len(frame),
        "stride": args.stride,
        "seed": args.seed,
        "python": sys.version,
        "platform": platform.platform(),
        "numpy": np.__version__,
        "pandas": pd.__version__,
        "scikit_learn": sklearn.__version__,
    }
    (args.results_dir / "run_metadata.json").write_text(
        json.dumps(run_metadata, indent=2, ensure_ascii=False), encoding="utf-8"
    )

    all_metrics: dict[str, object] = {}
    for use_physics in (False, True):
        features = feature_columns(use_physics)
        arm = "physics_features" if use_physics else "base_features"
        x = frame[features].to_numpy(dtype=np.float64)
        y = frame[TARGETS].to_numpy(dtype=np.float64)

        for model_name in args.models:
            key = f"{model_name}__{arm}"
            model = build_model(model_name, seed=args.seed)
            started = time.perf_counter()
            model.fit(x[split.train], y[split.train])
            train_seconds = time.perf_counter() - started

            started = time.perf_counter()
            prediction = model.predict(x[split.test])
            inference_seconds = time.perf_counter() - started
            metrics = regression_metrics(y[split.test], prediction, TARGETS)
            profile_metrics = per_profile_rmse(
                y[split.test],
                prediction,
                frame[GROUP_COLUMN].iloc[split.test].reset_index(drop=True),
                TARGETS,
            )
            profile_metrics.to_csv(args.results_dir / f"per_profile__{key}.csv", index=False)
            all_metrics[key] = {
                "features": features,
                "train_seconds": train_seconds,
                "inference_seconds": inference_seconds,
                "metrics": metrics,
                "worst_profile_rmse_macro": float(profile_metrics["rmse_macro"].max()),
                "p90_profile_rmse_macro": float(profile_metrics["rmse_macro"].quantile(0.9)),
            }
            print(
                f"{key}: macro RMSE={metrics['macro']['rmse']:.4f}, "
                f"worst-profile RMSE={profile_metrics['rmse_macro'].max():.4f}"
            )

    (args.results_dir / "metrics.json").write_text(
        json.dumps(all_metrics, indent=2, ensure_ascii=False), encoding="utf-8"
    )


if __name__ == "__main__":
    main()
