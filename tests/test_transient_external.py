from __future__ import annotations

import numpy as np
import pytest
from matio.utils import MatlabOpaque

from pmsm_sci.faults.signal_features import clarke_transform
from pmsm_sci.faults.transient_external import (
    extract_timeseries,
    fault_current_onset,
    load_transient_record,
    parse_loaded_transient_record,
    parse_transient_record_path,
    post_fault_window_bounds,
    pre_fault_window_bounds,
    pseudo_three_phase,
    record_disjoint_split,
    validate_transient_inventory,
)


def test_pseudo_three_phase_round_trips_alpha_beta_and_has_zero_sequence() -> None:
    time = np.arange(1_000) / 10_000
    alpha_beta = np.column_stack(
        [np.sin(2 * np.pi * 200 * time), np.cos(2 * np.pi * 200 * time)]
    )
    reconstructed = pseudo_three_phase(alpha_beta)
    transformed = clarke_transform(reconstructed)
    np.testing.assert_allclose(transformed[:, :2], alpha_beta, atol=1e-12)
    np.testing.assert_allclose(transformed[:, 2], 0.0, atol=1e-12)


def test_fault_current_onset_uses_first_sustained_fault_current_interval() -> None:
    sample_rate = 10_000
    onset = 20_000
    time = np.arange(40_000) / sample_rate
    current = np.zeros_like(time)
    current[onset:] = 4.0 * np.sin(2 * np.pi * 200 * time[onset:])
    result = fault_current_onset(current, sample_rate)
    assert onset <= result.onset_index <= onset + 200
    assert result.baseline_stop_index == 5_000
    assert result.threshold > 0


def test_fault_current_onset_rejects_absent_fault() -> None:
    with pytest.raises(ValueError, match="no resolvable"):
        fault_current_onset(np.zeros(30_000), 10_000)


def test_pre_and_post_windows_respect_guard_and_onset_alignment() -> None:
    pre = pre_fault_window_bounds(40_000, 20_000, 10_000)
    post = post_fault_window_bounds(
        40_000, 20_000, 10_000, horizon_seconds=1.0
    )
    assert len(pre) == 9
    assert pre[-1] == (16_000, 18_000)
    assert post == [
        (20_000, 22_000),
        (22_000, 24_000),
        (24_000, 26_000),
        (26_000, 28_000),
        (28_000, 30_000),
    ]


def test_record_split_is_deterministic_disjoint_and_fit_heavy() -> None:
    records = tuple(f"record_{index}" for index in range(11))
    first = record_disjoint_split("heldout", records)
    second = record_disjoint_split("heldout", records)
    assert first == second
    assert len(first.fit) == 6
    assert len(first.calibration) == 5
    assert set(first.fit).isdisjoint(first.calibration)
    assert set(first.fit) | set(first.calibration) == set(records)


def test_record_split_rejects_heldout_leakage() -> None:
    with pytest.raises(ValueError, match="held-out"):
        record_disjoint_split("r0", ["r0", "r1"])


def matlab_timeseries(data: np.ndarray, time: np.ndarray) -> MatlabOpaque:
    return MatlabOpaque(
        properties={"Data": data, "Time": time},
        classname="timeseries",
    )


def test_extract_timeseries_uses_semantic_paths_and_orients_data() -> None:
    time = np.arange(1_000, dtype=np.float64) / 10_000
    data = np.column_stack([np.sin(time), np.cos(time)])
    extracted = extract_timeseries(
        matlab_timeseries(data.T, time.reshape(-1, 1)), expected_columns=2
    )
    np.testing.assert_array_equal(extracted.time, time)
    np.testing.assert_array_equal(extracted.data, data)
    assert extracted.time_property_path == "Time"
    assert extracted.data_property_path == "Data"


def test_extract_timeseries_rejects_ambiguous_data_candidates() -> None:
    time = np.arange(1_000, dtype=np.float64) / 10_000
    opaque = MatlabOpaque(
        properties={"Time": time, "DataA": np.ones(1_000), "DataB": np.ones(1_000)},
        classname="timeseries",
    )
    with pytest.raises(ValueError, match="ambiguous"):
        extract_timeseries(opaque, expected_columns=1)


def test_post_reveal_implicit_uniform_time_is_opt_in_and_shape_checked() -> None:
    samples = 1_001
    time_info = MatlabOpaque(
        properties={
            "Initialized": np.array([[True]]),
            "Start_": np.array([[0.0]]),
            "Increment_": np.array([[0.0001]]),
            "Length": np.array([[float(samples)]]),
            "Units": np.array(["seconds"]),
            "Time_": np.empty((0, 0)),
        },
        classname="tsdata.timemetadata",
    )
    opaque = MatlabOpaque(
        properties={
            "Data_": np.ones((2, 1, samples), dtype=np.float32),
            "Time_": np.empty((0, 0)),
            "TimeInfo": time_info,
        },
        classname="timeseries",
    )
    with pytest.raises(ValueError, match="no 10 kHz monotonic time"):
        extract_timeseries(opaque, expected_columns=2)
    extracted = extract_timeseries(
        opaque,
        expected_columns=2,
        allow_implicit_uniform_time=True,
    )
    assert extracted.data.shape == (samples, 2)
    assert extracted.time[0] == 0
    assert extracted.time[-1] == pytest.approx(0.1)
    assert extracted.time_property_path == "TimeInfo/Start_+Increment_+Length"


def test_parse_official_inventory_and_loaded_whitelist(tmp_path) -> None:
    records = []
    conditions = ("load_transient", "steady_state", "velocity_transient")
    for condition in conditions:
        for speed, turns in ((1000, 4), (1200, 2), (1200, 4), (1200, 6)):
            records.append(
                parse_transient_record_path(
                    tmp_path
                    / "200Wmotor"
                    / f"{condition}_{speed}_{turns}turns.mat"
                )
            )
        for turns in (1, 2, 3):
            suffix = "turn" if turns == 1 else "turns"
            records.append(
                parse_transient_record_path(
                    tmp_path / "20kWmotor" / f"{condition}_1000_{turns}{suffix}.mat"
                )
            )
    validate_transient_inventory(records)

    metadata = records[0]
    time = np.arange(1_000, dtype=np.float64) / 10_000
    loaded = {
        "ialbt_meas": matlab_timeseries(np.ones((1_000, 2)), time),
        "if_meas": matlab_timeseries(np.ones((1_000, 1)), time),
        "we": matlab_timeseries(np.ones((1_000, 1)), time),
    }
    parsed = parse_loaded_transient_record(metadata, loaded)
    assert parsed.metadata.motor_id == "200W"
    assert parsed.alpha_beta.shape == (1_000, 2)
    assert parsed.fault_current.shape == (1_000,)
    assert parsed.sample_rate_hz == pytest.approx(10_000)


def test_loader_symbol_is_available_without_opening_a_mat_file() -> None:
    assert callable(load_transient_record)
