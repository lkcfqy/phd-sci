from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest
from scipy.io import savemat

from pmsm_sci.faults.external_pmsm import (
    EXPECTED_SAMPLES,
    REQUIRED_MAT_VARIABLES,
    SUBSYSTEM_VARIABLES,
    extract_feature_rows,
    iter_analysis_windows,
    load_external_pmsm_mat,
    parse_external_pmsm_filename,
)


@pytest.fixture(scope="module")
def valid_payload() -> dict[str, np.ndarray]:
    time = np.arange(EXPECTED_SAMPLES, dtype=np.float64) / 10_000.0
    angle = 2 * np.pi * 100.0 * time
    phases = (
        np.sin(angle),
        np.sin(angle - 2 * np.pi / 3),
        np.sin(angle + 2 * np.pi / 3),
    )
    payload: dict[str, np.ndarray] = {"Time": time[:, None]}
    for subsystem_index, names in enumerate(SUBSYSTEM_VARIABLES.values(), start=1):
        for name, phase in zip(names, phases, strict=True):
            payload[name] = (subsystem_index * phase).astype(np.float32)[:, None]
    # Malformed forbidden variables prove that validation/loading is whitelist-only.
    payload["Currents_SubSys1_d"] = np.asarray([[np.nan]], dtype=np.float32)
    payload["Voltage_SubSys1_d"] = np.asarray([[np.nan]], dtype=np.float32)
    return payload


def _write_mat(
    path: Path,
    payload: dict[str, np.ndarray],
    *,
    overrides: dict[str, np.ndarray] | None = None,
) -> Path:
    values = dict(payload)
    values.update(overrides or {})
    savemat(path, values, do_compression=False)
    return path


def test_filename_parser_freezes_health_and_future_fault_labels() -> None:
    healthy = parse_external_pmsm_filename("spd10-5000rpm_flt0z_10NM.mat")
    assert healthy.load_nm == 10.0
    assert healthy.fault_turns == 0
    assert healthy.fault_phase is None
    assert healthy.is_healthy

    fault = parse_external_pmsm_filename("spd10-5000rpm_flt6zv_25NM.mat")
    assert fault.load_nm == 25.0
    assert fault.fault_turns == 6
    assert fault.fault_phase == "v"
    assert not fault.is_healthy


@pytest.mark.parametrize(
    "name",
    [
        "spd10-5000rpm_flt0zu_10NM.mat",
        "spd10-5000rpm_flt7zu_10NM.mat",
        "spd10-5000rpm_flt2zw_10NM.mat",
        "spd10-5000rpm_flt2zu_10NM.csv",
    ],
)
def test_filename_parser_rejects_conditions_outside_frozen_grammar(name: str) -> None:
    with pytest.raises(ValueError, match="Unsupported"):
        parse_external_pmsm_filename(name)


def test_strict_mat_load_window_split_and_feature_rows(
    tmp_path: Path, valid_payload: dict[str, np.ndarray]
) -> None:
    path = _write_mat(
        tmp_path / "spd10-5000rpm_flt0z_5NM.mat",
        valid_payload,
    )
    record = load_external_pmsm_mat(path)

    assert record.samples == 415_001
    assert record.sample_rate_hz == pytest.approx(10_000.0)
    assert record.time[0] == 0.0
    assert record.time[-1] == 41.5
    assert set(record.currents) == {"SubSys1", "SubSys2"}
    assert all(current.shape == (415_001, 3) for current in record.currents.values())
    assert not any("Voltage" in name or name.endswith(("_d", "_q")) for name in REQUIRED_MAT_VARIABLES)

    for subsystem in SUBSYSTEM_VARIABLES:
        windows = list(iter_analysis_windows(record, subsystem))
        assert len(windows) == 120
        assert {index.block_id for index, _ in windows} == set(range(8))
        assert all(sum(index.block_id == block for index, _ in windows) == 15 for block in range(8))
        first_index, first_current = windows[0]
        last_index, last_current = windows[-1]
        assert (first_index.start_sample, first_index.stop_sample) == (120_000, 122_000)
        assert (first_index.start_time_s, first_index.stop_time_s) == pytest.approx((12.0, 12.2))
        assert (last_index.start_sample, last_index.stop_sample) == (358_000, 360_000)
        assert (last_index.start_time_s, last_index.stop_time_s) == pytest.approx((35.8, 36.0))
        assert first_current.shape == last_current.shape == (2_000, 3)

    rows = extract_feature_rows(record, source_sha256="0" * 64)
    assert len(rows) == 240
    assert {row["subsystem"] for row in rows} == {"SubSys1", "SubSys2"}
    assert {row["record_id"] for row in rows} == {
        "external_dual_three_phase_flt0z_load_5nm",
    }
    streams = {(row["record_id"], row["subsystem"]) for row in rows}
    assert streams == {
        ("external_dual_three_phase_flt0z_load_5nm", "SubSys1"),
        ("external_dual_three_phase_flt0z_load_5nm", "SubSys2"),
    }
    assert all(row["motor_id"] == "external_dual_three_phase" for row in rows)
    assert all(row["is_healthy"] for row in rows)
    assert all(row["fundamental_hz"] == pytest.approx(100.0) for row in rows)


def test_strict_mat_loader_rejects_noncolumn_phase(
    tmp_path: Path, valid_payload: dict[str, np.ndarray]
) -> None:
    phase_name = SUBSYSTEM_VARIABLES["SubSys1"][0]
    path = _write_mat(
        tmp_path / "spd10-5000rpm_flt0z_0NM.mat",
        valid_payload,
        overrides={phase_name: valid_payload[phase_name].T},
    )
    with pytest.raises(ValueError, match="column vector"):
        load_external_pmsm_mat(path)


def test_strict_mat_loader_rejects_current_length_mismatch(
    tmp_path: Path, valid_payload: dict[str, np.ndarray]
) -> None:
    phase_name = SUBSYSTEM_VARIABLES["SubSys2"][2]
    path = _write_mat(
        tmp_path / "spd10-5000rpm_flt0z_20NM.mat",
        valid_payload,
        overrides={phase_name: valid_payload[phase_name][:-1]},
    )
    with pytest.raises(ValueError, match="equal length"):
        load_external_pmsm_mat(path)


def test_strict_mat_loader_rejects_wrong_sample_rate(
    tmp_path: Path, valid_payload: dict[str, np.ndarray]
) -> None:
    wrong_time = np.arange(EXPECTED_SAMPLES, dtype=np.float64)[:, None] / 9_999.0
    path = _write_mat(
        tmp_path / "spd10-5000rpm_flt0z_15NM.mat",
        valid_payload,
        overrides={"Time": wrong_time},
    )
    with pytest.raises(ValueError, match="10 kHz"):
        load_external_pmsm_mat(path)
