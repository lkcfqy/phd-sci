import numpy as np
import pandas as pd
import pytest

from pmsm_sci.faults.oneclass import (
    METHOD_SPECS,
    build_oneclass_estimator,
    independent_training_columns,
    motor_balanced_reference_mask,
    oneclass_anomaly_scores,
    stratified_record_bootstrap_interval,
)


def test_method_specs_include_target_and_balanced_versions() -> None:
    assert len(METHOD_SPECS) == 6
    assert {spec.training_scope for spec in METHOD_SPECS} == {
        "target",
        "source_target_balanced",
    }
    assert {spec.estimator_kind for spec in METHOD_SPECS} == {
        "ocsvm",
        "isolation_forest",
        "min_cov_det",
    }


def test_ocsvm_score_is_oriented_toward_anomaly() -> None:
    rng = np.random.default_rng(4)
    healthy = rng.normal(0, 0.15, size=(80, 2))
    model = build_oneclass_estimator("ocsvm", seed=9)
    model.fit(healthy)
    scores = oneclass_anomaly_scores(model, "ocsvm", [[0.0, 0.0], [5.0, 5.0]])
    assert scores[1] > scores[0]


def test_motor_balancing_selects_complete_evenly_spaced_blocks() -> None:
    rows = []
    for motor, n_blocks in [("source", 6), ("target", 2)]:
        for block in range(n_blocks):
            for window in range(3):
                rows.append(
                    {
                        "motor_id": motor,
                        "is_healthy": True,
                        "block_id": block,
                        "window_id": window,
                    }
                )
    rows.append(
        {"motor_id": "source", "is_healthy": False, "block_id": 0, "window_id": 0}
    )
    frame = pd.DataFrame(rows)
    mask = motor_balanced_reference_mask(
        frame, {"source": list(range(6)), "target": [0, 1]}
    )
    selected = frame.loc[mask]
    counts = selected.groupby("motor_id").size().to_dict()
    assert counts == {"source": 6, "target": 6}
    assert selected["is_healthy"].all()
    assert set(selected.loc[selected["motor_id"].eq("source"), "block_id"]) == {0, 5}


def test_record_bootstrap_is_deterministic_and_bounded() -> None:
    records = pd.DataFrame(
        {
            "motor_id": ["a", "a", "b", "b"],
            "detection_rate": [0.2, 0.4, 0.6, 0.8],
        }
    )
    first = stratified_record_bootstrap_interval(
        records, value_column="detection_rate", iterations=500, seed=3
    )
    second = stratified_record_bootstrap_interval(
        records, value_column="detection_rate", iterations=500, seed=3
    )
    assert first == second
    assert 0.2 <= first[0] <= first[1] <= 0.8


def test_independent_columns_remove_constant_and_exact_relation() -> None:
    values = np.asarray(
        [
            [1.0, 0.0, 0.0, 4.0],
            [1.0, 1.0, 2.0, 4.0],
            [1.0, 2.0, 4.0, 3.0],
            [1.0, 3.0, 6.0, 7.0],
        ]
    )
    selected = independent_training_columns(values)
    centered = values[:, selected] - values[:, selected].mean(axis=0)
    assert len(selected) == 2
    assert np.linalg.matrix_rank(centered) == 2


def test_invalid_oneclass_kind_is_rejected() -> None:
    with pytest.raises(ValueError, match="Unknown estimator"):
        build_oneclass_estimator("not-a-model", seed=1)  # type: ignore[arg-type]
