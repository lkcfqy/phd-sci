from __future__ import annotations

from pathlib import Path

import matplotlib.pyplot as plt
import pandas as pd
import pytest

from scripts.make_paper3_figures import read_summary, require_columns, save_figure


def test_require_columns_rejects_missing_fields() -> None:
    with pytest.raises(ValueError, match="missing columns"):
        require_columns(pd.DataFrame({"a": [1]}), {"a", "b"}, label="test")


def test_read_summary_accepts_nested_payload(tmp_path: Path) -> None:
    path = tmp_path / "summary.json"
    path.write_text('{"summary": {"records": 216}}', encoding="utf-8")
    assert read_summary(path) == {"records": 216}


def test_save_figure_writes_png_and_pdf(tmp_path: Path) -> None:
    figure, axis = plt.subplots()
    axis.plot([0, 1], [0, 1])
    save_figure(figure, tmp_path, "sample")
    assert (tmp_path / "sample.png").stat().st_size > 1000
    assert (tmp_path / "sample.pdf").stat().st_size > 1000
