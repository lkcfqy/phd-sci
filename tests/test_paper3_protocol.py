from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from pmsm_sci.faults.paper3 import (
    PAPER3_LOADS_NM,
    aggregate_paper3_system_blocks,
    paper3_load_roles,
)


def test_load_roles_have_valid_geometry_and_never_overlap() -> None:
    for test_load in PAPER3_LOADS_NM:
        roles = paper3_load_roles(test_load)
        assert set(roles) == set(PAPER3_LOADS_NM)
        assert list(roles.values()).count("test") == 1
        assert list(roles.values()).count("calibration") == 3
        assert list(roles.values()).count("fit") == 4
        assert roles[test_load] == "test"
        fit = np.asarray([load for load, role in roles.items() if role == "fit"])
        calibration = np.asarray(
            [load for load, role in roles.items() if role == "calibration"]
        )
        assert calibration.min() >= fit.min()
        assert calibration.max() <= fit.max()
        if test_load not in {0.0, 35.0}:
            assert (fit < test_load).any()
            assert (fit > test_load).any()


def test_system_aggregation_maxes_scores_and_requires_complete_support() -> None:
    rows = []
    scores = []
    supported = []
    for subsystem_index, subsystem in enumerate(("SubSys1", "SubSys2")):
        for window in range(15):
            rows.append(
                {
                    "record_id": "healthy_0",
                    "load_nm": 0.0,
                    "fault_turns": 0,
                    "fault_phase": np.nan,
                    "is_healthy": True,
                    "subsystem": subsystem,
                    "block_id": 0,
                }
            )
            scores.append(float(subsystem_index * 100 + window))
            supported.append(not (subsystem == "SubSys2" and window == 4))
    result = aggregate_paper3_system_blocks(pd.DataFrame(rows), scores, supported)
    assert len(result) == 1
    assert result.loc[0, "score"] == 114.0
    assert not bool(result.loc[0, "supported"])


def test_unknown_test_load_is_rejected() -> None:
    with pytest.raises(ValueError, match="Unknown"):
        paper3_load_roles(7.5)
