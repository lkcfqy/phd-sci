from __future__ import annotations

import numpy as np
import pandas as pd

from pmsm_sci.faults.paper3 import PAPER3_OUTCOME_FEATURES
from pmsm_sci.faults.pmsg_session import pmsg_session_residual_table


def test_residual_table_uses_two_anchor_windows_per_health_record() -> None:
    rows = []
    for window in range(13):
        row = {
            "record_id": "healthy",
            "is_healthy_file": True,
            "standalone_role": "fit",
            "segment": "health_analysis",
            "segment_window_id": window,
            "start_time_s": 0.2 + 0.2 * window,
            "stop_time_s": 0.4 + 0.2 * window,
        }
        row.update({column: float(window) for column in PAPER3_OUTCOME_FEATURES})
        rows.append(row)
    result = pmsg_session_residual_table(
        pd.DataFrame(rows), expected_roles={"fit": 11}
    )
    assert len(result) == 11
    assert result["anchor_start_time_s"].eq(0.2).all()
    assert np.allclose(result["anchor_stop_time_s"], 0.6)
    assert result[f"residual__{PAPER3_OUTCOME_FEATURES[0]}"].iloc[0] == 1.5
