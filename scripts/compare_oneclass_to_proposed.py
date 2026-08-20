"""Compare primary one-class baselines with the proposed method by fault record."""

from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np
import pandas as pd

from pmsm_sci.faults.oneclass import METHOD_SPECS

PROPOSED = "log_euclidean_entity_covariance"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--oneclass-dir", type=Path, default=Path("results/oneclass_baselines")
    )
    parser.add_argument(
        "--proposed-dir", type=Path, default=Path("results/healthy_covariance_v0")
    )
    parser.add_argument("--bootstrap-replicates", type=int, default=10_000)
    parser.add_argument("--seed", type=int, default=42)
    return parser.parse_args()


def record_rates(frame: pd.DataFrame) -> pd.DataFrame:
    faults = frame[~frame["is_healthy"].astype(bool)]
    return (
        faults.groupby(["target_motor", "record_id"], observed=True, sort=True)["alarm"]
        .mean()
        .rename("detection_rate")
        .reset_index()
    )


def paired_stratified_bootstrap(
    differences: pd.DataFrame, *, replicates: int, seed: int
) -> np.ndarray:
    if replicates < 100:
        raise ValueError("bootstrap-replicates must be at least 100")
    rng = np.random.default_rng(seed)
    groups = [
        group["difference"].to_numpy(dtype=np.float64)
        for _, group in differences.groupby("target_motor", sort=True)
    ]
    draws = np.empty(replicates, dtype=np.float64)
    for index in range(replicates):
        draws[index] = np.mean(
            [rng.choice(group, size=len(group), replace=True).mean() for group in groups]
        )
    return draws


def load_proposed(directory: Path) -> pd.DataFrame:
    parts = []
    for target_dir in sorted(directory.glob("target_*")):
        path = (
            target_dir
            / "scale_free"
            / "log_euclidean_entity_covariance"
            / "block_predictions.csv"
        )
        frame = pd.read_csv(path)
        frame["target_motor"] = target_dir.name.removeprefix("target_")
        parts.append(frame)
    if len(parts) != 3:
        raise ValueError("Expected proposed predictions for three target motors")
    return pd.concat(parts, ignore_index=True)


def main() -> None:
    args = parse_args()
    oneclass = pd.read_csv(args.oneclass_dir / "block_predictions.csv.gz")
    proposed = load_proposed(args.proposed_dir)
    proposed_records = record_rates(proposed).rename(
        columns={"detection_rate": "proposed_detection_rate"}
    )

    rows: list[dict[str, object]] = []
    motor_rows: list[dict[str, object]] = []
    for spec in METHOD_SPECS:
        baseline = oneclass[oneclass["method"].eq(spec.name)]
        baseline_records = record_rates(baseline).rename(
            columns={"detection_rate": "baseline_detection_rate"}
        )
        paired = proposed_records.merge(
            baseline_records,
            on=["target_motor", "record_id"],
            validate="one_to_one",
        )
        if len(paired) != 42:
            raise ValueError(f"Expected 42 paired fault records for {spec.name}")
        paired["difference"] = (
            paired["proposed_detection_rate"] - paired["baseline_detection_rate"]
        )
        draws = paired_stratified_bootstrap(
            paired,
            replicates=args.bootstrap_replicates,
            seed=args.seed,
        )
        proposed_healthy = proposed[
            proposed["is_healthy"].astype(bool)
            & proposed["block_id"].between(26, 39)
        ]
        baseline_healthy = baseline[
            baseline["is_healthy"].astype(bool)
            & baseline["block_id"].between(26, 39)
        ]
        rows.append(
            {
                "proposed": PROPOSED,
                "baseline": spec.name,
                "proposed_fault_record_macro_detection": float(
                    paired["proposed_detection_rate"].mean()
                ),
                "baseline_fault_record_macro_detection": float(
                    paired["baseline_detection_rate"].mean()
                ),
                "proposed_minus_baseline_detection": float(paired["difference"].mean()),
                "paired_record_bootstrap_ci_lower": float(np.quantile(draws, 0.025)),
                "paired_record_bootstrap_ci_upper": float(np.quantile(draws, 0.975)),
                "bootstrap_probability_proposed_better": float(np.mean(draws > 0)),
                "fault_records": len(paired),
                "proposed_false_alarms_over_42_blocks": int(
                    proposed_healthy["alarm"].sum()
                ),
                "baseline_false_alarms_over_42_blocks": int(
                    baseline_healthy["alarm"].sum()
                ),
            }
        )
        for motor, group in paired.groupby("target_motor", sort=True):
            motor_rows.append(
                {
                    "target_motor": motor,
                    "baseline": spec.name,
                    "proposed_minus_baseline_detection": float(
                        group["difference"].mean()
                    ),
                }
            )

    comparison = pd.DataFrame(rows)
    comparison.to_csv(
        args.oneclass_dir / "comparison_to_proposed.csv", index=False
    )
    pd.DataFrame(motor_rows).to_csv(
        args.oneclass_dir / "comparison_to_proposed_by_motor.csv", index=False
    )
    print(comparison.to_string(index=False))


if __name__ == "__main__":
    main()
