from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

from scripts.make_external_validation_figures import (
    PROPOSED,
    analysis_speed_by_block,
    configure_style,
    plot_condition_drift,
    plot_method_performance,
    plot_proposed_heatmap,
    prepare_method_performance,
    prepare_proposed_heatmap,
    summarize_condition_drift,
)


def synthetic_performance() -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "method": "target_min_cov_det",
                "faults_available": True,
                "fault_records": 48,
                "fault_blocks": 384,
                "fault_block_detection_rate": 0.70,
                "record_bootstrap_detection_ci_lower": 0.65,
                "record_bootstrap_detection_ci_upper": 0.75,
                "health_test_records": 4,
                "health_test_blocks": 32,
                "healthy_block_false_alarm_rate": 0.0,
                "descriptive_wilson_lower": 0.0,
                "descriptive_wilson_upper": 0.107,
                "max_heldout_load_false_alarm_rate": 0.0,
                "h1_empirical_pass": True,
            },
            {
                "method": PROPOSED,
                "faults_available": True,
                "fault_records": 48,
                "fault_blocks": 384,
                "fault_block_detection_rate": 0.25,
                "record_bootstrap_detection_ci_lower": 0.21,
                "record_bootstrap_detection_ci_upper": 0.29,
                "health_test_records": 4,
                "health_test_blocks": 32,
                "healthy_block_false_alarm_rate": 0.03125,
                "descriptive_wilson_lower": 0.006,
                "descriptive_wilson_upper": 0.157,
                "max_heldout_load_false_alarm_rate": 0.125,
                "h1_empirical_pass": False,
            },
            {
                "method": "target_isolation_forest",
                "faults_available": True,
                "fault_records": 48,
                "fault_blocks": 384,
                "fault_block_detection_rate": 0.60,
                "record_bootstrap_detection_ci_lower": 0.57,
                "record_bootstrap_detection_ci_upper": 0.63,
                "health_test_records": 4,
                "health_test_blocks": 32,
                "healthy_block_false_alarm_rate": 0.09375,
                "descriptive_wilson_lower": 0.032,
                "descriptive_wilson_upper": 0.242,
                "max_heldout_load_false_alarm_rate": 0.125,
                "h1_empirical_pass": False,
            },
        ]
    )


def synthetic_predictions() -> pd.DataFrame:
    rows: list[dict[str, object]] = []
    threshold = 100.0
    for block in range(8):
        for record in range(3):
            score = 50 + 18 * block + 3 * record
            rows.append(
                {
                    "record_id": f"fault_{record}",
                    "block_id": block,
                    "score": score,
                    "is_healthy": False,
                    "role": "fault_test",
                    "alarm": score > threshold,
                    "method": PROPOSED,
                }
            )
        for record in range(2):
            score = 35 + 8 * block + record
            rows.append(
                {
                    "record_id": f"health_test_{record}",
                    "block_id": block,
                    "score": score,
                    "is_healthy": True,
                    "role": "health_test",
                    "alarm": score > threshold,
                    "method": PROPOSED,
                }
            )
        rows.append(
            {
                "record_id": "adaptation_health",
                "block_id": block,
                "score": 10_000.0,
                "is_healthy": True,
                "role": "adaptation",
                "alarm": True,
                "method": PROPOSED,
            }
        )
    return pd.DataFrame(rows)


def synthetic_record_summary() -> pd.DataFrame:
    phases = {1: "u", 2: "v", 3: "u", 4: "v", 5: "u", 6: "u"}
    rows: list[dict[str, object]] = []
    for turns in range(1, 7):
        for load in range(0, 36, 5):
            alarms = min(8, max(1, turns + (35 - load) // 10))
            rows.append(
                {
                    "record_id": f"turns_{turns}_load_{load}",
                    "load_nm": load,
                    "fault_turns": turns,
                    "fault_phase": phases[turns],
                    "blocks": 8,
                    "alarms": alarms,
                    "block_alarm_rate": alarms / 8,
                }
            )
    return pd.DataFrame(rows)


def test_data_preparation_preserves_leader_h1_and_heldout_scope() -> None:
    performance = prepare_method_performance(synthetic_performance())
    assert performance.iloc[0]["method"] == "target_min_cov_det"
    assert performance.iloc[0]["h1_empirical_pass"]
    assert not performance.loc[performance["method"].eq(PROPOSED), "h1_empirical_pass"].item()

    drift = summarize_condition_drift(synthetic_predictions())
    health = drift[drift["condition"].eq("Held-out health")]
    fault = drift[drift["condition"].eq("Fault")]
    assert health["records"].eq(2).all()
    assert health["observations"].eq(2).all()
    assert fault["records"].eq(3).all()
    assert health["score_median"].max() < 100.0


def test_speed_mapping_and_complete_heatmap() -> None:
    inventory = pd.DataFrame(
        {
            "block_id": np.repeat(np.arange(4, 12), 2),
            "speed_rpm_median": np.repeat(np.linspace(220, 2_220, 8), 2),
            "inside_frozen_12_36s_segment": True,
        }
    )
    speed = analysis_speed_by_block(inventory)
    assert tuple(speed.index) == tuple(range(8))
    assert np.all(np.diff(speed) > 0)

    heatmap = prepare_proposed_heatmap(synthetic_record_summary())
    assert heatmap.rates.shape == (6, 8)
    assert heatmap.loads == tuple(range(0, 36, 5))
    assert heatmap.phase_labels == ("1 (u)", "2 (v)", "3 (u)", "4 (v)", "5 (u)", "6 (u)")


def test_all_static_figure_pairs_are_written(tmp_path: Path) -> None:
    configure_style()
    performance = prepare_method_performance(synthetic_performance())
    drift = summarize_condition_drift(synthetic_predictions())
    speed = pd.Series(np.linspace(220, 2_220, 8), index=range(8))
    heatmap = prepare_proposed_heatmap(synthetic_record_summary())

    outputs = [
        *plot_method_performance(performance, tmp_path),
        *plot_condition_drift(
            drift,
            threshold=100.0,
            speed_by_block=speed,
            output_dir=tmp_path,
        ),
        *plot_proposed_heatmap(heatmap, tmp_path),
    ]
    assert len(outputs) == 6
    for output in outputs:
        assert output.exists()
        assert output.stat().st_size > 5_000
        signature = output.read_bytes()[:8]
        if output.suffix == ".png":
            assert signature == b"\x89PNG\r\n\x1a\n"
        else:
            assert signature.startswith(b"%PDF")
