"""Leakage-resistant grouped split utilities."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd
from sklearn.model_selection import GroupShuffleSplit


@dataclass(frozen=True)
class SplitIndices:
    train: np.ndarray
    validation: np.ndarray
    test: np.ndarray


def make_grouped_split(
    groups: pd.Series,
    *,
    seed: int = 42,
    test_size: float = 0.20,
    validation_size: float = 0.20,
) -> SplitIndices:
    """Split complete profiles into train, validation, and test sets.

    ``validation_size`` is the fraction of the post-test training pool assigned
    to validation. Group overlap is checked explicitly.
    """

    indices = np.arange(len(groups))
    outer = GroupShuffleSplit(n_splits=1, test_size=test_size, random_state=seed)
    train_val_pos, test_pos = next(outer.split(indices, groups=groups))

    inner_groups = groups.iloc[train_val_pos].reset_index(drop=True)
    inner = GroupShuffleSplit(
        n_splits=1,
        test_size=validation_size,
        random_state=seed + 1,
    )
    train_inner, val_inner = next(inner.split(train_val_pos, groups=inner_groups))
    train_pos = train_val_pos[train_inner]
    val_pos = train_val_pos[val_inner]

    split = SplitIndices(train=train_pos, validation=val_pos, test=test_pos)
    assert_no_group_overlap(groups, split)
    return split


def assert_no_group_overlap(groups: pd.Series, split: SplitIndices) -> None:
    """Raise if any physical profile occurs in more than one split."""

    train_groups = set(groups.iloc[split.train].tolist())
    val_groups = set(groups.iloc[split.validation].tolist())
    test_groups = set(groups.iloc[split.test].tolist())
    if train_groups & val_groups or train_groups & test_groups or val_groups & test_groups:
        raise AssertionError("profile_id leakage detected across split partitions")


def split_manifest(groups: pd.Series, split: SplitIndices) -> pd.DataFrame:
    """Create a compact profile-level manifest for exact auditing."""

    rows: list[dict[str, int | str]] = []
    for label, positions in (
        ("train", split.train),
        ("validation", split.validation),
        ("test", split.test),
    ):
        counts = groups.iloc[positions].value_counts().sort_index()
        rows.extend(
            {"profile_id": int(profile), "split": label, "n_rows": int(count)}
            for profile, count in counts.items()
        )
    return pd.DataFrame(rows).sort_values(["split", "profile_id"]).reset_index(drop=True)
