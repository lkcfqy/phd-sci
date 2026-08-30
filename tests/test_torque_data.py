from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from pmsm_sci.torque.data import load_torque_pair


def write_pair(root: Path, *, duplicate: bool = False) -> tuple[Path, Path]:
    parameters = pd.DataFrame(
        np.arange(60, dtype=float).reshape(3, 20),
        columns=[f"p{index}" for index in range(20)],
    )
    if duplicate:
        parameters.iloc[1] = parameters.iloc[0]
    angle = np.arange(120) * 0.25
    torque = pd.DataFrame(
        np.vstack([0.3 + 0.01 * index + np.sin(angle) for index in range(3)]),
        columns=[str(value) for value in angle],
    )
    parameter_path = root / "parameters.csv"
    torque_path = root / "torque.csv"
    parameters.to_csv(parameter_path, index=False)
    torque.to_csv(torque_path, index=False)
    return parameter_path, torque_path


def test_load_torque_pair_validates_alignment_and_grid(tmp_path: Path) -> None:
    parameter_path, torque_path = write_pair(tmp_path)
    dataset = load_torque_pair(parameter_path, torque_path, name="synthetic")
    assert dataset.n_designs == 3
    assert dataset.n_parameters == 20
    assert dataset.n_angles == 120
    np.testing.assert_allclose(np.diff(dataset.angles_deg), 0.25)


def test_load_torque_pair_rejects_duplicate_designs(tmp_path: Path) -> None:
    parameter_path, torque_path = write_pair(tmp_path, duplicate=True)
    with pytest.raises(ValueError, match="duplicate parameter"):
        load_torque_pair(parameter_path, torque_path, name="synthetic")
