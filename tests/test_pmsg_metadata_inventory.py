from __future__ import annotations

import pytest

from scripts.freeze_pmsg_confirmation_metadata import parse_tree_line


def test_parse_tree_line_accepts_only_regular_blobs() -> None:
    line = (
        "100644 blob 0123456789012345678901234567890123456789\t"
        "PMSG-3phase-Dataset/HEALTHY_S1200_T52.mat"
    )
    object_id, path, name = parse_tree_line(line)
    assert object_id == "0123456789012345678901234567890123456789"
    assert path.endswith(name)
    assert name == "HEALTHY_S1200_T52.mat"
    with pytest.raises(ValueError, match="Unexpected"):
        parse_tree_line("040000 tree abc\tPMSG-3phase-Dataset")
