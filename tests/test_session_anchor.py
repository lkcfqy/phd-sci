from __future__ import annotations

import numpy as np
import pytest

from pmsm_sci.faults.session_anchor import (
    SessionAnchoredDetector,
    session_residuals,
)


def test_session_anchor_removes_session_offset_and_detects_change() -> None:
    rng = np.random.default_rng(8)
    training = rng.normal(0.0, 0.1, size=(60, 3))
    detector = SessionAnchoredDetector().fit(training)
    anchor = np.asarray([[10.0, -4.0, 2.0], [10.1, -4.1, 2.0]])
    healthy = np.asarray([[10.05, -4.05, 2.02]])
    fault = np.asarray([[11.0, -4.05, 1.1]])
    healthy_score = detector.score(session_residuals(anchor, healthy))[0]
    fault_score = detector.score(session_residuals(anchor, fault))[0]
    assert fault_score > 10 * healthy_score


def test_session_anchor_requires_two_aligned_windows() -> None:
    with pytest.raises(ValueError, match="At least two"):
        session_residuals([[1.0, 2.0]], [[1.0, 2.0]])
    with pytest.raises(ValueError, match="dimensions differ"):
        session_residuals([[1.0], [2.0]], [[1.0, 2.0]])
