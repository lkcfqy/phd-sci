import numpy as np
import pandas as pd
import pytest

from scripts.analyze_external_feature_drift import (
    feature_family,
    same_block_feature_effects,
    symmetric_mahalanobis_contributions,
)


def test_symmetric_contributions_sum_to_quadratic_score() -> None:
    values = np.asarray([[2.0, -1.0], [1.0, 3.0]])
    precision = np.asarray([[2.0, 1.0], [1.0, 3.0]])
    scores, contributions = symmetric_mahalanobis_contributions(values, precision)
    expected = np.einsum("ij,jk,ik->i", values, precision, values)
    assert scores == pytest.approx(expected)
    assert contributions.sum(axis=1) == pytest.approx(expected)
    assert contributions[0].tolist() == pytest.approx([6.0, 1.0])


def test_symmetric_contributions_reject_nonsymmetric_precision() -> None:
    with pytest.raises(ValueError, match="symmetric"):
        symmetric_mahalanobis_contributions(
            np.ones((2, 2)), np.asarray([[1.0, 2.0], [0.0, 1.0]])
        )


def test_feature_family_covers_priority_groups() -> None:
    assert feature_family("fundamental_hz") == "speed_proxy"
    assert feature_family("spectral_entropy") == "spectral_entropy"
    assert feature_family("harmonic_3_ratio_mean") == "harmonic_sideband"
    assert feature_family("sequence_unbalance") == "sequence_imbalance"
    assert feature_family("kurtosis_a") == "current_shape"


def _unit_rows() -> pd.DataFrame:
    rows = []
    for block in range(8):
        for load in (5, 15, 25, 35):
            for subsystem in ("SubSys1", "SubSys2"):
                rows.append(
                    {
                        "record_id": f"health_{load}",
                        "load_nm": load,
                        "subsystem": subsystem,
                        "block_id": block,
                        "is_healthy": True,
                        "fault_turns": 0,
                        "fault_phase": "none",
                        "role": "health_test",
                        "motor_id": "one_motor",
                        "windows": 15,
                        "feature": "spectral_entropy",
                        "raw_value": float(block),
                        "robust_z_value": float(block),
                        "speed_proxy_hz": float(30 + 40 * block),
                        "feature_family": "spectral_entropy",
                        "health_population": "healthy_health_test",
                    }
                )
                for turns in range(1, 7):
                    rows.append(
                        {
                            "record_id": f"fault_{turns}_{load}",
                            "load_nm": load,
                            "subsystem": subsystem,
                            "block_id": block,
                            "is_healthy": False,
                            "fault_turns": turns,
                            "fault_phase": "u",
                            "role": "fault_test",
                            "motor_id": "one_motor",
                            "windows": 15,
                            "feature": "spectral_entropy",
                            "raw_value": float(block + 1),
                            "robust_z_value": float(block + 1),
                            "speed_proxy_hz": float(30 + 40 * block),
                            "feature_family": "spectral_entropy",
                            "health_population": "fault",
                        }
                    )
    return pd.DataFrame(rows)


def test_same_block_effect_detects_complete_single_feature_separation() -> None:
    effects = same_block_feature_effects(_unit_rows())
    row = effects[
        effects["scope"].eq("heldout_health_test_loads")
        & effects["block_id"].eq(3)
    ].iloc[0]
    assert row["healthy_units"] == 8
    assert row["fault_units"] == 48
    assert row["matched_fault_health_pairs"] == 48
    assert row["raw_single_feature_auc_fault_higher"] == pytest.approx(1.0)
    assert row["matched_raw_difference_mean"] == pytest.approx(1.0)


def test_same_block_matching_rejects_duplicate_health_unit() -> None:
    units = _unit_rows()
    duplicate = units[units["is_healthy"]].iloc[[0]]
    with pytest.raises(AssertionError, match="one health unit"):
        same_block_feature_effects(pd.concat([units, duplicate], ignore_index=True))
