import numpy as np
import pandas as pd
import pytest

from pmsm_sci.faults.external_validation import (
    external_health_role,
    robust_reference_parameters,
    robust_transform,
    system_block_scores,
)


def test_robust_reference_matches_median_and_handles_invariant_column() -> None:
    values = np.asarray([[1.0, 5.0], [2.0, 5.0], [3.0, 5.0]])
    center, scale = robust_reference_parameters(values)
    transformed = robust_transform(values, center, scale)
    assert center.tolist() == pytest.approx([2.0, 5.0])
    assert scale[1] == pytest.approx(1.0)
    assert transformed[:, 1].tolist() == pytest.approx([0.0, 0.0, 0.0])


def test_external_health_roles_are_record_disjoint() -> None:
    frame = pd.DataFrame(
        {
            "load_nm": np.repeat([0, 5, 10, 15, 20, 25, 30, 35], 8),
            "block_id": np.tile(np.arange(8), 8),
            "is_healthy": True,
        }
    )
    roles = external_health_role(frame)
    assert (roles == "adaptation").sum() == 4
    assert (roles == "calibration").sum() == 24
    assert (roles == "health_test").sum() == 32
    assert (roles == "unused").sum() == 4
    role_loads = {
        role: set(frame.loc[roles.eq(role), "load_nm"].astype(int))
        for role in ("adaptation", "calibration", "health_test")
    }
    assert role_loads["adaptation"].isdisjoint(role_loads["calibration"])
    assert role_loads["adaptation"].isdisjoint(role_loads["health_test"])
    assert role_loads["calibration"].isdisjoint(role_loads["health_test"])


def test_system_score_is_maximum_over_window_and_subsystem() -> None:
    rows = []
    scores = []
    for subsystem_number, subsystem in enumerate(("SubSys1", "SubSys2"), start=1):
        for window in range(15):
            rows.append(
                {
                    "record_id": "healthy_5Nm",
                    "load_nm": 5,
                    "subsystem": subsystem,
                    "block_id": 0,
                }
            )
            scores.append(subsystem_number * 10 + window)
    result = system_block_scores(pd.DataFrame(rows), scores)
    assert len(result) == 1
    assert result.loc[0, "score"] == pytest.approx(34.0)
    assert result.loc[0, "subsystem_count"] == 2


def test_system_score_rejects_missing_subsystem() -> None:
    frame = pd.DataFrame(
        {
            "record_id": ["one"] * 15,
            "load_nm": [5] * 15,
            "subsystem": ["SubSys1"] * 15,
            "block_id": [0] * 15,
        }
    )
    with pytest.raises(ValueError, match="expected subsystem"):
        system_block_scores(frame, np.arange(15.0))
