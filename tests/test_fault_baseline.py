import numpy as np
import pandas as pd
import pytest

from pmsm_sci.faults.baseline import (
    block_score_table,
    classifier_scores,
    feature_columns,
    healthy_relative_features,
    source_train_and_calibration_masks,
)
from pmsm_sci.faults.statistics import wilson_interval


def synthetic_frame() -> pd.DataFrame:
    rows = []
    for motor in ("1kW", "1.5kW"):
        for healthy in (True, False):
            for block in range(60):
                rows.append(
                    {
                        "motor_id": motor,
                        "record_id": f"{motor}_{healthy}",
                        "fault_family": "healthy" if healthy else "interturn",
                        "severity_percent": 0.0 if healthy else 2.0,
                        "is_healthy": healthy,
                        "block_id": block,
                        "window_id": block,
                        "motor_watts": 1_000,
                        "sequence_unbalance": block / 100,
                        "rms_a": 1.0,
                    }
                )
    return pd.DataFrame(rows)


def test_feature_selection_excludes_labels_and_scale_for_scale_free_arm() -> None:
    frame = synthetic_frame()
    all_features = feature_columns(frame, "all_features")
    scale_free = feature_columns(frame, "scale_free")
    assert "severity_percent" not in all_features
    assert "motor_watts" not in all_features
    assert "sequence_unbalance" in scale_free
    assert "rms_a" in all_features and "rms_a" not in scale_free


def test_source_health_calibration_does_not_overlap_training() -> None:
    frame = synthetic_frame()
    train, calibration = source_train_and_calibration_masks(frame, ["1kW"])
    assert not np.any(train & calibration)
    assert frame.loc[calibration, "is_healthy"].all()
    assert (frame.loc[calibration, "block_id"] >= 25).all()
    assert (~frame.loc[train & ~frame["is_healthy"].to_numpy(), "is_healthy"]).all()


def test_block_score_table_uses_one_row_per_record_block() -> None:
    frame = pd.concat([synthetic_frame().iloc[:2]] * 3, ignore_index=True)
    scores = np.asarray([0.1, 0.2, 0.8, 0.3, 0.7, 0.4])
    table = block_score_table(frame, scores)
    assert len(table) == 2
    assert sorted(table["score"].tolist()) == [0.4, 0.8]


def test_wilson_interval_is_finite_for_zero_false_alarms() -> None:
    lower, upper = wilson_interval(0, 42)
    assert lower == 0.0
    assert 0.08 < upper < 0.09


def test_classifier_scores_prefer_unsquashed_decision_function() -> None:
    class SaturatingClassifier:
        def decision_function(self, features):
            return features[:, 0] * 100

        def predict_proba(self, features):
            return np.ones((len(features), 2))

    values = classifier_scores(SaturatingClassifier(), np.asarray([[1.0], [2.0]]))
    assert values.tolist() == [100.0, 200.0]


def test_healthy_relative_features_remove_motor_offset_without_target_faults() -> None:
    frame = synthetic_frame()
    frame.loc[frame["motor_id"] == "1.5kW", "sequence_unbalance"] += 10.0
    values, parameters = healthy_relative_features(
        frame,
        ["sequence_unbalance"],
        {"1kW": range(10), "1.5kW": range(10)},
    )
    for motor in ("1kW", "1.5kW"):
        reference = (
            frame["motor_id"].eq(motor)
            & frame["is_healthy"]
            & frame["block_id"].isin(range(10))
        )
        assert np.median(values[reference.to_numpy(), 0]) == pytest.approx(0.0, abs=1e-12)
        assert motor in parameters
