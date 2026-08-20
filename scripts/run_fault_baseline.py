"""Run the first LOMO source-classifier plus healthy-only calibration baseline."""

from __future__ import annotations

import argparse
import hashlib
import json
import platform
import time
from datetime import UTC, datetime
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
import sklearn
from sklearn.metrics import average_precision_score, roc_auc_score

from pmsm_sci.faults.baseline import (
    block_score_table,
    build_classifier,
    classifier_scores,
    feature_columns,
    healthy_relative_features,
    source_train_and_calibration_masks,
)
from pmsm_sci.faults.conformal import conformal_p_values, conformal_threshold
from pmsm_sci.faults.splits import leave_one_motor_out, partition_contiguous_blocks
from pmsm_sci.faults.statistics import wilson_interval


def file_sha256(path: Path, chunk_size: int = 8 * 1024 * 1024) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        while chunk := stream.read(chunk_size):
            digest.update(chunk)
    return digest.hexdigest()


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--features", type=Path, default=Path("data/processed/kaist_current_features.csv.gz")
    )
    parser.add_argument(
        "--results-dir", type=Path, default=Path("results/paper1_baseline_v0")
    )
    parser.add_argument(
        "--models",
        nargs="+",
        choices=["logistic", "hist_gbr", "random_forest"],
        default=["logistic"],
    )
    parser.add_argument(
        "--feature-arms",
        nargs="+",
        choices=["all_features", "scale_free", "healthy_relative"],
        default=["all_features", "scale_free", "healthy_relative"],
    )
    parser.add_argument("--alpha", type=float, default=0.05)
    parser.add_argument("--block-score-quantile", type=float, default=1.0)
    parser.add_argument("--seed", type=int, default=42)
    return parser.parse_args()


def target_partition(frame: pd.DataFrame, target_motor: str):
    healthy = frame[(frame["motor_id"] == target_motor) & frame["is_healthy"].astype(bool)]
    block_ids = np.sort(healthy["block_id"].astype(int).unique())
    if not np.array_equal(block_ids, np.arange(len(block_ids))):
        raise ValueError(f"Target healthy blocks are not contiguous for {target_motor}")
    return partition_contiguous_blocks(
        len(block_ids),
        adaptation_fraction=0.12,
        calibration_fraction=0.55,
        guard_blocks=1,
    )


def evaluate_one(
    frame: pd.DataFrame,
    *,
    model_name: str,
    feature_arm: str,
    source_motors: tuple[str, ...],
    target_motor: str,
    alpha: float,
    block_score_quantile: float,
    seed: int,
    output_dir: Path,
) -> dict[str, object]:
    columns = feature_columns(frame, feature_arm)
    partition = target_partition(frame, target_motor)
    if feature_arm == "healthy_relative":
        reference_blocks = {
            motor: list(range(24)) for motor in source_motors
        } | {target_motor: partition.adaptation.tolist()}
        features, reference_parameters = healthy_relative_features(
            frame, columns, reference_blocks
        )
    else:
        features = frame[columns].to_numpy(dtype=np.float64)
        reference_parameters = {}
    train_mask, source_calibration_mask = source_train_and_calibration_masks(
        frame, source_motors
    )
    model = build_classifier(model_name, seed)
    started = time.perf_counter()
    model.fit(
        features[train_mask],
        (~frame.loc[train_mask, "is_healthy"].astype(bool)).astype(int).to_numpy(),
    )
    train_seconds = time.perf_counter() - started

    source_calibration_scores = classifier_scores(
        model,
        features[source_calibration_mask],
    )
    source_calibration_blocks = block_score_table(
        frame.loc[source_calibration_mask].reset_index(drop=True),
        source_calibration_scores,
        quantile=block_score_quantile,
    )
    source_threshold = conformal_threshold(source_calibration_blocks["score"], alpha)

    target_mask = frame["motor_id"].eq(target_motor).to_numpy()
    target_frame = frame.loc[target_mask].reset_index(drop=True)
    target_features = features[target_mask]
    target_scores = classifier_scores(
        model, target_features
    )
    target_blocks = block_score_table(
        target_frame, target_scores, quantile=block_score_quantile
    )
    target_healthy = target_blocks[target_blocks["is_healthy"].astype(bool)]
    calibration = target_healthy[target_healthy["block_id"].isin(partition.calibration)]
    healthy_test = target_healthy[target_healthy["block_id"].isin(partition.test)]
    target_threshold = conformal_threshold(calibration["score"], alpha)

    target_blocks["p_source"] = conformal_p_values(
        source_calibration_blocks["score"], target_blocks["score"]
    )
    target_blocks["p_target_healthy"] = conformal_p_values(
        calibration["score"], target_blocks["score"]
    )
    target_blocks["alarm_source"] = target_blocks["p_source"] <= alpha
    target_blocks["alarm_target_healthy"] = target_blocks["p_target_healthy"] <= alpha

    healthy_test = target_blocks[
        target_blocks["is_healthy"].astype(bool)
        & target_blocks["block_id"].isin(partition.test)
    ]
    fault_test = target_blocks[~target_blocks["is_healthy"].astype(bool)]
    evaluation = pd.concat([healthy_test, fault_test], ignore_index=True)
    labels = (~evaluation["is_healthy"].astype(bool)).astype(int)

    severity = (
        fault_test.groupby(["fault_family", "severity_percent"], observed=True)
        .agg(
            blocks=("score", "size"),
            score_mean=("score", "mean"),
            source_detection=("alarm_source", "mean"),
            target_healthy_detection=("alarm_target_healthy", "mean"),
        )
        .reset_index()
    )
    output_dir.mkdir(parents=True, exist_ok=True)
    target_blocks.to_csv(output_dir / "block_predictions.csv", index=False)
    severity.to_csv(output_dir / "severity_detection.csv", index=False)
    joblib.dump(model, output_dir / "model.joblib")
    (output_dir / "healthy_reference.json").write_text(
        json.dumps(
            {"columns": columns, "parameters": reference_parameters}, indent=2
        ),
        encoding="utf-8",
    )

    summary: dict[str, object] = {
        "model": model_name,
        "feature_arm": feature_arm,
        "source_motors": list(source_motors),
        "target_motor": target_motor,
        "features": columns,
        "seed": seed,
        "alpha": alpha,
        "train_windows": int(train_mask.sum()),
        "source_calibration_blocks": len(source_calibration_blocks),
        "target_calibration_blocks": len(calibration),
        "target_healthy_test_blocks": len(healthy_test),
        "target_fault_test_blocks": len(fault_test),
        "target_adaptation_blocks": len(partition.adaptation),
        "source_threshold": source_threshold,
        "target_threshold": target_threshold,
        "source_false_alarm_rate": float(healthy_test["alarm_source"].mean()),
        "target_healthy_false_alarm_rate": float(
            healthy_test["alarm_target_healthy"].mean()
        ),
        "source_detection_rate": float(fault_test["alarm_source"].mean()),
        "target_healthy_detection_rate": float(
            fault_test["alarm_target_healthy"].mean()
        ),
        "source_false_alarms": int(healthy_test["alarm_source"].sum()),
        "target_healthy_false_alarms": int(
            healthy_test["alarm_target_healthy"].sum()
        ),
        "source_detected_fault_blocks": int(fault_test["alarm_source"].sum()),
        "target_healthy_detected_fault_blocks": int(
            fault_test["alarm_target_healthy"].sum()
        ),
        "block_auroc": float(roc_auc_score(labels, evaluation["score"])),
        "block_auprc": float(average_precision_score(labels, evaluation["score"])),
        "train_seconds": train_seconds,
    }
    (output_dir / "summary.json").write_text(
        json.dumps(summary, indent=2), encoding="utf-8"
    )
    return summary


