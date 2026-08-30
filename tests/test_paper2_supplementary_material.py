from __future__ import annotations

from pathlib import Path

from scripts.build_paper2_supplementary_material import OUTPUT, build_content

ROOT = Path(__file__).resolve().parents[1]


def test_paper2_supplement_contains_complete_frozen_evidence() -> None:
    content = build_content()
    assert content.count("# S") == 9
    assert "23,250" in content
    assert "76.13%" in content
    assert "78.31%" in content
    assert "0/5,000" in content
    assert "4.31/600" in content
    assert "42,900" in content
    assert "not repaired" in content
    assert "hardware uncertainty" in content


def test_checked_in_supplement_is_current_when_present() -> None:
    assert OUTPUT == ROOT / "papers" / "paper2_torque_uq" / "supplementary_material.md"
    if OUTPUT.is_file():
        assert OUTPUT.read_text(encoding="utf-8") == build_content()
