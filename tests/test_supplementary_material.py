from pathlib import Path

import pandas as pd
import pytest

from scripts.build_supplementary_material import (
    build_supplementary,
    markdown_table,
)

ROOT = Path(__file__).resolve().parents[1]


def test_markdown_table_rejects_mismatched_rows() -> None:
    with pytest.raises(ValueError, match="header"):
        markdown_table(["a", "b"], [[1]])


def test_supplementary_material_is_current_and_complete() -> None:
    generated = build_supplementary(ROOT)
    checked_in = (ROOT / "paper/supplementary_material.md").read_text(
        encoding="utf-8"
    )
    assert generated == checked_in
    for section in range(1, 9):
        assert f"## S{section}." in generated
    assert "one physical motor" in generated
    assert "post-reveal" in generated.lower()
    assert "did not select a new model or threshold" in generated


def test_external_table_values_are_rendered_from_frozen_csv() -> None:
    generated = build_supplementary(ROOT)
    summary = pd.read_csv(
        ROOT / "results/external_pmsm_validation/aggregate_summary.csv"
    ).set_index("method")
    proposed = summary.loc["log_euclidean_entity_covariance"]
    min_cov = summary.loc["target_min_cov_det"]
    assert f"{100 * proposed['fault_block_detection_rate']:.2f}%" in generated
    assert f"{100 * min_cov['fault_block_detection_rate']:.2f}%" in generated
    assert min_cov["fault_block_detection_rate"] > proposed[
        "fault_block_detection_rate"
    ]


def test_supplement_has_full_requested_table_families() -> None:
    paired = pd.read_csv(
        ROOT / "results/external_failure_diagnostics/paired_vs_proposed.csv"
    )
    transfer = pd.read_csv(
        ROOT / "results/external_failure_diagnostics/target_vs_source_transfer.csv"
    )
    blocks = pd.read_csv(
        ROOT / "results/external_failure_diagnostics/block_auroc.csv"
    )
    seeds = pd.read_csv(
        ROOT / "results/external_seed_sensitivity/aggregate_seed_ranges.csv"
    )
    assert (len(paired), len(transfer), len(blocks), len(seeds)) == (10, 5, 88, 4)
    assert paired["holm_family_size"].eq(10).all()
    assert transfer["holm_family_size"].eq(5).all()
    assert seeds["seeds"].eq(5).all()
