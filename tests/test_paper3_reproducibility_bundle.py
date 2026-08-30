from __future__ import annotations

from scripts.build_paper3_reproducibility_bundle import (
    MANIFEST_OUT,
    ZIP_OUT,
    audit_bundle,
    bundle_sources,
)


def test_paper3_bundle_sources_exclude_signal_data() -> None:
    sources = bundle_sources()
    relatives = [str(path).replace("\\", "/").lower() for _, path in sources]
    assert sources
    assert not any("/data/raw/" in path or "/tmp/" in path for path in relatives)
    assert not any(path.endswith("features.csv.gz") for path in relatives)
    assert any(path.endswith("paper3_manuscript_anonymous.pdf") for path in relatives)
    assert any(path.endswith("paper3_supplementary_material.pdf") for path in relatives)


def test_generated_paper3_bundle_audits_when_present() -> None:
    if ZIP_OUT.is_file() and MANIFEST_OUT.is_file():
        result = audit_bundle()
        assert result["status"] == "pass"
        assert int(result["source_file_count"]) >= 60

