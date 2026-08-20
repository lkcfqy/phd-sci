from __future__ import annotations

from pathlib import Path

import pytest

from scripts.validate_manuscript_evidence import (
    recompute_external,
    recompute_kaist,
    recompute_transient,
    wilson_interval,
)

ROOT = Path(__file__).resolve().parents[1]


def test_wilson_interval_reproduces_external_health_bounds() -> None:
    lower, upper = wilson_interval(1, 32)
    assert lower == pytest.approx(0.0055378601640031)
    assert upper == pytest.approx(0.1574426382001255)


def test_lower_grain_frozen_results_reproduce_headline_evidence() -> None:
    kaist = recompute_kaist(ROOT)
    external = recompute_external(ROOT)
    transient = recompute_transient(ROOT)
    assert kaist["proposed"]["false_alarms"] == 0
    assert external["proposed"]["false_alarms"] == 1
    assert external["target_min_cov_det"]["false_alarms"] == 0
    assert external["fault_turn_phase_fully_crossed"] is False
    assert transient["primary_parser_compatible"] == 0
