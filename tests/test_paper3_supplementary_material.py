from __future__ import annotations

from scripts.build_paper3_supplementary_material import OUTPUT, ROOT, build_content


def test_paper3_supplement_contains_complete_evidence() -> None:
    content = build_content()
    assert content.count("# S") == 9
    assert "71/216" in content
    assert "156/216" in content
    assert "17/216" in content
    assert "14/216" in content
    assert "18/216" in content
    assert "signal-unrevealed metadata freeze" in content
    assert "2,493" in content
    assert "not independent machines" in content


def test_checked_in_paper3_supplement_is_current_when_present() -> None:
    assert OUTPUT == ROOT / "papers/paper3_calibration_transport/supplementary_material.md"
    if OUTPUT.is_file():
        assert OUTPUT.read_text(encoding="utf-8") == build_content()
