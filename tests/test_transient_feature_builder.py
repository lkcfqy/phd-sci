from __future__ import annotations

from pathlib import Path

import numpy as np

from pmsm_sci.faults.transient_external import (
    TransientMetadata,
    TransientRecord,
)
from scripts.build_transient_pmsm_features import (
    PRIMARY_POST_WINDOWS,
    build_record_features,
)


def synthetic_record() -> TransientRecord:
    sample_rate = 10_000.0
    samples = 40_000
    time = np.arange(samples, dtype=np.float64) / sample_rate
    alpha_beta = np.column_stack(
        [
            np.sin(2 * np.pi * 200 * time),
            np.cos(2 * np.pi * 200 * time),
        ]
    )
    fault_current = np.zeros(samples)
    fault_current[20_000:] = 3.0 * np.sin(2 * np.pi * 200 * time[20_000:])
    return TransientRecord(
        metadata=TransientMetadata(
            path=Path("200Wmotor/steady_state_1200_2turns.mat"),
            motor_id="200W",
            motor_watts=200,
            condition="steady_state",
            setpoint_rad_s=1200,
            fault_turns=2,
            winding_turns=25,
            fault_phase="a",
        ),
        time=time,
        alpha_beta=alpha_beta,
        fault_current=fault_current,
        electrical_speed_rad_s=np.full(samples, 1200.0),
        sample_rate_hz=sample_rate,
        property_paths={
            name: {"time": "Time", "data": "Data"}
            for name in ("ialbt_meas", "if_meas", "we")
        },
    )


def test_record_builder_applies_guard_horizons_and_observability_rule() -> None:
    rows, diagnostics = build_record_features(synthetic_record())
    pre = [row for row in rows if row["segment"] == "pre_fault"]
    post = [row for row in rows if row["segment"] == "post_fault"]
    assert len(pre) in {8, 9}
    assert len(post) in {9, 10}
    assert sum(bool(row["primary_post_window"]) for row in post) == PRIMARY_POST_WINDOWS
    assert pre[-1]["stop_sample"] <= diagnostics["fault_onset_index"] - 2_000
    assert post[0]["start_sample"] in range(19_900, 20_101)
    assert diagnostics["main_endpoint_compatible"] is True
    assert diagnostics["pre_fault_windows"] == len(pre)
    assert diagnostics["post_fault_windows_up_to_2s"] == len(post)
    assert all("zero_sequence_rms" not in row for row in rows)
    assert all("zero_sequence_ratio" not in row for row in rows)
    assert all(np.isfinite(row["fundamental_hz"]) for row in rows)
