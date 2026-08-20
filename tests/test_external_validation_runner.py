import numpy as np
import pandas as pd
import pytest

from scripts.run_external_pmsm_validation import (
    evaluate_system_scores,
    external_roles,
)


def _external_frame(*, include_fault: bool = False) -> pd.DataFrame:
    rows = []
    for load in (0, 5, 10, 15, 20, 25, 30, 35):
        for subsystem in ("SubSys1", "SubSys2"):
            for block in range(8):
                for window in range(15):
                    rows.append(
                        {
                            "record_id": f"healthy_{load}",
                            "load_nm": load,
                            "subsystem": subsystem,
                            "block_id": block,
                            "window_id": window,
                            "is_healthy": True,
                            "fault_turns": 0,
                            "fault_phase": "none",
                        }
                    )
    if include_fault:
        for subsystem in ("SubSys1", "SubSys2"):
            for block in range(8):
                for window in range(15):
                    rows.append(
                        {
                            "record_id": "fault_1u_5",
                            "load_nm": 5,
                            "subsystem": subsystem,
                            "block_id": block,
                            "window_id": window,
                            "is_healthy": False,
                            "fault_turns": 1,
                            "fault_phase": "u",
                        }
                    )
    return pd.DataFrame(rows)


def test_external_roles_never_assign_fault_to_health_subset() -> None:
    frame = _external_frame(include_fault=True)
    roles = external_roles(frame)
    assert roles[~frame["is_healthy"]].eq("fault_test").all()
    assert set(roles[frame["is_healthy"]]) == {
        "adaptation",
        "calibration",
        "health_test",
        "unused",
    }


def test_health_only_system_evaluation_has_frozen_counts() -> None:
    frame = _external_frame()
    scores = frame["load_nm"].to_numpy(dtype=float) + (
        frame["window_id"].to_numpy(dtype=float) / 100
    )
    summary, blocks, records = evaluate_system_scores(
        frame,
        scores,
        method="synthetic",
        alpha=0.05,
        require_faults=False,
    )
    assert summary["calibration_blocks"] == 24
    assert summary["health_test_blocks"] == 32
    assert summary["faults_available"] is False
    assert len(blocks[blocks["role"].eq("adaptation")]) == 4
    assert records.empty


def test_confirmatory_flag_rejects_partial_fault_reveal() -> None:
    frame = _external_frame(include_fault=True)
    with pytest.raises(AssertionError, match="48 fault records"):
        evaluate_system_scores(
            frame,
            np.arange(len(frame), dtype=float),
            method="synthetic",
            alpha=0.05,
            require_faults=True,
        )
