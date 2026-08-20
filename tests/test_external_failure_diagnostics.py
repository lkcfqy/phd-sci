import numpy as np
import pandas as pd
import pytest

from scripts.analyze_external_failure_diagnostics import (
    PROPOSED,
    block_auroc_diagnostics,
    first_alarm_records,
    holm_adjust,
    horizon_diagnostics,
    paired_bootstrap,
    score_speed_diagnostics,
)


def synthetic_blocks() -> pd.DataFrame:
    rows: list[dict[str, object]] = []
    methods = [PROPOSED, "target_min_cov_det"]
    for method in methods:
        for healthy, role, records in (
            (True, "health_test", ("h0", "h1")),
            (False, "fault_test", ("f0", "f1")),
        ):
            for record_index, record_id in enumerate(records):
                for block_id in range(8):
                    if healthy:
                        score = float(block_id + record_index * 0.01)
                        alarm = False
                        fault_turns = 0
                    else:
                        score = float(block_id + 10 + record_index)
                        if method == PROPOSED:
                            alarm = block_id == 7
                        else:
                            alarm = block_id >= 4
                        fault_turns = record_index + 1
                    rows.append(
                        {
                            "method": method,
                            "record_id": record_id,
                            "load_nm": record_index * 5,
                            "block_id": block_id,
                            "score": score,
                            "is_healthy": healthy,
                            "fault_turns": fault_turns,
                            "fault_phase": "u" if not healthy else np.nan,
                            "role": role,
                            "alarm": alarm,
                            "approx_speed_rpm_min": 100.0 * block_id,
                            "approx_speed_rpm_median": 100.0 * block_id + 50.0,
                            "approx_speed_rpm_max": 100.0 * block_id + 100.0,
                        }
                    )
    return pd.DataFrame(rows)


def test_horizon_diagnostics_distinguishes_detection_from_record_any() -> None:
    blocks = synthetic_blocks()
    table = horizon_diagnostics(blocks)
    proposed = table[table["method"].eq(PROPOSED)].set_index("horizon")
    assert proposed.loc["first_4_blocks", "fault_block_detection_rate"] == 0.0
    assert proposed.loc["first_7_blocks", "fault_record_any_alarm_rate"] == 0.0
    assert proposed.loc["all_8_blocks", "fault_block_detection_rate"] == pytest.approx(1 / 8)
    assert proposed.loc["all_8_blocks", "fault_record_any_alarm_rate"] == 1.0


def test_first_alarm_uses_health_derived_speed_proxy() -> None:
    first = first_alarm_records(synthetic_blocks())
    proposed = first[first["method"].eq(PROPOSED)]
    assert proposed["first_alarm_block_id"].eq(7).all()
    assert proposed["first_alarm_start_seconds"].eq(33.0).all()
    assert proposed["first_alarm_approx_rpm_median"].eq(750.0).all()
    target = first[first["method"].eq("target_min_cov_det")]
    assert target["first_alarm_block_id"].eq(4).all()


def test_block_auroc_is_computed_at_each_matched_position() -> None:
    per_block, summary = block_auroc_diagnostics(synthetic_blocks())
    assert len(per_block) == 16
    assert per_block["block_matched_auroc"].eq(1.0).all()
    assert summary["equal_weight_mean_block_auroc"].eq(1.0).all()


def test_score_speed_diagnostics_preserves_population_boundary() -> None:
    summary, records = score_speed_diagnostics(synthetic_blocks())
    assert len(summary) == 4
    assert len(records) == 8
    assert summary["pooled_spearman_block_score"].gt(0.97).all()
    assert summary["record_spearman_median"].eq(1.0).all()
    assert not summary["inference_valid"].any()


def test_paired_bootstrap_and_holm_are_deterministic() -> None:
    differences = np.asarray([0.25, 0.5, 0.25, 0.5])
    strata = np.asarray([1, 1, 2, 2])
    first = paired_bootstrap(differences, strata, iterations=500, seed=711)
    second = paired_bootstrap(differences, strata, iterations=500, seed=711)
    assert first == second
    assert first["mean_difference"] == pytest.approx(0.375)
    adjusted = holm_adjust(np.asarray([0.01, 0.04, 0.03]))
    assert adjusted == pytest.approx([0.03, 0.06, 0.06])
