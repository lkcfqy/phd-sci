from __future__ import annotations

import itertools

import pytest

from scripts.download_transient_pmsm_archive import range_plan


def test_range_plan_is_contiguous_complete_and_balanced() -> None:
    ranges = range_plan(13, 101, 4)
    assert ranges[0][0] == 13
    assert ranges[-1][1] == 101
    assert all(
        left[1] + 1 == right[0] for left, right in itertools.pairwise(ranges)
    )
    lengths = [stop - start + 1 for start, stop in ranges]
    assert max(lengths) - min(lengths) <= 1
    assert sum(lengths) == 89


def test_range_plan_reduces_workers_for_tiny_range() -> None:
    assert range_plan(5, 6, 8) == [(5, 5), (6, 6)]


@pytest.mark.parametrize("start, stop, workers", [(-1, 2, 1), (2, 1, 1), (0, 2, 0)])
def test_range_plan_rejects_invalid_input(start: int, stop: int, workers: int) -> None:
    with pytest.raises(ValueError):
        range_plan(start, stop, workers)
