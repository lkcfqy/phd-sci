from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from scripts.summarize_sampling_rate_sensitivity import (
    PROPOSED_METHOD,
    external_method_comparison,
    feature_shift_summary,
    validate_feature_pair,
    write_interpretation,
)


def feature_frames() -> tuple[pd.DataFrame, pd.DataFrame]:
    rows: list[dict[str, object]] = []
    for window in range(4):
        rows.append(
            {
                "record_id": "healthy",
                "motor_id": "1kW",
                "is_healthy": True,
                "fault_family": "intercoil",
                "severity_percent": 0.0,
                "block_id": window // 2,
                "window_id": window,
                "start_sample": window * 20_000,
                "stop_sample": (window + 1) * 20_000,
                "spectral_entropy": 0.1 + window,
            }
        )
    native = pd.DataFrame(rows)
    target = native.copy()
    target["start_sample"] //= 10
    target["stop_sample"] //= 10
    target["spectral_entropy"] += 0.25
    return native, target


def external_rows(proposed_detection: float) -> pd.DataFrame:
    methods = [PROPOSED_METHOD, "target_min_cov_det"]
    rows: list[dict[str, object]] = []
    for method in methods:
        rows.append(
            {
                "method": method,
                "threshold": 2.0,
                "false_alarms": 0,
                "healthy_block_false_alarm_rate": 0.0,
                "h1_empirical_pass": True,
                "fault_block_detection_rate": (
                    proposed_detection if method == PROPOSED_METHOD else 0.7
                ),
                "fault_record_macro_detection_rate": 0.5,
                "fault_record_any_alarm_rate": 0.8,
                "block_auroc": 0.75,
                "block_auprc": 0.9,
            }
        )
    return pd.DataFrame(rows)


def test_feature_pair_preserves_physical_time_and_profiles_shift() -> None:
    native, target = feature_frames()
    integrity = validate_feature_pair(native, target)
    shifts = feature_shift_summary(native, target, ["spectral_entropy"])
    assert integrity["rows"].tolist() == [4, 4]
    assert integrity["duplicate_window_keys"].sum() == 0
    assert shifts["median_absolute_delta"].tolist() == pytest.approx([0.25, 0.25])


def test_feature_pair_rejects_changed_labels() -> None:
    native, target = feature_frames()
    target.loc[0, "record_id"] = "different"
    with pytest.raises(ValueError, match="labels"):
        validate_feature_pair(native, target)


def test_external_comparison_separates_controls_and_source_methods() -> None:
    old = external_rows(0.25)
    new = external_rows(0.20)
    comparison = external_method_comparison(old, new).set_index("method")
    assert comparison.loc[PROPOSED_METHOD, "source_dependency"] == "source_sensitive"
    assert (
        comparison.loc[
            "target_min_cov_det", "source_dependency"
        ]
        == "target_only_invariant_control"
    )
    assert comparison.loc[
        PROPOSED_METHOD, "delta_fault_block_detection_rate_10khz_minus_100khz"
    ] == pytest.approx(-0.05)


def test_interpretation_is_explicitly_post_reveal(tmp_path: Path) -> None:
    comparison = external_method_comparison(external_rows(0.25), external_rows(0.24))
    internal = pd.DataFrame(
        {
            "method": [PROPOSED_METHOD],
            "detection_source_100khz": [0.95],
            "detection_source_10khz": [0.92],
            "auroc_source_100khz": [0.999],
            "auroc_source_10khz": [0.995],
        }
    )
    records = pd.DataFrame(
        {"delta_block_alarm_rate_10khz_minus_100khz": np.array([-0.1, 0.0, 0.2])}
    )
    output = tmp_path / "interpretation.md"
    write_interpretation(output, comparison, internal, records)
    text = output.read_text(encoding="utf-8")
    assert "POST-REVEAL SENSITIVITY" in text
    assert "does **not** support" in text
