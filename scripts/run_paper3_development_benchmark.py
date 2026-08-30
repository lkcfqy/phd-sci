"""Run the fault-blind-fit Paper 3 development benchmark across held-out loads."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
from dataclasses import asdict
from datetime import UTC, datetime
from pathlib import Path

import numpy as np
import pandas as pd
from numpy.typing import NDArray
from sklearn.metrics import average_precision_score, roc_auc_score

from pmsm_sci.faults.conditional import ContextSupportModel
from pmsm_sci.faults.conformal import conformal_p_values, conformal_threshold
from pmsm_sci.faults.paper3 import (
    PAPER3_CONTEXT_FEATURES,
    PAPER3_LOADS_NM,
    PAPER3_METHODS,
    PAPER3_OUTCOME_FEATURES,
    Paper3MethodSpec,
    aggregate_paper3_system_blocks,
    array_columns,
    paper3_load_roles,
)
from pmsm_sci.faults.paper3_modeling import paper3_detector_scores
from pmsm_sci.faults.statistics import wilson_interval

ALPHA = 0.05
SEED = 711
SELECTION_MAX_HEALTH_BLOCK_FAR = 0.05
SELECTION_MAX_FAULT_ABSTENTION = 0.20
PRIMARY_INTERPOLATION_LOADS_NM = (5.0, 10.0, 15.0, 20.0, 25.0, 30.0)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--features",
        type=Path,
        default=Path("data/processed/paper3_development_features.csv.gz"),
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("results/paper3_development"),
    )
    return parser.parse_args()


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        while chunk := stream.read(8 * 1024 * 1024):
            digest.update(chunk)
    return digest.hexdigest()


def detector_scores(
    spec: Paper3MethodSpec,
    fit_frame: pd.DataFrame,
    score_frame: pd.DataFrame,
    *,
    seed: int,
) -> NDArray[np.float64]:
    return paper3_detector_scores(
        spec,
        fit_context=array_columns(fit_frame, PAPER3_CONTEXT_FEATURES),
        fit_outcomes=array_columns(fit_frame, PAPER3_OUTCOME_FEATURES),
        fit_groups=fit_frame["record_id"].to_numpy(),
        score_context=array_columns(score_frame, PAPER3_CONTEXT_FEATURES),
        score_outcomes=array_columns(score_frame, PAPER3_OUTCOME_FEATURES),
        seed=seed,
    )


def validate_input(frame: pd.DataFrame) -> None:
    required = {
        "record_id",
        "subsystem",
        "load_nm",
        "fault_turns",
        "fault_phase",
        "is_healthy",
        "block_id",
        "window_id",
        *PAPER3_CONTEXT_FEATURES,
        *PAPER3_OUTCOME_FEATURES,
    }
    missing = required.difference(frame.columns)
    if missing:
        raise ValueError(f"Development table lacks required columns: {sorted(missing)}")
    if len(frame) != 13_440 or frame["record_id"].nunique() != 56:
        raise ValueError("Expected exactly 56 physical records and 13,440 feature rows")
    healthy = frame[frame["is_healthy"].astype(bool)]
    faults = frame[~frame["is_healthy"].astype(bool)]
    if healthy["record_id"].nunique() != 8 or faults["record_id"].nunique() != 48:
        raise ValueError("Expected 8 healthy and 48 fault records")
    if tuple(sorted(frame["load_nm"].unique())) != PAPER3_LOADS_NM:
        raise ValueError("Development loads differ from the frozen eight-load grid")
    counts = frame.groupby(["record_id", "subsystem"], observed=True).agg(
        windows=("window_id", "nunique"), blocks=("block_id", "nunique")
    )
    if not (counts["windows"].eq(120) & counts["blocks"].eq(8)).all():
        raise ValueError("Each record/subsystem must contain 120 windows and 8 blocks")


def summarize_fold(
    method: str,
    test_load_nm: float,
    blocks: pd.DataFrame,
    threshold: float,
) -> dict[str, object]:
    health = blocks[blocks["role"].eq("health_test")]
    fault = blocks[blocks["role"].eq("fault_test")]
    if len(health) != 8 or len(fault) != 48:
        raise AssertionError("Each fold must expose 8 healthy and 48 fault test blocks")
    supported_faults = fault[fault["supported"]]
    record_rates = fault.groupby("record_id", sort=True).agg(
        actionable_detection=("actionable_alarm", "mean"),
        raw_detection=("alarm", "mean"),
        abstention=("supported", lambda values: 1.0 - values.mean()),
        any_actionable_alarm=("actionable_alarm", "any"),
    )
    labels = np.concatenate([np.zeros(len(health)), np.ones(len(fault))])
    scores = np.concatenate([health["score"].to_numpy(), fault["score"].to_numpy()])
    return {
        "method": method,
        "test_load_nm": test_load_nm,
        "threshold": threshold,
        "health_blocks": len(health),
        "health_alarms": int(health["alarm"].sum()),
        "health_actionable_alarms": int(health["actionable_alarm"].sum()),
        "health_abstentions": int((~health["supported"]).sum()),
        "health_block_raw_far": float(health["alarm"].mean()),
        "health_block_actionable_far": float(health["actionable_alarm"].mean()),
        "health_block_abstention": float((~health["supported"]).mean()),
        "fault_blocks": len(fault),
        "fault_supported_blocks": len(supported_faults),
        "fault_raw_detection": float(fault["alarm"].mean()),
        "fault_actionable_detection": float(fault["actionable_alarm"].mean()),
        "fault_supported_detection": (
            float(supported_faults["alarm"].mean()) if len(supported_faults) else math.nan
        ),
        "fault_abstention": float((~fault["supported"]).mean()),
        "record_macro_raw_detection": float(record_rates["raw_detection"].mean()),
        "record_macro_actionable_detection": float(
            record_rates["actionable_detection"].mean()
        ),
        "record_any_actionable_detection": float(
            record_rates["any_actionable_alarm"].mean()
        ),
        "auroc": float(roc_auc_score(labels, scores)),
        "auprc": float(average_precision_score(labels, scores)),
    }


def aggregate_methods(blocks: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, object]] = []
    for method, method_blocks in blocks.groupby("method", sort=False):
        health = method_blocks[method_blocks["role"].eq("health_test")]
        fault = method_blocks[method_blocks["role"].eq("fault_test")]
        primary_health = health[
            health["test_load_nm"].isin(PRIMARY_INTERPOLATION_LOADS_NM)
        ]
        primary_fault = fault[
            fault["test_load_nm"].isin(PRIMARY_INTERPOLATION_LOADS_NM)
        ]
        if len(health) != 64 or len(fault) != 384:
            raise AssertionError("Aggregate output must contain 64 health/384 fault blocks")
        supported_fault = fault[fault["supported"]]
        primary_supported_fault = primary_fault[primary_fault["supported"]]
        records = fault.groupby(
            ["record_id", "load_nm", "fault_turns", "fault_phase"],
            dropna=False,
            sort=True,
        ).agg(
            actionable_detection=("actionable_alarm", "mean"),
            raw_detection=("alarm", "mean"),
            any_actionable_alarm=("actionable_alarm", "any"),
        )
        primary_records = primary_fault.groupby(
            ["record_id", "load_nm", "fault_turns", "fault_phase"],
            dropna=False,
            sort=True,
        ).agg(
            actionable_detection=("actionable_alarm", "mean"),
            raw_detection=("alarm", "mean"),
            any_actionable_alarm=("actionable_alarm", "any"),
        )
        labels = np.concatenate([np.zeros(len(health)), np.ones(len(fault))])
        score_values = np.concatenate(
            [health["score"].to_numpy(), fault["score"].to_numpy()]
        )
        far_lower, far_upper = wilson_interval(
            int(health["actionable_alarm"].sum()), len(health)
        )
        rows.append(
            {
                "method": method,
                "health_blocks": len(health),
                "health_actionable_alarms": int(health["actionable_alarm"].sum()),
                "health_block_actionable_far": float(health["actionable_alarm"].mean()),
                "health_far_wilson_lower": far_lower,
                "health_far_wilson_upper": far_upper,
                "health_block_abstention": float((~health["supported"]).mean()),
                "healthy_records_with_any_actionable_alarm": int(
                    health.groupby("record_id")["actionable_alarm"].any().sum()
                ),
                "primary_health_blocks": len(primary_health),
                "primary_health_actionable_alarms": int(
                    primary_health["actionable_alarm"].sum()
                ),
                "primary_health_block_actionable_far": float(
                    primary_health["actionable_alarm"].mean()
                ),
                "primary_health_block_abstention": float(
                    (~primary_health["supported"]).mean()
                ),
                "fault_blocks": len(fault),
                "fault_actionable_detection": float(fault["actionable_alarm"].mean()),
                "fault_supported_detection": (
                    float(supported_fault["alarm"].mean())
                    if len(supported_fault)
                    else math.nan
                ),
                "fault_abstention": float((~fault["supported"]).mean()),
                "primary_fault_blocks": len(primary_fault),
                "primary_fault_actionable_detection": float(
                    primary_fault["actionable_alarm"].mean()
                ),
                "primary_fault_supported_detection": (
                    float(primary_supported_fault["alarm"].mean())
                    if len(primary_supported_fault)
                    else math.nan
                ),
                "primary_fault_abstention": float(
                    (~primary_fault["supported"]).mean()
                ),
                "fault_records": len(records),
                "record_macro_actionable_detection": float(
                    records["actionable_detection"].mean()
                ),
                "record_macro_raw_detection": float(records["raw_detection"].mean()),
                "record_any_actionable_detection": float(
                    records["any_actionable_alarm"].mean()
                ),
                "primary_fault_records": len(primary_records),
                "primary_record_macro_actionable_detection": float(
                    primary_records["actionable_detection"].mean()
                ),
                "primary_record_any_actionable_detection": float(
                    primary_records["any_actionable_alarm"].mean()
                ),
                "auroc": float(roc_auc_score(labels, score_values)),
                "auprc": float(average_precision_score(labels, score_values)),
            }
        )
    result = pd.DataFrame(rows)
    method_order = {spec.name: index for index, spec in enumerate(PAPER3_METHODS)}
    result["selection_eligible"] = (
        result["primary_health_block_actionable_far"].le(
            SELECTION_MAX_HEALTH_BLOCK_FAR
        )
        & result["primary_fault_abstention"].le(SELECTION_MAX_FAULT_ABSTENTION)
    )
    result["method_order"] = result["method"].map(method_order)
    result = (
        result.sort_values("method_order")
        .drop(columns="method_order")
        .reset_index(drop=True)
    )
    return result


def select_method(summary: pd.DataFrame) -> pd.Series:
    eligible = summary[summary["selection_eligible"]].copy()
    if eligible.empty:
        raise RuntimeError("No development method met the predeclared FAR/abstention guardrails")
    method_order = {spec.name: index for index, spec in enumerate(PAPER3_METHODS)}
    eligible["method_order"] = eligible["method"].map(method_order)
    ranked = eligible.sort_values(
        [
            "primary_record_macro_actionable_detection",
            "primary_health_block_actionable_far",
            "primary_fault_abstention",
            "method_order",
        ],
        ascending=[False, True, True, True],
    )
    return ranked.iloc[0]


def main() -> None:
    args = parse_args()
    frame = pd.read_csv(args.features)
    validate_input(frame)
    output_blocks: list[pd.DataFrame] = []
    fold_rows: list[dict[str, object]] = []
    fold_assignments: list[dict[str, object]] = []

    for fold_index, test_load in enumerate(PAPER3_LOADS_NM):
        roles = paper3_load_roles(test_load)
        fit_loads = [load for load, role in roles.items() if role == "fit"]
        calibration_loads = [
            load for load, role in roles.items() if role == "calibration"
        ]
        fold_assignments.extend(
            {
                "fold_index": fold_index,
                "test_load_nm": test_load,
                "load_nm": load,
                "role": role,
            }
            for load, role in roles.items()
        )
        healthy = frame["is_healthy"].astype(bool)
        fit_mask = healthy & frame["load_nm"].isin(fit_loads)
        calibration_mask = healthy & frame["load_nm"].isin(calibration_loads)
        test_mask = frame["load_nm"].eq(test_load)
        score_mask = calibration_mask | test_mask
        reference_subsystem = frame["subsystem"].eq("SubSys1")
        support = ContextSupportModel(
            radius_multiplier=1.1,
            require_axis_bounds=True,
        ).fit(
            array_columns(frame[fit_mask & reference_subsystem], PAPER3_CONTEXT_FEATURES),
            array_columns(
                frame[calibration_mask & reference_subsystem], PAPER3_CONTEXT_FEATURES
            ),
        )

        for method_index, spec in enumerate(PAPER3_METHODS):
            scored_parts: list[pd.DataFrame] = []
            score_parts: list[NDArray[np.float64]] = []
            support_parts: list[NDArray[np.bool_]] = []
            for subsystem_index, subsystem in enumerate(("SubSys1", "SubSys2")):
                subsystem_mask = frame["subsystem"].eq(subsystem)
                fit_frame = frame[fit_mask & subsystem_mask]
                scored_frame = frame[score_mask & subsystem_mask].copy()
                score_values = detector_scores(
                    spec,
                    fit_frame,
                    scored_frame,
                    seed=SEED + 100 * fold_index + 10 * method_index + subsystem_index,
                )
                support_values = support.evaluate(
                    array_columns(scored_frame, PAPER3_CONTEXT_FEATURES)
                ).supported
                scored_parts.append(scored_frame)
                score_parts.append(score_values)
                support_parts.append(support_values)
            scored_frame = pd.concat(scored_parts, ignore_index=True)
            score_values = np.concatenate(score_parts)
            support_values = np.concatenate(support_parts)
            blocks = aggregate_paper3_system_blocks(
                scored_frame, score_values, support_values
            )
            blocks["role"] = np.where(
                blocks["is_healthy"].astype(bool),
                np.where(
                    blocks["load_nm"].isin(calibration_loads),
                    "calibration",
                    "health_test",
                ),
                "fault_test",
            )
            calibration = blocks[blocks["role"].eq("calibration")]
            if len(calibration) != 24:
                raise AssertionError("Every fold requires 24 calibration blocks")
            threshold = conformal_threshold(calibration["score"], ALPHA)
            if not np.isfinite(threshold):
                raise AssertionError("Twenty-four calibration blocks must resolve alpha=.05")
            blocks["p_value"] = np.nan
            test_rows = ~blocks["role"].eq("calibration")
            blocks.loc[test_rows, "p_value"] = conformal_p_values(
                calibration["score"], blocks.loc[test_rows, "score"]
            )
            blocks["alarm"] = blocks["p_value"].le(ALPHA).fillna(False)
            blocks["actionable_alarm"] = blocks["alarm"] & blocks["supported"]
            blocks["method"] = spec.name
            blocks["fold_index"] = fold_index
            blocks["test_load_nm"] = test_load
            blocks["threshold"] = threshold
            output_blocks.append(blocks)
            fold_rows.append(summarize_fold(spec.name, test_load, blocks, threshold))
            print(
                f"fold={fold_index + 1}/8 load={test_load:g} method={spec.name}: "
                f"FAR={fold_rows[-1]['health_block_actionable_far']:.3f}, "
                f"detection={fold_rows[-1]['record_macro_actionable_detection']:.3f}, "
                f"abstain={fold_rows[-1]['fault_abstention']:.3f}"
            )

    block_table = pd.concat(output_blocks, ignore_index=True)
    fold_summary = pd.DataFrame(fold_rows)
    aggregate = aggregate_methods(block_table)
    selected = select_method(aggregate)

    args.output_dir.mkdir(parents=True, exist_ok=True)
    block_table.to_csv(args.output_dir / "per_block_results.csv", index=False)
    fold_summary.to_csv(args.output_dir / "per_fold_summary.csv", index=False)
    aggregate.to_csv(args.output_dir / "aggregate_summary.csv", index=False)
    pd.DataFrame(fold_assignments).to_csv(
        args.output_dir / "fold_assignments.csv", index=False
    )
    selected_spec = next(spec for spec in PAPER3_METHODS if spec.name == selected["method"])
    selection_payload = {
        "selected_method": selected["method"],
        "selected_spec": asdict(selected_spec),
        "selection_rule": {
            "eligibility": (
                "on interpolation loads only: "
                f"health_block_actionable_far <= {SELECTION_MAX_HEALTH_BLOCK_FAR} "
                f"and fault_abstention <= {SELECTION_MAX_FAULT_ABSTENTION}"
            ),
            "objective": "maximize primary_record_macro_actionable_detection",
            "tie_breaks": [
                "lower health_block_actionable_far",
                "lower fault_abstention",
                "earlier frozen method order",
            ],
        },
        "selected_development_metrics": {
            key: (bool(value) if isinstance(value, np.bool_) else value.item() if hasattr(value, "item") else value)
            for key, value in selected.items()
            if key not in {"method", "method_order"}
        },
        "warning": (
            "Development fault labels selected the method. The independent PMSG bench "
            "must be parsed only after this method and its confirmation protocol are frozen."
        ),
    }
    (args.output_dir / "selected_method.json").write_text(
        json.dumps(selection_payload, indent=2, allow_nan=False), encoding="utf-8"
    )
    protocol = {
        "created_utc": datetime.now(UTC).isoformat(),
        "input": str(args.features.resolve()),
        "input_sha256": sha256(args.features),
        "alpha": ALPHA,
        "seed": SEED,
        "unit": "non-overlapping 3 s physical-record block after subsystem/window maxima",
        "folds": 8,
        "per_fold": {
            "healthy_fit_loads": 4,
            "healthy_calibration_loads": 3,
            "heldout_test_loads": 1,
            "calibration_blocks": 24,
            "healthy_test_blocks": 8,
            "fault_test_records": 6,
            "fault_test_blocks": 48,
        },
        "fit_uses_fault_labels": False,
        "calibration_uses_fault_labels": False,
        "development_selection_uses_fault_labels": True,
        "context_features": list(PAPER3_CONTEXT_FEATURES),
        "outcome_features": list(PAPER3_OUTCOME_FEATURES),
        "methods": [asdict(spec) for spec in PAPER3_METHODS],
        "support_rule": (
            "robust-normalized nearest healthy-fit context; radius=max distance of "
            "disjoint healthy calibration windows times 1.1; context must also remain "
            "inside every fit-axis range; block supported only if all windows of both "
            "subsystems are supported"
        ),
        "primary_interpolation_loads_nm": list(PRIMARY_INTERPOLATION_LOADS_NM),
        "edge_extrapolation_stress_loads_nm": [0.0, 35.0],
        "support_is_conformal": False,
        "calibration_note": (
            "Blocks are non-overlapping but come from one healthy record per load; Wilson "
            "intervals are descriptive and do not establish independent replication."
        ),
    }
    (args.output_dir / "protocol.json").write_text(
        json.dumps(protocol, indent=2), encoding="utf-8"
    )
    print("\nAggregate development results:")
    print(
        aggregate[
            [
                "method",
                "primary_health_block_actionable_far",
                "primary_fault_abstention",
                "primary_record_macro_actionable_detection",
                "fault_abstention",
                "auroc",
                "selection_eligible",
            ]
        ].to_string(index=False)
    )
    print(f"\nSelected and now frozen for confirmation: {selected['method']}")
    print(f"wrote results to {args.output_dir.resolve()}")


if __name__ == "__main__":
    main()
