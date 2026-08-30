from __future__ import annotations

from pathlib import Path

from scripts.build_paper2_submission import (
    DISPLAY_EQUATIONS,
    audit_docx,
    display_equation,
    parse_markdown,
)

ROOT = Path(__file__).resolve().parents[1]


def test_paper2_markdown_parser_finds_complete_submission_structure() -> None:
    title, blocks = parse_markdown(ROOT / "papers" / "paper2_torque_uq" / "manuscript.md")
    assert title.startswith("Curvewise Conformal Prediction Bands")
    assert sum(block.kind == "image" for block in blocks) == 5
    assert sum(block.kind == "table" for block in blocks) == 5
    assert sum(block.kind == "equation" for block in blocks) == 7
    assert sum(block.kind == "number" for block in blocks) == 10
    assert [block.ordinal for block in blocks if block.kind == "number"] == [
        1,
        2,
        3,
        4,
        1,
        2,
        3,
        4,
        5,
        6,
    ]


def test_every_frozen_display_equation_has_a_readable_mapping() -> None:
    _, blocks = parse_markdown(ROOT / "papers" / "paper2_torque_uq" / "manuscript.md")
    equations = [block.text for block in blocks if block.kind == "equation"]
    assert len(equations) == len(DISPLAY_EQUATIONS)
    assert all("\\" not in display_equation(equation) for equation in equations)
    assert all("_" not in display_equation(equation) for equation in equations)
    assert any("α" in display_equation(equation) for equation in equations)


def test_generated_docx_structural_audit_when_artifact_exists() -> None:
    path = (
        ROOT
        / "papers"
        / "paper2_torque_uq"
        / "submission"
        / "Paper2_Manuscript_Anonymous.docx"
    )
    if path.is_file():
        result = audit_docx(path)
        assert result["tables"] == 5
        assert result["inline_drawings"] == 5
