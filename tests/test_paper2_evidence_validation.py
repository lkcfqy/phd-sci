from __future__ import annotations

from pathlib import Path

import pytest

from scripts.validate_paper2_evidence import (
    recompute_primary,
    recompute_weighted,
    validate_manuscript_and_artifacts,
)

ROOT = Path(__file__).resolve().parents[1]


def test_primary_lower_grain_rows_reproduce_headline_and_sparse_tail() -> None:
    evidence = recompute_primary(ROOT)
    uniform = evidence["aggregate"]["uq_uniform"]
    assert uniform["global"]["coverage"] == pytest.approx(0.9029333333333334)
    assert uniform["geometry_scaled"]["coverage"] == pytest.approx(0.8996444444444445)
    assert evidence["uniform_sparse_quintile"]["global_coverage"] == pytest.approx(
        0.7613333333333333
    )
    assert evidence["uniform_sparse_quintile"][
        "geometry_scaled_coverage"
    ] == pytest.approx(0.7831111111111111)


def test_weighted_diagnostic_preserves_gaussian_vacuity() -> None:
    evidence = recompute_weighted(ROOT)
    assert evidence["uq_uniform"]["finite_bands"] == 5_625
    assert evidence["uq_uniform"]["finite_band_coverage"] == pytest.approx(
        0.9198222222222222
    )
    assert evidence["uq_gauss"]["finite_bands"] == 0
    assert evidence["uq_gauss"]["calibration_weight_ess"] == pytest.approx(
        4.3063191510830485
    )


def test_manuscript_citations_and_all_ten_figure_files_validate() -> None:
    evidence = validate_manuscript_and_artifacts(ROOT)
    assert evidence["manuscript_words"] > 4_500
    assert evidence["citation_count"] >= 10
    assert len(evidence["figure_files"]) == 10
