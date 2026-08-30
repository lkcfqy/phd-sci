from __future__ import annotations

from scripts.build_paper2_reproducibility_bundle import (
    ZIP_OUT,
    audit_bundle,
    source_manifest,
)


def test_bundle_inventory_is_complete_and_excludes_raw_data() -> None:
    manifest = source_manifest()
    paths = {item["path"] for item in manifest["files"]}
    assert manifest["raw_data_included"] is False
    assert not any(path.startswith("data/raw/") for path in paths)
    assert "papers/paper2_torque_uq/manuscript.md" in paths
    assert "papers/paper2_torque_uq/supplementary_material.md" in paths
    assert "papers/paper2_torque_uq/README_REPRODUCE.md" in paths
    assert "papers/paper2_torque_uq/SUBMISSION_CHECKLIST.md" in paths
    assert (
        "papers/paper2_torque_uq/submission/Paper2_Supplementary_Material.pdf"
        in paths
    )
    assert "scripts/build_paper2_supplementary_pdf.py" in paths
    assert "scripts/validate_paper2_evidence.py" in paths
    assert "src/pmsm_sci/torque/conformal.py" in paths
    assert "results/paper2_evidence_validation/evidence.json" in paths
    assert "results/paper2_torque_conformal/primary_per_design_scores.csv.gz" in paths
    assert "results/paper2_weighted_conformal/weighted_per_design.csv.gz" in paths
    assert manifest["file_count"] >= 60


def test_built_bundle_passes_member_hash_audit_when_present() -> None:
    if ZIP_OUT.is_file():
        result = audit_bundle()
        assert result["status"] == "pass"
        assert result["source_file_count"] >= 60
