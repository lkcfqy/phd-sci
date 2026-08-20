import numpy as np

from pmsm_sci.faults.splits import (
    assert_disjoint_partition,
    leave_one_motor_out,
    partition_contiguous_blocks,
)


def test_leave_one_motor_out_never_leaks_target_motor() -> None:
    folds = leave_one_motor_out()
    assert len(folds) == 3
    for fold in folds:
        assert fold.target_motor not in fold.source_motors
        assert len(fold.source_motors) == 2


def test_contiguous_partition_is_complete_and_guarded() -> None:
    partition = partition_contiguous_blocks(60, guard_blocks=2)
    assert_disjoint_partition(partition, 60)
    assert partition.adaptation[-1] + 1 == partition.guard[0]
    assert partition.guard[1] + 1 == partition.calibration[0]
    assert partition.calibration[-1] + 1 == partition.guard[2]
    assert partition.guard[3] + 1 == partition.test[0]
    assert np.all(np.diff(partition.test) == 1)
