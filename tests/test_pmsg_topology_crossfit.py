from __future__ import annotations

import pandas as pd

from pmsm_sci.faults.pmsg_session import pmsg_topology_assignments


def test_topology_assignment_is_balanced_by_family() -> None:
    rows = []
    for family in ("turns", "windings"):
        for index in range(12):
            rows.append(
                {
                    "evaluation_role": "fault_test",
                    "fault_family": family,
                    "terminal_a": f"D{index + 1:02d}",
                    "terminal_b": f"D{index + 13:02d}",
                }
            )
    assignments = pmsg_topology_assignments(pd.DataFrame(rows))
    counts = assignments.groupby(["topology_bucket", "fault_family"]).size()
    assert counts.eq(4).all()
    assert assignments["topology_id"].nunique() == 24
