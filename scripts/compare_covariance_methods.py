"""Paired record-level bootstrap comparisons for healthy-covariance methods."""

from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np
import pandas as pd

PROPOSED = "log_euclidean_entity_covariance"
COMPARATORS = (
    "target_ledoit",
    "target_sample_covariance",
    "source_covariance",
    "entity_balanced_covariance",
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--results-dir", type=Path, default=Path("results/healthy_covariance_v0")
    )
    parser.add_argument("--bootstrap-replicates", type=int, default=10_000)
    parser.add_argument("--seed", type=int, default=42)
    return parser.parse_args()


def load_record_detection(results_dir: Path) -> pd.DataFrame:
    rows: list[dict[str, object]] = []
    methods = (PROPOSED, *COMPARATORS)
    for target_dir in sorted(results_dir.glob("target_*")):
        target_motor = target_dir.name.removeprefix("target_")
        for method in methods:
            path = target_dir / "scale_free" / method / "block_predictions.csv"
            frame = pd.read_csv(path)
            faults = frame[~frame["is_healthy"].astype(bool)]
            for record_id, record in faults.groupby("record_id", observed=True):
                rows.append(
                    {
                        "target_motor": target_motor,
                        "record_id": record_id,
                        "method": method,
                        "detection_rate": float(record["alarm"].mean()),
                    }
                )
    result = pd.DataFrame(rows)
    expected = 3 * 14 * len(methods)
    if len(result) != expected:
        raise ValueError(f"Expected {expected} motor-record-method rows, found {len(result)}")
    return result


def stratified_record_bootstrap(
    differences: pd.DataFrame, *, replicates: int, seed: int
) -> np.ndarray:
    rng = np.random.default_rng(seed)
    by_motor = [
        group["difference"].to_numpy(dtype=np.float64)
        for _, group in differences.groupby("target_motor", sort=True)
    ]
    draws = np.empty(replicates, dtype=np.float64)
    for index in range(replicates):
        motor_means = [rng.choice(values, size=len(values), replace=True).mean() for values in by_motor]
        draws[index] = np.mean(motor_means)
    return draws


def main() -> None:
    args = parse_args()
    detection = load_record_detection(args.results_dir)
    wide = detection.pivot(
        index=["target_motor", "record_id"], columns="method", values="detection_rate"
    ).reset_index()
    comparison_rows: list[dict[str, object]] = []
    per_motor_rows: list[dict[str, object]] = []
    for comparator in COMPARATORS:
        differences = wide[["target_motor", "record_id"]].copy()
        differences["difference"] = wide[PROPOSED] - wide[comparator]
        draws = stratified_record_bootstrap(
            differences,
            replicates=args.bootstrap_replicates,
            seed=args.seed,
        )
        comparison_rows.append(
            {
                "proposed": PROPOSED,
                "comparator": comparator,
                "mean_detection_difference": float(differences["difference"].mean()),
                "bootstrap_ci_lower": float(np.quantile(draws, 0.025)),
                "bootstrap_ci_upper": float(np.quantile(draws, 0.975)),
                "bootstrap_probability_positive": float(np.mean(draws > 0)),
                "records": len(differences),
            }
        )
        for motor, group in differences.groupby("target_motor", sort=True):
            per_motor_rows.append(
                {
                    "target_motor": motor,
                    "comparator": comparator,
                    "mean_detection_difference": float(group["difference"].mean()),
                }
            )

    pd.DataFrame(comparison_rows).to_csv(
        args.results_dir / "paired_record_bootstrap.csv", index=False
    )
    pd.DataFrame(per_motor_rows).to_csv(
        args.results_dir / "paired_record_differences_by_motor.csv", index=False
    )
    print(pd.DataFrame(comparison_rows).to_string(index=False))


if __name__ == "__main__":
    main()
