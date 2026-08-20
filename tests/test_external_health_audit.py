from pathlib import Path

import numpy as np
import pytest
from scipy.io import savemat

from scripts.audit_external_pmsm_health import (
    ADAPTATION_BLOCK_IDS,
    ANALYSIS_BLOCK_IDS,
    AUDIT_VECTORS,
    CALIBRATION_LOADS_NM,
    EXPECTED_VARIABLES,
    HEALTH_TEST_LOADS_NM,
    audit_health_file,
    calibration_feasibility,
    minimum_calibration_blocks,
    protocol_role,
)


def synthetic_health_mat(path: Path, *, sample_rate_hz: float = 100.0, seconds: float = 6.5) -> None:
    samples = round(sample_rate_hz * seconds) + 1
    time = np.arange(samples, dtype=np.float64) / sample_rate_hz
    base = np.sin(2.0 * np.pi * 25.0 * time).astype(np.float32)
    values: dict[str, np.ndarray] = {}
    for name in EXPECTED_VARIABLES:
        if name == "Time":
            vector = time
        elif name in {"Speed_rad_el", "Speed_requred_rad_el"}:
            vector = np.full(samples, 2.0 * np.pi * 100.0, dtype=np.float32)
        elif name in {"Speed_rpm", "Speed_requred_rpm"}:
            vector = np.full(samples, 600.0, dtype=np.float32)
        else:
            vector = base
        values[name] = vector.reshape(-1, 1)
    savemat(path, values)


def test_alpha_point_zero_five_resolution_is_arithmetic_not_a_coverage_claim() -> None:
    assert minimum_calibration_blocks(0.05) == 19
    assert calibration_feasibility(18)["finite_upper_threshold"] is False
    feasible = calibration_feasibility(24)
    assert feasible["finite_upper_threshold"] is True
    assert feasible["minimum_attainable_p_value"] == pytest.approx(0.04)
    assert feasible["upper_threshold_order_statistic_rank"] == 24


def test_frozen_roles_are_record_disjoint_and_have_declared_counts() -> None:
    assignments = {
        (load, block): protocol_role(load, block)
        for load in range(0, 40, 5)
        for block in range(13)
    }
    assert sum(role == "adaptation" for role in assignments.values()) == 4
    assert sum(role == "calibration" for role in assignments.values()) == 24
    assert sum(role == "health_test" for role in assignments.values()) == 32
    assert {
        load for (load, _), role in assignments.items() if role == "adaptation"
    } == {0}
    assert {
        load for (load, _), role in assignments.items() if role == "calibration"
    } == set(CALIBRATION_LOADS_NM)
    assert {
        load for (load, _), role in assignments.items() if role == "health_test"
    } == set(HEALTH_TEST_LOADS_NM)
    assert set(ADAPTATION_BLOCK_IDS).issubset(ANALYSIS_BLOCK_IDS)


def test_synthetic_mat_audit_reports_structure_sampling_and_blocks(tmp_path: Path) -> None:
    path = tmp_path / "spd10-5000rpm_flt0z_0NM.mat"
    synthetic_health_mat(path)
    file_row, variables, blocks = audit_health_file(path)
    assert file_row["samples"] == 651
    assert file_row["sample_rate_hz"] == pytest.approx(100.0)
    assert file_row["duration_seconds"] == pytest.approx(6.5)
    assert file_row["complete_0p2s_windows"] == 32
    assert file_row["complete_3s_blocks"] == 2
    assert len(variables) == len(EXPECTED_VARIABLES)
    assert len(blocks) == 2
    assert all(row["samples"] == 300 for row in blocks)
    assert all(row["fully_inside_20_500hz_feature_band"] for row in blocks)
    assert set(AUDIT_VECTORS).issubset({row["variable"] for row in variables})


def test_missing_required_variable_is_rejected(tmp_path: Path) -> None:
    path = tmp_path / "spd10-5000rpm_flt0z_0NM.mat"
    synthetic_health_mat(path)
    from scipy.io import loadmat

    values = {
        key: value
        for key, value in loadmat(path).items()
        if not key.startswith("__") and key != "Currents_SubSys2_C"
    }
    savemat(path, values)
    with pytest.raises(ValueError, match="missing expected variables"):
        audit_health_file(path)
