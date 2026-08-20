"""Time-ordered target-health budget partitions for sensitivity experiments."""

from __future__ import annotations

import math
from dataclasses import dataclass

import numpy as np


@dataclass(frozen=True)
class BudgetPartition:
    """One chronological target-health partition, including intentionally unused blocks."""

    adaptation: np.ndarray
    calibration: np.ndarray
    test: np.ndarray
    guard: np.ndarray
    unused: np.ndarray


def minimum_calibration_blocks(alpha: float) -> int:
    """Return the fewest calibration units yielding a finite split-conformal threshold."""

    if not 0 < alpha < 1:
        raise ValueError("alpha must lie strictly between zero and one")
    # A finite upper threshold requires ceil((n + 1) * (1 - alpha)) <= n,
    # equivalently alpha * (n + 1) >= 1. The tiny tolerance only protects
    # exact reciprocal values (for example alpha=0.05) from binary rounding.
    return max(1, math.ceil((1.0 / alpha) - 1.0 - 1e-12))


def _indices(start: int, size: int) -> np.ndarray:
    return np.arange(start, start + size, dtype=np.int64)


def fixed_horizon_budget_partition(
    n_blocks: int,
    *,
    adaptation_blocks: int,
    max_adaptation_blocks: int,
    calibration_blocks: int,
    guard_blocks: int = 1,
) -> BudgetPartition:
    """Create nested adaptation budgets with identical calibration and test periods.

    Every budget uses a prefix of the initial maximum-adaptation region. The
    remaining prefix blocks are deliberately unused, so changing the statistical
    adaptation budget does not also change calibration or test time.
    """

    if not 1 <= adaptation_blocks <= max_adaptation_blocks:
        raise ValueError("adaptation_blocks must lie in [1, max_adaptation_blocks]")
    if calibration_blocks < 1 or guard_blocks < 0:
        raise ValueError("calibration_blocks must be positive and guards non-negative")
    required = max_adaptation_blocks + calibration_blocks + 2 * guard_blocks
    if required >= n_blocks:
        raise ValueError("partition leaves no target-health test blocks")

    adaptation = _indices(0, adaptation_blocks)
    unused = _indices(adaptation_blocks, max_adaptation_blocks - adaptation_blocks)
    cursor = max_adaptation_blocks
    guard_one = _indices(cursor, guard_blocks)
    cursor += guard_blocks
    calibration = _indices(cursor, calibration_blocks)
    cursor += calibration_blocks
    guard_two = _indices(cursor, guard_blocks)
    cursor += guard_blocks
    test = _indices(cursor, n_blocks - cursor)
    return BudgetPartition(
        adaptation=adaptation,
        calibration=calibration,
        test=test,
        guard=np.concatenate([guard_one, guard_two]),
        unused=unused,
    )


def sequential_budget_partition(
    n_blocks: int,
    *,
    adaptation_blocks: int,
    calibration_blocks: int,
    guard_blocks: int = 1,
) -> BudgetPartition:
    """Create a deployment-like partition whose calibration follows adaptation."""

    if adaptation_blocks < 1 or calibration_blocks < 1 or guard_blocks < 0:
        raise ValueError("adaptation/calibration must be positive and guards non-negative")
    required = adaptation_blocks + calibration_blocks + 2 * guard_blocks
    if required >= n_blocks:
        raise ValueError("partition leaves no target-health test blocks")

    cursor = 0
    adaptation = _indices(cursor, adaptation_blocks)
    cursor += adaptation_blocks
    guard_one = _indices(cursor, guard_blocks)
    cursor += guard_blocks
    calibration = _indices(cursor, calibration_blocks)
    cursor += calibration_blocks
    guard_two = _indices(cursor, guard_blocks)
    cursor += guard_blocks
    test = _indices(cursor, n_blocks - cursor)
    return BudgetPartition(
        adaptation=adaptation,
        calibration=calibration,
        test=test,
        guard=np.concatenate([guard_one, guard_two]),
        unused=np.asarray([], dtype=np.int64),
    )


def assert_budget_partition(partition: BudgetPartition, n_blocks: int) -> None:
    """Check that a budget partition is disjoint, ordered, and exhaustive."""

    groups = (
        partition.adaptation,
        partition.calibration,
        partition.test,
        partition.guard,
        partition.unused,
    )
    merged = np.concatenate(groups)
    if len(merged) != len(np.unique(merged)):
        raise AssertionError("A block appears in more than one budget subset")
    if not np.array_equal(np.sort(merged), np.arange(n_blocks)):
        raise AssertionError("Budget partition must cover every block")
    # ``guard`` intentionally concatenates the two separated guard regions.
    for values in (
        partition.adaptation,
        partition.calibration,
        partition.test,
        partition.unused,
    ):
        if values.size > 1 and not np.all(np.diff(values) == 1):
            raise AssertionError("Each budget subset must contain contiguous blocks")
