from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest
from scipy.io import savemat

from pmsm_sci.faults.pmsg_confirmation import (
    HEALTH_CALIBRATION_CONDITIONS,
    HEALTH_FIT_CONDITIONS,
    HEALTH_TEST_CONDITIONS,
    REQUIRED_MAT_VARIABLES,
    extract_pmsg_feature_rows,
    iter_pmsg_windows,
    load_pmsg_mat,
    parse_pmsg_filename,
    standalone_health_role,
)


def _write_record(path: Path) -> Path:
    time = np.arange(60_001, dtype=np.float64) / 20_000.0
    angle = 2 * np.pi * 40.0 * time
    currents = (
        np.sin(angle),
        np.sin(angle - 2 * np.pi / 3),
        np.sin(angle + 2 * np.pi / 3),
    )
    savemat(
        path,
        {
            "t": time[None, :],
            "Ia": currents[0][:, None],
            "Ib": currents[1][None, :],
            "Ic": currents[2][:, None],
            # Forbidden fields are malformed to prove whitelist-only loading.
            "Ifault": np.asarray([[np.nan]]),
            "Fault_Relay": np.asarray([[np.nan]]),
            "Theta_est": np.asarray([[np.nan]]),
        },
    )
    return path


def test_filename_parser_covers_health_and_two_fault_families() -> None:
    healthy = parse_pmsg_filename("HEALTHY_S1500_T64.mat")
    assert healthy.is_healthy
    assert healthy.condition == (1500, 64)
    assert healthy.fault_span_percent is None

    turns = parse_pmsg_filename("FAULT_TURNS_D01_D04_R026_S1200_T52.mat")
    assert not turns.is_healthy
    assert turns.fault_family == "turns"
    assert turns.resistance_code == "026"
    assert turns.fault_span_percent == pytest.approx(12.04)

    windings = parse_pmsg_filename("FAULT_WINDINGS_D16_D19_R026_S1800_T80.mat")
    assert windings.fault_family == "windings"
    assert windings.fault_span_percent == pytest.approx(10.6)


@pytest.mark.parametrize(
    "name",
    [
        "HEALTHY_S1000_T52.mat",
        "FAULT_TURNS_D01_D25_R026_S1200_T52.mat",
        "FAULT_COILS_D01_D04_R026_S1200_T52.mat",
        "FAULT_TURNS_D01_D01_R026_S1200_T52.mat",
    ],
)
def test_filename_parser_rejects_out_of_protocol_names(name: str) -> None:
    with pytest.raises(ValueError):
        parse_pmsg_filename(name)


def test_health_role_partition_is_complete_and_disjoint() -> None:
    conditions = {
        (speed, torque)
        for speed in (1200, 1500, 1800)
        for torque in (52, 64, 80)
    }
    assert set(HEALTH_FIT_CONDITIONS).isdisjoint(HEALTH_CALIBRATION_CONDITIONS)
    assert set(HEALTH_FIT_CONDITIONS).isdisjoint(HEALTH_TEST_CONDITIONS)
    assert set(HEALTH_CALIBRATION_CONDITIONS).isdisjoint(HEALTH_TEST_CONDITIONS)
    assert (
        set(HEALTH_FIT_CONDITIONS)
        | set(HEALTH_CALIBRATION_CONDITIONS)
        | set(HEALTH_TEST_CONDITIONS)
    ) == conditions
    assert standalone_health_role(parse_pmsg_filename("HEALTHY_S1200_T52.mat")) == "fit"
    assert (
        standalone_health_role(parse_pmsg_filename("HEALTHY_S1800_T64.mat"))
        == "calibration"
    )


def test_strict_load_and_frozen_windows_are_whitelist_only(tmp_path: Path) -> None:
    healthy_path = _write_record(tmp_path / "HEALTHY_S1200_T52.mat")
    healthy = load_pmsg_mat(healthy_path)
    assert healthy.currents.shape == (60_001, 3)
    assert healthy.sample_rate_hz == pytest.approx(20_000.0)
    health_windows = list(iter_pmsg_windows(healthy))
    assert len(health_windows) == 13
    assert {window.segment for window, _ in health_windows} == {"health_analysis"}
    assert health_windows[0][0].start_time_s == pytest.approx(0.2)
    assert health_windows[-1][0].stop_time_s == pytest.approx(2.8)

    fault_path = _write_record(
        tmp_path / "FAULT_TURNS_D01_D04_R026_S1200_T52.mat"
    )
    fault = load_pmsg_mat(fault_path)
    fault_windows = list(iter_pmsg_windows(fault))
    counts: dict[str, int] = {}
    for window, _ in fault_windows:
        counts[window.segment] = counts.get(window.segment, 0) + 1
    assert counts == {"pre_fault": 3, "fault_active": 2, "recovery": 6}
    rows = extract_pmsg_feature_rows(fault, source_sha256="0" * 64)
    assert len(rows) == 11
    assert all(row["fundamental_hz"] == pytest.approx(40.0) for row in rows)
    assert REQUIRED_MAT_VARIABLES == ("t", "Ia", "Ib", "Ic")


def test_loader_rejects_missing_phase(tmp_path: Path) -> None:
    time = np.arange(60_001, dtype=np.float64)[:, None] / 20_000.0
    path = tmp_path / "HEALTHY_S1500_T80.mat"
    savemat(path, {"t": time, "Ia": time, "Ib": time})
    with pytest.raises(ValueError, match="Ic"):
        load_pmsg_mat(path)
