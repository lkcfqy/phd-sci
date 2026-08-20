from pmsm_sci.faults.tdms_io import window_ranges


def test_windows_never_cross_macro_block_boundaries() -> None:
    ranges = window_ranges(
        1_000, window_samples=100, stride_samples=50, block_samples=250
    )
    assert len(ranges) == 16
    for item in ranges:
        assert item.start // 250 == item.block_id
        assert (item.stop - 1) // 250 == item.block_id


def test_incomplete_tail_is_not_silently_used() -> None:
    ranges = window_ranges(
        1_099, window_samples=100, stride_samples=100, block_samples=500
    )
    assert ranges[-1].stop == 1_000
