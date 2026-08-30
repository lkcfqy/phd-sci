"""Loading and validation for the public PMSM geometry--torque dataset."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pandas as pd

PUBLISHED_FILES = {
    "train_test": ("train_test_parameters.csv", "train_test_torque.csv"),
    "uq_uniform": ("uq_uniform_parameters_11k.csv", "uq_uniform_torque_11k.csv"),
    "uq_gauss": ("uq_gauss_parameters_10k.csv", "uq_gauss_torque_10k.csv"),
}


@dataclass(frozen=True)
class TorqueDataset:
    """One aligned table of geometries and periodic torque signals."""

    name: str
    parameters: pd.DataFrame
    torque: np.ndarray
    angles_deg: np.ndarray
    parameter_path: Path
    torque_path: Path

    @property
    def n_designs(self) -> int:
        return len(self.parameters)

    @property
    def n_parameters(self) -> int:
        return self.parameters.shape[1]

    @property
    def n_angles(self) -> int:
        return self.torque.shape[1]


def sha256(path: Path) -> str:
    """Return a streaming SHA-256 digest."""

    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def load_torque_pair(
    parameter_path: Path,
    torque_path: Path,
    *,
    name: str,
    expected_parameters: int = 20,
    expected_angles: int = 120,
) -> TorqueDataset:
    """Load an aligned parameter/torque pair and enforce stable domain rules."""

    parameters = pd.read_csv(parameter_path)
    torque_frame = pd.read_csv(torque_path)
    try:
        angles = np.asarray([float(column) for column in torque_frame.columns], dtype=float)
    except ValueError as error:
        raise ValueError(f"{name}: torque headers must be numeric angles") from error

    torque = torque_frame.to_numpy(dtype=float)
    parameter_values = parameters.to_numpy(dtype=float)
    if len(parameters) != len(torque):
        raise ValueError(
            f"{name}: parameter and torque row counts differ "
            f"({len(parameters)} != {len(torque)})"
        )
    if parameters.shape[1] != expected_parameters:
        raise ValueError(
            f"{name}: expected {expected_parameters} parameters, got {parameters.shape[1]}"
        )
    if torque.shape[1] != expected_angles:
        raise ValueError(f"{name}: expected {expected_angles} angles, got {torque.shape[1]}")
    if not np.isfinite(parameter_values).all() or not np.isfinite(torque).all():
        raise ValueError(f"{name}: non-finite values found")
    if parameters.columns.duplicated().any() or torque_frame.columns.duplicated().any():
        raise ValueError(f"{name}: duplicate columns found")
    if parameters.duplicated().any():
        raise ValueError(f"{name}: duplicate parameter designs found")
    if torque_frame.duplicated().any():
        raise ValueError(f"{name}: duplicate torque signals found")
    if len(angles) < 2 or not np.all(np.diff(angles) > 0):
        raise ValueError(f"{name}: torque angles must be strictly increasing")
    spacing = np.diff(angles)
    if not np.allclose(spacing, spacing[0], rtol=0.0, atol=1e-12):
        raise ValueError(f"{name}: torque angles must be equally spaced")

    return TorqueDataset(
        name=name,
        parameters=parameters,
        torque=torque,
        angles_deg=angles,
        parameter_path=parameter_path,
        torque_path=torque_path,
    )


def load_published_torque_data(root: Path) -> dict[str, TorqueDataset]:
    """Load all three tables released with DOI 10.5281/zenodo.15688397."""

    datasets: dict[str, TorqueDataset] = {}
    for name, (parameter_file, torque_file) in PUBLISHED_FILES.items():
        datasets[name] = load_torque_pair(
            root / parameter_file,
            root / torque_file,
            name=name,
        )

    parameter_columns = datasets["train_test"].parameters.columns.tolist()
    reference_angles = datasets["train_test"].angles_deg
    for name, dataset in datasets.items():
        if dataset.parameters.columns.tolist() != parameter_columns:
            raise ValueError(f"{name}: parameter schema differs from train_test")
        if not np.array_equal(dataset.angles_deg, reference_angles):
            raise ValueError(f"{name}: angle grid differs from train_test")
    return datasets


def parameter_row_hashes(frame: pd.DataFrame) -> set[int]:
    """Hash exact published parameter rows for cross-table overlap checks."""

    return set(pd.util.hash_pandas_object(frame, index=False).astype("uint64").tolist())
