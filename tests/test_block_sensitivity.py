from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from scripts.run_block_sensitivity import (
    aggregation_order_from_largest,
    assign_macroblocks,
    audit_block_design,
    make_partition,
)


def test_only_one_two_and_three_second_designs_resolve_alpha_point_zero_five() -> None:
    designs = {
        seconds: audit_block_design(seconds, alpha=0.05)
        for seconds in (1.0, 2.0, 3.0, 5.0, 6.0)
    }

    assert [seconds for seconds, design in designs.items() if design.finite_alpha_threshold] == [
        1.0,
        2.0,
        3.0,
    ]
    assert [designs[seconds].calibration_blocks for seconds in (1.0, 2.0, 3.0)] == [
        60,
        30,
        20,
    ]
    assert designs[5.0].calibration_blocks == 12
    assert designs[6.0].calibration_blocks == 10
    assert all(not design.independence_claimed for design in designs.values())


@pytest.mark.parametrize(
    ("seconds", "expected"),
    [
        (1.0, (12, 60, 46)),
        (2.0, (6, 30, 22)),
        (3.0, (4, 20, 14)),
    ],
)
def test_feasible_partitions_are_ordered_and_guarded(
    seconds: float, expected: tuple[int, int, int]
) -> None:
    design = audit_block_design(seconds)
    partition = make_partition(design)

    assert (
        len(partition.adaptation),
        len(partition.calibration),
        len(partition.test),
    ) == expected
    assert len(partition.guard) == 2
    assert partition.adaptation[-1] + 1 == partition.guard[0]
    assert partition.guard[0] + 1 == partition.calibration[0]
    assert partition.calibration[-1] + 1 == partition.guard[1]
    assert partition.guard[1] + 1 == partition.test[0]


def test_macroblocks_are_rebuilt_from_window_ids_not_old_block_ids() -> None:
    design = audit_block_design(1.0)
    frame = pd.DataFrame(
        {
            "record_id": np.repeat(["a", "b"], 600),
            "window_id": np.tile(np.arange(600), 2),
            "block_id": 999,
        }
    )

    regrouped = assign_macroblocks(frame, design)

    assert regrouped.groupby("record_id")["block_id"].nunique().eq(120).all()
    assert regrouped.loc[0:4, "block_id"].eq(0).all()
    assert regrouped.loc[5:9, "block_id"].eq(1).all()
    assert regrouped.loc[599, "block_id"] == 119


def test_higher_q90_equals_max_for_five_and_ten_window_blocks() -> None:
    assert aggregation_order_from_largest(5, 0.9) == 1
    assert aggregation_order_from_largest(10, 0.9) == 1
    assert aggregation_order_from_largest(15, 0.9) == 2
    assert aggregation_order_from_largest(15, 1.0) == 1
