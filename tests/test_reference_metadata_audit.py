from __future__ import annotations

from pathlib import Path

from scripts.audit_reference_metadata import (
    cited_keys,
    first_author_family,
    normalize_person,
    normalize_text,
    parse_bibtex,
    title_similarity,
)

ROOT = Path(__file__).resolve().parents[1]


def test_bibliography_parser_covers_every_cited_key() -> None:
    records = parse_bibtex(ROOT / "references" / "key_papers.bib")
    keys = cited_keys(ROOT / "paper" / "manuscript.md")
    assert len(keys) == 34
    assert set(keys) <= set(records)
    assert sum(bool(records[key].fields.get("doi")) for key in keys) == 32


def test_metadata_normalization_handles_bibtex_protection_and_punctuation() -> None:
    assert normalize_text("Diagnosis of {PMSM}s: A Review") == "diagnosis of pmsms a review"
    assert first_author_family("Barber, Rina Foygel and Pananjady, Ashwin") == "barber"
    assert first_author_family(r"Sch{\"o}lkopf, Bernhard") == "scholkopf"
    assert normalize_person("Schölkopf") == "scholkopf"
    assert title_similarity("Fault Diagnosis: A Study", "Fault diagnosis — a study") == 1.0
