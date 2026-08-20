"""Select the log-covariance ridge using source motors only within each outer fold."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
import pandas as pd

from pmsm_sci.faults.baseline import (
    block_score_table,
    feature_columns,
    healthy_relative_features,
)
from pmsm_sci.faults.conformal import conformal_threshold
from pmsm_sci.faults.covariance import (
    log_euclidean_entity_covariance,
    mahalanobis_scores,
    sample_covariance,
)
from pmsm_sci.faults.splits import leave_one_motor_out, partition_contiguous_blocks


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--features", type=Path, default=Path("data/processed/kaist_current_features.csv.gz")
    )
    parser.add_argument(
        "--results-dir", type=Path, default=Path("results/log_ridge_selection")
    )
    parser.add_argument(
        "--ridge-grid", nargs="+", type=float, default=[1e-4, 1e-3, 1e-2, 1e-1]
    )
    parser.add_argument("--alpha", type=float, default=0.05)
    return parser.parse_args()


def split():
    return partition_contiguous_blocks(
        40,
        adaptation_fraction=0.12,
        calibration_fraction=0.55,
        guard_blocks=1,
    )


def pseudo_target_metrics(
    frame: pd.DataFrame,
    *,
    pseudo_target: str,
    pseudo_source: str,
    ridge_fraction: float,
    alpha: float,
) -> tuple[float, float]:
    data = frame[frame["motor_id"].isin([pseudo_target, pseudo_source])].reset_index(
        drop=True
    )
    blocks = split()
    columns = feature_columns(data, "scale_free")
    values, _ = healthy_relative_features(
        data,
        columns,
        {pseudo_target: blocks.adaptation.tolist(), pseudo_source: list(range(24))},
    )
    covariances: list[np.ndarray] = []
    for motor in (pseudo_target, pseudo_source):
        reference_blocks = blocks.adaptation if motor == pseudo_target else range(24)
        reference = (
            data["motor_id"].eq(motor)
            & data["is_healthy"].astype(bool)
            & data["block_id"].isin(reference_blocks)
        ).to_numpy()
        covariances.append(sample_covariance(values[reference]))
    covariance = log_euclidean_entity_covariance(covariances, ridge_fraction)

    target = data["motor_id"].eq(pseudo_target).to_numpy()
    target_frame = data.loc[target].reset_index(drop=True)
    scores = mahalanobis_scores(
        values[target], covariance, np.zeros(len(columns), dtype=np.float64)
    )
    table = block_score_table(target_frame, scores)
    healthy = table[table["is_healthy"].astype(bool)]
    calibration = healthy[healthy["block_id"].isin(blocks.calibration)]
    healthy_test = healthy[healthy["block_id"].isin(blocks.test)]
    faults = table[~table["is_healthy"].astype(bool)]
    threshold = conformal_threshold(calibration["score"], alpha)
    return float((healthy_test["score"] > threshold).mean()), float(
        (faults["score"] > threshold).mean()
    )


def main() -> None:
    args = parse_args()
    frame = pd.read_csv(args.features)
    args.results_dir.mkdir(parents=True, exist_ok=True)
    rows: list[dict[str, object]] = []
    selected: dict[str, float] = {}
    for fold in leave_one_motor_out():
        fold_rows: list[dict[str, object]] = []
        first, second = fold.source_motors
        for ridge in args.ridge_grid:
            metrics = [
                pseudo_target_metrics(
                    frame,
                    pseudo_target=first,
                    pseudo_source=second,
                    ridge_fraction=ridge,
                    alpha=args.alpha,
                ),
                pseudo_target_metrics(
                    frame,
                    pseudo_target=second,
                    pseudo_source=first,
                    ridge_fraction=ridge,
                    alpha=args.alpha,
                ),
            ]
            mean_far = float(np.mean([item[0] for item in metrics]))
            mean_detection = float(np.mean([item[1] for item in metrics]))
            row: dict[str, object] = {
                "outer_target": fold.target_motor,
                "ridge_fraction": ridge,
                "mean_source_validation_far": mean_far,
                "mean_source_validation_detection": mean_detection,
                "selection_objective": mean_detection - 2 * mean_far,
            }
            rows.append(row)
            fold_rows.append(row)
        winner = max(
            fold_rows,
            key=lambda row: (float(row["selection_objective"]), -float(row["ridge_fraction"])),
        )
        selected[fold.target_motor] = float(winner["ridge_fraction"])
        print(f"outer target {fold.target_motor}: selected {winner['ridge_fraction']}")

    pd.DataFrame(rows).to_csv(args.results_dir / "ridge_selection.csv", index=False)
    (args.results_dir / "selected_ridge.json").write_text(
        json.dumps(selected, indent=2), encoding="utf-8"
    )


if __name__ == "__main__":
    main()
