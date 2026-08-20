from __future__ import annotations

import hashlib
import json
import re
import zipfile
from pathlib import Path
from xml.etree import ElementTree

ROOT = Path(__file__).resolve().parents[1]
SUBMISSION = ROOT / "submission" / "jeet"
WORD_NS = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"


def digest(path: Path) -> str:
    value = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            value.update(chunk)
    return value.hexdigest()


def xml_text(archive: zipfile.ZipFile, member: str) -> str:
    root = ElementTree.fromstring(archive.read(member))
    return "".join(root.itertext())


def test_source_meets_jeet_abstract_keyword_and_resource_requirements() -> None:
    text = (ROOT / "paper" / "manuscript.md").read_text(encoding="utf-8")
    normalized = " ".join(text.split())
    abstract = text.split("## Abstract", 1)[1].split("**Keywords:**", 1)[0]
    abstract_words = re.findall(r"[A-Za-z0-9]+(?:[.-][A-Za-z0-9]+)*", abstract)
    keywords = text.split("**Keywords:**", 1)[1].split("##", 1)[0].replace("\n", " ").split(";")
    assert len(abstract_words) == 247
    assert len([keyword for keyword in keywords if keyword.strip()]) == 6
    assert "Online Resource 1" in normalized
    assert "Online Resource 2" in normalized
    assert "## Statements and declarations" in text


def test_package_contains_every_expected_submission_artifact() -> None:
    expected = {
        "Manuscript_Anonymous.docx",
        "Manuscript_Anonymous.pdf",
        "Title_Page_AUTHOR_INPUT_REQUIRED.docx",
        "Cover_Letter_AUTHOR_INPUT_REQUIRED.docx",
        "ESM_1_Supplementary_Material.pdf",
        "ESM_2_Reproducibility_Code.zip",
        "Submission_Checklist.md",
        "author_metadata_REQUIRED.yaml",
        "build_metadata.json",
        "QA_Report.md",
        "README.md",
    }
    assert expected <= {path.name for path in SUBMISSION.iterdir()}
    figure_names = {path.name for path in (SUBMISSION / "figures").iterdir()}
    assert figure_names == {
        f"Fig{number}.{extension}" for number in range(1, 12) for extension in ("pdf", "png")
    }


def test_anonymous_manuscript_docx_has_expected_structure_and_no_identity() -> None:
    path = SUBMISSION / "Manuscript_Anonymous.docx"
    with zipfile.ZipFile(path) as archive:
        names = set(archive.namelist())
        document_xml = archive.read("word/document.xml")
        document = ElementTree.fromstring(document_xml)
        visible = "".join(document.itertext())
        core = xml_text(archive, "docProps/core.xml")
        footer = xml_text(archive, "word/footer1.xml")
        styles = archive.read("word/styles.xml").decode("utf-8")

        assert core.count("Anonymous") >= 2
        assert "When Healthy-Only Transfer Fails" in visible
        assert "Abstract" in visible
        assert "References" in visible
        assert "Online Resource 2" in visible
        assert "Development draft" not in visible
        assert len(document.findall(f".//{{{WORD_NS}}}tbl")) == 3
        assert len([name for name in names if name.startswith("word/media/")]) == 11
        descriptions = [
            value
            for element in document.iter()
            for key, value in element.attrib.items()
            if key.endswith("descr")
        ]
        assert len(descriptions) == 11
        assert all(description.strip() for description in descriptions)
        assert "PAGE" in footer
        assert "Times New Roman" in styles

        lowered_xml = document_xml.lower()
        for forbidden in (
            b"author input required",
            b"c:\\users",
            b"c:/users",
            b"lkcfq",
            b"changwon",
        ):
            assert forbidden not in lowered_xml


def test_title_page_and_cover_letter_remain_explicit_human_input_templates() -> None:
    expectations = {
        "Title_Page_AUTHOR_INPUT_REQUIRED.docx": (
            "AUTHOR INPUT REQUIRED",
            "FULL NAME",
            "ORCID",
            "CRediT",
        ),
        "Cover_Letter_AUTHOR_INPUT_REQUIRED.docx": (
            "AUTHOR INPUT REQUIRED",
            "CORRESPONDING AUTHOR NAME",
            "Sincerely",
        ),
    }
    for name, required in expectations.items():
        with zipfile.ZipFile(SUBMISSION / name) as archive:
            visible = xml_text(archive, "word/document.xml")
            core = xml_text(archive, "docProps/core.xml")
        assert "AUTHOR INPUT REQUIRED" in core
        for token in required[1:]:
            assert token in visible


