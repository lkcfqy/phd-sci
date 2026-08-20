"""Data discovery, loading, and schema validation."""

from __future__ import annotations

from pathlib import Path

import pandas as pd

from .constants import REQUIRED_COLUMNS


def discover_dataset(data_dir: Path) -> Path:
    """Find the PMSM CSV below ``data_dir``.

    The Kaggle archive has changed file naming across versions, so discovery is
    schema-oriented rather than tied to a single filename.
    """

    candidates = sorted(data_dir.rglob("*.csv"))
    preferred = [path for path in candidates if "temperature" in path.name.lower()]
    for path in preferred + candidates:
        try:
            columns = pd.read_csv(path, nrows=0).columns
        except (OSError, UnicodeDecodeError, ValueError, pd.errors.ParserError):
            continue
        if set(REQUIRED_COLUMNS).issubset(columns):
            return path
    raise FileNotFoundError(
        f"No CSV with the required PMSM schema found below {data_dir.resolve()}"
    )


def load_dataset(path: Path) -> pd.DataFrame:
    """Load and validate the public PMSM temperature dataset."""

    frame = pd.read_csv(path)
    missing = sorted(set(REQUIRED_COLUMNS) - set(frame.columns))
    if missing:
        raise ValueError(f"Dataset is missing required columns: {missing}")
    if frame[REQUIRED_COLUMNS].isna().any().any():
        bad = frame[REQUIRED_COLUMNS].columns[frame[REQUIRED_COLUMNS].isna().any()].tolist()
        raise ValueError(f"Missing values found in required columns: {bad}")
    frame = frame.copy()
    frame["profile_id"] = frame["profile_id"].astype("int64")
    return frame


def downsample_profiles(frame: pd.DataFrame, stride: int) -> pd.DataFrame:
    """Deterministically retain every ``stride``-th sample within each profile."""

    if stride < 1:
        raise ValueError("stride must be >= 1")
    if stride == 1:
        return frame.reset_index(drop=True)
    positions = frame.groupby("profile_id", sort=False).cumcount()
    return frame.loc[positions.mod(stride).eq(0)].reset_index(drop=True)
