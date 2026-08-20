from __future__ import annotations

from pathlib import Path

import matplotlib.image as mpimg
import numpy as np
import pandas as pd
import pytest

from scripts.make_external_feature_geometry_figure import (
    EXPECTED_FEATURE_COUNT,
    FEATURE_ORDER,
    FOCAL_FREQUENCY,
    FOCAL_HARMONIC,
    configure_style,
    plot_feature_geometry,
    prepare_feature_geometry,
)


def synthetic_summary() -> pd.DataFrame:
    filler_count = EXPECTED_FEATURE_COUNT - len(FEATURE_ORDER)
    features = [*FEATURE_ORDER, *(f"filler_{index}" for index in range(filler_count))]
    fault_weights = np.ones(EXPECTED_FEATURE_COUNT)
    health_weights = np.ones(EXPECTED_FEATURE_COUNT)
    fault_weights[features.index(FOCAL_FREQUENCY)] = 10.0
    health_weights[features.index(FOCAL_FREQUENCY)] = 12.0
    fault_weights /= fault_weights.sum()
    health_weights /= health_weights.sum()

    rows: list[dict[str, object]] = []
    for index, feature in enumerate(features):
        auc = 0.61 + index / 1_000
        if feature == FOCAL_HARMONIC:
            auc = 0.93
        elif feature == FOCAL_FREQUENCY:
            auc = 0.505
        rows.append(
            {
                "scope": "heldout_health_test_loads",
                "feature": feature,
                "block_id": -1,
                "independent_motors": 1,
                "healthy_units": 64,
                "fault_units": 384,
                "matched_fault_health_pairs": 384,
                "raw_direction_free_auc": auc,
                "matched_raw_dz": -0.2 if feature == "zero_sequence_ratio" else 0.7,
                "auroc_inferential_claimed": False,
                "fault_absolute_contribution_share": fault_weights[index],
                "healthy_test_absolute_contribution_share": health_weights[index],
            }
        )
    return pd.DataFrame(rows)


def test_prepare_feature_geometry_preserves_order_and_focal_mismatch() -> None:
    prepared = prepare_feature_geometry(synthetic_summary())
    assert tuple(prepared["feature"]) == FEATURE_ORDER
    harmonic = prepared.loc[prepared["feature"].eq(FOCAL_HARMONIC)].iloc[0]
    frequency = prepared.loc[prepared["feature"].eq(FOCAL_FREQUENCY)].iloc[0]
    assert harmonic["raw_direction_free_auc"] > frequency["raw_direction_free_auc"]
    assert (
        harmonic["fault_absolute_contribution_share"]
        < frequency["fault_absolute_contribution_share"]
    )
    assert prepared.loc[
        prepared["feature"].eq("zero_sequence_ratio"), "absolute_matched_dz"
    ].item() == pytest.approx(0.2)


def test_prepare_feature_geometry_enforces_single_motor_and_complete_shares() -> None:
    multiple_motors = synthetic_summary()
    multiple_motors.loc[0, "independent_motors"] = 2
    with pytest.raises(ValueError, match="single-motor"):
        prepare_feature_geometry(multiple_motors)

    incomplete = synthetic_summary()
    incomplete.loc[0, "fault_absolute_contribution_share"] = 0.0
    with pytest.raises(ValueError, match="sum to one"):
        prepare_feature_geometry(incomplete)


def test_static_feature_geometry_pair_is_written(tmp_path: Path) -> None:
    configure_style()
    prepared = prepare_feature_geometry(synthetic_summary())
    png, pdf = plot_feature_geometry(prepared, tmp_path)

    assert png.exists() and png.stat().st_size > 25_000
    assert pdf.exists() and pdf.stat().st_size > 8_000
    assert png.read_bytes()[:8] == b"\x89PNG\r\n\x1a\n"
    assert pdf.read_bytes()[:4] == b"%PDF"
    image = mpimg.imread(png)
    assert image.shape[1] > image.shape[0]
    assert image.shape[1] >= 2_500
    assert image.shape[0] >= 1_500