def main() -> None:
    args = parse_args()
    frame = pd.read_csv(args.features)
    required = {"motor_id", "record_id", "is_healthy", "block_id", "severity_percent"}
    missing = sorted(required - set(frame.columns))
    if missing:
        raise ValueError(f"Feature table is missing columns: {missing}")
    args.results_dir.mkdir(parents=True, exist_ok=True)

    summaries: list[dict[str, object]] = []
    for fold in leave_one_motor_out():
        for model_name in args.models:
            for feature_arm in args.feature_arms:
                output_dir = args.results_dir / fold.fold_id / model_name / feature_arm
                summary = evaluate_one(
                    frame,
                    model_name=model_name,
                    feature_arm=feature_arm,
                    source_motors=fold.source_motors,
                    target_motor=fold.target_motor,
                    alpha=args.alpha,
                    block_score_quantile=args.block_score_quantile,
                    seed=args.seed,
                    output_dir=output_dir,
                )
                summaries.append(summary)
                print(
                    f"{fold.fold_id} {model_name} {feature_arm}: "
                    f"FAR {summary['target_healthy_false_alarm_rate']:.3f}, "
                    f"detection {summary['target_healthy_detection_rate']:.3f}, "
                    f"AUROC {summary['block_auroc']:.3f}"
                )

    pd.DataFrame(summaries).drop(columns="features").to_csv(
        args.results_dir / "summary.csv", index=False
    )
    summary_frame = pd.DataFrame(summaries)
    aggregate_rows: list[dict[str, object]] = []
    for (model_name, feature_arm), group in summary_frame.groupby(
        ["model", "feature_arm"], sort=True
    ):
        healthy_blocks = int(group["target_healthy_test_blocks"].sum())
        false_alarms = int(group["target_healthy_false_alarms"].sum())
        lower, upper = wilson_interval(false_alarms, healthy_blocks)
        aggregate_rows.append(
            {
                "model": model_name,
                "feature_arm": feature_arm,
                "healthy_test_blocks": healthy_blocks,
                "false_alarms": false_alarms,
                "pooled_false_alarm_rate": false_alarms / healthy_blocks,
                "pooled_far_wilson_lower": lower,
                "pooled_far_wilson_upper": upper,
                "max_motor_false_alarm_rate": float(
                    group["target_healthy_false_alarm_rate"].max()
                ),
                "h1_empirical_pass": bool(
                    upper <= 0.12
                    and group["target_healthy_false_alarm_rate"].max() <= 0.15
                ),
                "mean_detection_rate": float(
                    group["target_healthy_detection_rate"].mean()
                ),
                "mean_block_auroc": float(group["block_auroc"].mean()),
            }
        )
    pd.DataFrame(aggregate_rows).to_csv(
        args.results_dir / "aggregate_summary.csv", index=False
    )
    metadata = {
        "created_utc": datetime.now(UTC).isoformat(),
        "features_path": str(args.features.resolve()),
        "features_sha256": file_sha256(args.features),
        "python": platform.python_version(),
        "scikit_learn": sklearn.__version__,
        "rows": len(frame),
        "models": args.models,
        "feature_arms": args.feature_arms,
    }
    (args.results_dir / "run_metadata.json").write_text(
        json.dumps(metadata, indent=2), encoding="utf-8"
    )


if __name__ == "__main__":
    main()