def test_review_pdfs_have_anonymous_metadata_and_expected_page_counts() -> None:
    expected = {
        "Manuscript_Anonymous.pdf": 16,
        "ESM_1_Supplementary_Material.pdf": 6,
    }
    for name, pages in expected.items():
        data = (SUBMISSION / name).read_bytes()
        assert data.startswith(b"%PDF-")
        assert b"/Author (Anonymous)" in data
        assert len(re.findall(rb"/Type\s*/Page\b", data)) == pages
        assert len(data) > 100_000


def test_reproducibility_bundle_is_installable_shaped_hash_locked_and_anonymous() -> None:
    bundle = SUBMISSION / "ESM_2_Reproducibility_Code.zip"
    with zipfile.ZipFile(bundle) as archive:
        names = archive.namelist()
        assert "README.md" in names
        assert "README_ANONYMOUS.md" in names
        assert "pyproject.toml" in names
        assert "src/pmsm_sci/faults/external_validation.py" in names
        assert "docs/external_validation_protocol.md" in names
        assert "MANIFEST_SHA256.json" in names
        assert not any(name.startswith("data/raw/") for name in names)
        assert not any(name.startswith("data/processed/") for name in names)
        assert not any(name.startswith("submission/") for name in names)
        assert not any(".git" in name.split("/") for name in names)
        assert not any("egg-info" in name or "__pycache__" in name for name in names)
        assert not any(Path(name).name.startswith("build_jeet_") for name in names)
        assert "tests/test_jeet_submission.py" not in names

        manifest = json.loads(archive.read("MANIFEST_SHA256.json"))
        manifest_names = {entry["path"] for entry in manifest}
        assert manifest_names == set(names) - {"MANIFEST_SHA256.json"}
        for entry in manifest:
            assert hashlib.sha256(archive.read(entry["path"])).hexdigest() == entry["sha256"]

        for name in names:
            if name.endswith("/"):
                continue
            data = archive.read(name).lower()
            for forbidden in (b"c:\\users", b"c:/users", b"lkcfq", b"changwon national"):
                assert forbidden not in data


def test_build_metadata_matches_final_binary_artifacts() -> None:
    metadata = json.loads((SUBMISSION / "build_metadata.json").read_text(encoding="utf-8"))
    assert metadata["source_audit"] == {
        "abstract_words": 247,
        "cited_bibliography_entries": 33,
        "figure_citations": list(range(1, 12)),
        "keywords": 6,
        "table_citations": [1, 2, 3],
    }
    assert metadata["manuscript"]["figures"] == 11
    assert metadata["manuscript"]["tables"] == 3
    assert metadata["supplement_intermediate"]["tables"] == 14
    assert metadata["pdfs"]["manuscript"]["pages"] == 16
    assert metadata["pdfs"]["supplement"]["pages"] == 6
    assert metadata["manuscript"]["sha256"] == digest(SUBMISSION / "Manuscript_Anonymous.docx")
    assert metadata["reproducibility_bundle"]["sha256"] == digest(
        SUBMISSION / "ESM_2_Reproducibility_Code.zip"
    )
    assert metadata["pdfs"]["manuscript"]["sha256"] == digest(
        SUBMISSION / "Manuscript_Anonymous.pdf"
    )
    assert metadata["pdfs"]["supplement"]["sha256"] == digest(
        SUBMISSION / "ESM_1_Supplementary_Material.pdf"
    )
    for figure in metadata["figures"]:
        assert figure["pdf_sha256"] == digest(SUBMISSION / "figures" / figure["pdf"])
        assert figure["png_sha256"] == digest(SUBMISSION / "figures" / figure["png"])
        assert figure["png_dpi"] >= 299


def test_human_only_gates_are_not_marked_complete() -> None:
    checklist = (SUBMISSION / "Submission_Checklist.md").read_text(encoding="utf-8")
    human_section = checklist.split("## Human approval required", 1)[1].split("## Cost warning", 1)[
        0
    ]
    assert "- [x]" not in human_section
    assert human_section.count("- [ ]") == 10
    metadata_template = (SUBMISSION / "author_metadata_REQUIRED.yaml").read_text(encoding="utf-8")
    assert metadata_template.count("REQUIRED") >= 4
