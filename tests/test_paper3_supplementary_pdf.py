from __future__ import annotations

from scripts.build_paper3_supplementary_pdf import OUTPUT, SOURCE, audit


def test_paper3_supplement_source_is_present() -> None:
    assert SOURCE.is_file()
    assert SOURCE.stat().st_size > 10_000


def test_paper3_supplement_pdf_audit_when_present() -> None:
    if OUTPUT.is_file():
        result = audit()
        assert int(result["pages"]) >= 4
        assert result["author"] == "Anonymous"

