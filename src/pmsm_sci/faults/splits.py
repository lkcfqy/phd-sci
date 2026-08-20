"""Leakage-resistant machine and contiguous-block split primitives."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np


@dataclass(frozen=True)
class LOMOFold:
    """One leave-one-motor-out fold."""

    fold_id: str
    source_motors: tuple[str, ...]
    target_motor: str


@dataclass(frozen=True)
class BlockPartition:
    """Indices for sequential target-health adaptation, calibration, and test blocks."""

    adaptation: np.ndarray
    calibration: np.ndarray
    test: np.ndarray
    guard: np.ndarray


def leave_one_motor_out(
    motors: tuple[str, ...] = ("1kW", "1.5kW", "3kW"),
) -> tuple[LOMOFold, ...]:
    """Create the three deterministic LOMO folds."""

    if len(set(motors)) != len(motors) or len(motors) < 2:
        raise ValueError("motors must contain at least two unique identifiers")
    return tuple(
        LOMOFold(
            fold_id=f"target_{target}",
            source_motors=tuple(motor for motor in motors if motor != target),
            target_motor=target,
        )
        for target in motors
    )


def partition_contiguous_blocks(
    n_blocks: int,
    *,
    adaptation_fraction: float = 0.25,
    calibration_fraction: float = 0.25,
    guard_blocks: int = 1,
) -> BlockPartition:
    """Split ordered blocks without mixing adjacent regions across subsets.

    Two guard regions separate adaptation/calibration and calibration/test. The
    fractions apply to the usable (non-guard) blocks; all remaining usable blocks
    are assigned to the untouched test subset.
    """

    if n_blocks < 5:
        raise ValueError("At least five blocks are required")
    if guard_blocks < 0:
        raise ValueError("guard_blocks must be non-negative")
    if adaptation_fraction <= 0 or calibration_fraction <= 0:
        raise ValueError("adaptation and calibration fractions must be positive")
    if adaptation_fraction + calibration_fraction >= 1:
        raise ValueError("adaptation + calibration fractions must be less than one")

    usable = n_blocks - 2 * guard_blocks
    if usable < 3:
        raise ValueError("Not enough usable blocks after applying guard regions")
    n_adaptation = max(1, int(np.floor(usable * adaptation_fraction)))
    n_calibration = max(1, int(np.floor(usable * calibration_fraction)))
    n_test = usable - n_adaptation - n_calibration
    if n_test < 1:
        raise ValueError("Partition leaves no test blocks")

    cursor = 0
    adaptation = np.arange(cursor, cursor + n_adaptation, dtype=np.int64)
    cursor += n_adaptation
    guard_one = np.arange(cursor, cursor + guard_blocks, dtype=np.int64)
    cursor += guard_blocks
    calibration = np.arange(cursor, cursor + n_calibration, dtype=np.int64)
    cursor += n_calibration
    guard_two = np.arange(cursor, cursor + guard_blocks, dtype=np.int64)
    cursor += guard_blocks
    test = np.arange(cursor, cursor + n_test, dtype=np.int64)
    guard = np.concatenate([guard_one, guard_two])
    return BlockPartition(adaptation, calibration, test, guard)


def assert_disjoint_partition(partition: BlockPartition, n_blocks: int) -> None:
    """Fail if any block is duplicated, omitted, or out of bounds."""

    arrays = (partition.adaptation, partition.calibration, partition.test, partition.guard)
    merged = np.concatenate(arrays)
    if len(np.unique(merged)) != len(merged):
        raise AssertionError("A block appears in more than one subset")
    if not np.array_equal(np.sort(merged), np.arange(n_blocks)):
        raise AssertionError("Partition must cover each block exactly once")
