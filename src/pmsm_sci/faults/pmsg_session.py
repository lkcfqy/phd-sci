"""PMSG-specific construction of the frozen two-window session residual table."""

from __future__ import annotations

import numpy as np
import pandas as pd

from pmsm_sci.faults.paper3 import PAPER3_OUTCOME_FEATURES
from pmsm_sci.faults.session_anchor import session_residuals


def pmsg_session_residual_table(
    frame: pd.DataFrame,
    *,
    expected_roles: dict[str, int] | None = None,
) -> pd.DataFrame:
    """Anchor exactly two healthy windows and return later within-session residuals."""

    rows: list[pd.DataFrame] = []
    for record_id, record in frame.groupby("record_id", sort=True):
        is_health = bool(record["is_healthy_file"].iloc[0])
        if is_health:
            ordered = record[record["segment"].eq("health_analysis")].sort_values(
                "segment_window_id"
            )
            if len(ordered) != 13:
                raise AssertionError(f"Healthy record {record_id} must have 13 windows")
            anchor = ordered.iloc[:2]
            scored = ordered.iloc[2:].copy()
            scored["evaluation_role"] = scored["standalone_role"]
        else:
            pre = record[record["segment"].eq("pre_fault")].sort_values(
                "segment_window_id"
            )
            if len(pre) != 3:
                raise AssertionError(f"Fault record {record_id} must have 3 pre windows")
            anchor = pre.iloc[:2]
            scored = pd.concat(
                [
                    pre.iloc[2:].assign(evaluation_role="pre_fault_test"),
                    record[record["segment"].eq("fault_active")].assign(
                        evaluation_role="fault_test"
                    ),
                    record[record["segment"].eq("recovery")].assign(
                        evaluation_role="recovery"
                    ),
                ],
                ignore_index=True,
            )
        anchor_values = anchor[list(PAPER3_OUTCOME_FEATURES)].to_numpy(dtype=np.float64)
        score_values = scored[list(PAPER3_OUTCOME_FEATURES)].to_numpy(dtype=np.float64)
        residual = session_residuals(anchor_values, score_values)
        residual_frame = pd.DataFrame(
            residual,
            columns=[f"residual__{column}" for column in PAPER3_OUTCOME_FEATURES],
            index=scored.index,
        )
        scored = pd.concat([scored, residual_frame], axis=1)
        scored["anchor_start_time_s"] = float(anchor["start_time_s"].min())
        scored["anchor_stop_time_s"] = float(anchor["stop_time_s"].max())
        rows.append(scored)
    result = pd.concat(rows, ignore_index=True)
    if expected_roles is None:
        expected_roles = {
            "fit": 44,
            "calibration": 33,
            "standalone_health_test": 22,
            "pre_fault_test": 216,
            "fault_test": 432,
            "recovery": 1_296,
        }
    if result["evaluation_role"].value_counts().to_dict() != expected_roles:
        raise AssertionError("Session-anchor role counts differ from the frozen protocol")
    return result


def pmsg_topology_assignments(residuals: pd.DataFrame) -> pd.DataFrame:
    """Assign 24 lexically sorted fault topologies to three balanced buckets."""

    fault = residuals[residuals["evaluation_role"].eq("fault_test")]
    cases = (
        fault[["fault_family", "terminal_a", "terminal_b"]]
        .drop_duplicates()
        .sort_values(["fault_family", "terminal_a", "terminal_b"])
        .reset_index(drop=True)
    )
    if len(cases) != 24 or cases["fault_family"].value_counts().to_dict() != {
        "turns": 12,
        "windings": 12,
    }:
        raise AssertionError("Expected 12 cases per PMSG fault family")
    cases["family_case_index"] = cases.groupby("fault_family").cumcount()
    cases["topology_bucket"] = cases["family_case_index"] % 3
    cases["topology_id"] = (
        cases["fault_family"]
        + "__"
        + cases["terminal_a"]
        + "__"
        + cases["terminal_b"]
    )
    counts = cases.groupby(["topology_bucket", "fault_family"]).size()
    if not counts.eq(4).all():
        raise AssertionError("Each topology bucket must contain 4 cases per family")
    return cases
