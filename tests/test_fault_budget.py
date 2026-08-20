import numpy as np
import pytest

from pmsm_sci.faults.budget import (
    assert_budget_partition,
    fixed_horizon_budget_partition,
    minimum_calibration_blocks,
    sequential_budget_partition,
)
from scripts.run_calibration_budget_sensitivity import (
    calibration_feasibility_table,
    seconds_to_blocks,
)


def test_alpha_point_zero_five_requires_nineteen_calibration_blocks() -> None:
    assert minimum_calibration_blocks(0.05) == 19
    assert minimum_calibration_blocks(0.10) == 9


def test_fixed_horizon_keeps_calibration_and_test_constant() -> None:
    small = fixed_horizon_budget_partition(
        40,
        adaptation_blocks=1,
        max_adaptation_blocks=8,
        calibration_blocks=20,
    )
    large = fixed_horizon_budget_partition(
        40,
        adaptation_blocks=8,
        max_adaptation_blocks=8,
        calibration_blocks=20,
    )
    assert_budget_partition(small, 40)
    assert_budget_partition(large, 40)
    assert small.adaptation.tolist() == [0]
    assert small.unused.tolist() == list(range(1, 8))
    assert np.array_equal(small.calibration, large.calibration)
    assert np.array_equal(small.test, large.test)
    assert small.calibration.tolist() == list(range(9, 29))
    assert small.test.tolist() == list(range(30, 40))


def test_sequential_partition_moves_calibration_after_adaptation() -> None:
    partition = sequential_budget_partition(
        40, adaptation_blocks=4, calibration_blocks=20
    )
    assert_budget_partition(partition, 40)
    assert partition.adaptation.tolist() == list(range(4))
    assert partition.guard.tolist() == [4, 25]
    assert partition.calibration.tolist() == list(range(5, 25))
    assert partition.test.tolist() == list(range(26, 40))
    assert partition.unused.size == 0


def test_short_calibration_budgets_are_explicitly_skipped_at_five_percent() -> None:
    table = calibration_feasibility_table(
        [3.0, 6.0, 12.0, 24.0],
        primary_calibration_seconds=60.0,
        block_seconds=3.0,
        alpha=0.05,
    ).set_index("calibration_seconds")
    assert not table.loc[[3.0, 6.0, 12.0, 24.0], "finite_threshold"].any()
    assert table.loc[57.0, "finite_threshold"]
    assert table.loc[60.0, "status"] == "primary_evaluated"


def test_seconds_must_respect_macroblock_unit() -> None:
    assert seconds_to_blocks(6.0, 3.0, name="duration") == 2
    with pytest.raises(ValueError, match="integer multiple"):
        seconds_to_blocks(5.0, 3.0, name="duration")


@pytest.mark.parametrize(
    ("kwargs", "message"),
    [
        (
            {
                "adaptation_blocks": 9,
                "max_adaptation_blocks": 8,
                "calibration_blocks": 20,
            },
            "adaptation_blocks",
        ),
        (
            {
                "adaptation_blocks": 8,
                "max_adaptation_blocks": 8,
                "calibration_blocks": 31,
            },
            "no target-health test",
        ),
    ],
)
def test_fixed_horizon_rejects_invalid_budgets(kwargs, message: str) -> None:
    with pytest.raises(ValueError, match=message):
        fixed_horizon_budget_partition(40, **kwargs)
