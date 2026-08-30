from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd
import pytest
from scipy.io import savemat

from pmsm_sci.faults.external_pmsm import file_sha256
from pmsm_sci.faults.operating_context import (
    OPERATING_CONTEXT_VARIABLES,
    attach_external_operating_context,
    load_external_operating_context,
)


def _context_mat(path: Path) -> Path:
    time = np.arange(101, dtype=np.float64) / 10.0
    speed = np.linspace(100.0, 200.0, 101, dtype=np.float32)
    savemat(
        path,
        {
            "Time": time[:, None],
            "Speed_requred_rpm": speed[:, None],
            "Speed_rpm": np.asarray([[np.nan]], dtype=np.float32),
            "Ifault": np.asarray([[np.nan]], dtype=np.float32),
        },
    )
    return path


def _production_context_mat(path: Path) -> tuple[Path, np.ndarray]:
    time = np.arange(415_001, dtype=np.float64) / 10_000.0
    speed = np.linspace(100.0, 4_000.0, 415_001, dtype=np.float32)
    savemat(
        path,
        {
            "Time": time[:, None],
            "Speed_requred_rpm": speed[:, None],
            "Speed_rpm": np.asarray([[np.nan]], dtype=np.float32),
        },
    )
    return path, speed


def test_context_loader_is_strict_and_whitelist_only(tmp_path: Path) -> None:
    path = _context_mat(tmp_path / "spd10-5000rpm_flt0z_0NM.mat")
    context = load_external_operating_context(
        path,
        expected_samples=101,
        expected_sample_rate_hz=10.0,
    )
    assert context.commanded_speed_rpm.shape == (101,)
    assert context.sample_rate_hz == pytest.approx(10.0)
    assert OPERATING_CONTEXT_VARIABLES == ("Time", "Speed_requred_rpm")


def test_attach_context_aligns_windows_and_both_subsystems(tmp_path: Path) -> None:
    path, speed = _production_context_mat(
        tmp_path / "spd10-5000rpm_flt0z_0NM.mat"
    )
    digest = file_sha256(path)
    rows = []
    for subsystem in ("SubSys1", "SubSys2"):
        rows.append(
            {
                "source_filename": path.name,
                "source_sha256": digest,
                "load_nm": 0.0,
                "subsystem": subsystem,
                "start_sample": 120_000,
                "stop_sample": 122_000,
                "start_time_s": 12.0,
                "stop_time_s": 12.2,
            }
        )
    frame = pd.DataFrame(rows)
    attached = attach_external_operating_context(frame, tmp_path)
    expected = float(np.mean(speed[120_000:122_000], dtype=np.float64))
    assert attached["commanded_speed_rpm"].tolist() == pytest.approx(
        [expected, expected]
    )
    assert frame.columns.tolist() == [
        "source_filename",
        "source_sha256",
        "load_nm",
        "subsystem",
        "start_sample",
        "stop_sample",
        "start_time_s",
        "stop_time_s",
    ]


def test_context_loader_rejects_measured_speed_substitution(tmp_path: Path) -> None:
    path = tmp_path / "spd10-5000rpm_flt0z_5NM.mat"
    time = np.arange(101, dtype=np.float64)[:, None] / 10.0
    savemat(path, {"Time": time, "Speed_rpm": np.ones_like(time, dtype=np.float32)})
    with pytest.raises(ValueError, match="Speed_requred_rpm"):
        load_external_operating_context(
            path,
            expected_samples=101,
            expected_sample_rate_hz=10.0,
        )
