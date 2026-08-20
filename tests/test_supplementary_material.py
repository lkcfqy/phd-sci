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
    for section in range(1, 10):
        assert f"## S{section}." in generated
    assert "one physical motor" in generated
    assert "post-reveal" in generated.lower()
    assert "did not select a new model or threshold" in generated
    assert "frozen parser accepted 0/21 records" in generated
    assert "zero first-second detection" in generated


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


def test_secondary_transient_section_preserves_failure_and_null_result() -> None:
    generated = build_supplementary(ROOT)
    primary = pd.read_csv(
        ROOT / "results/transient_feature_build/record_compatibility.csv"
    )
    repaired = pd.read_csv(
        ROOT
        / "results/transient_feature_build_post_reveal_implicit_time/"
        "record_compatibility.csv"
    )
    aggregate = pd.read_csv(
        ROOT
        / "results/transient_pmsm_validation_post_reveal_200w/"
        "aggregate_summary.csv"
    )
    primary_seed = aggregate.loc[aggregate["seed"] == 20260820]
    assert len(primary) == 21
    assert not primary["main_endpoint_compatible"].astype(bool).any()
    assert repaired.groupby(["motor_id", "main_endpoint_compatible"]).size().to_dict() == {
        ("200W", True): 12,
        ("20kW", False): 5,
        ("20kW", True): 4,
    }
    assert len(primary_seed) == 12
    assert primary_seed["record_macro_detection_rate"].eq(0).all()
    assert primary_seed["fault_record_any_alarm_rate"].eq(0).all()
    assert "## S9. Prospectively logged secondary transient-set audit" in generated
