from pathlib import Path

import pytest

from pmsm_sci.faults.records import parse_record_name


def test_parse_record_name_normalizes_metadata() -> None:
    record = parse_record_name(
        Path("1.5kW") / "1500W_3_10_current_interturn.tdms"
    )
    assert record.motor_watts == 1500
    assert record.motor_id == "1.5kW"
    assert record.severity_percent == pytest.approx(3.10)
    assert record.modality == "current"
    assert record.fault_family == "interturn"
    assert not record.is_healthy


def test_parse_record_name_maps_coil_alias_and_healthy() -> None:
    record = parse_record_name("1000W_0_00_vibration_coil.tdms")
    assert record.fault_family == "intercoil"
    assert record.is_healthy


def test_parse_record_name_accepts_known_decimal_separator_typo() -> None:
    record = parse_record_name("1000W_1.01_current_intercoil.tdms")
    assert record.severity_percent == pytest.approx(1.01)


def test_parse_record_name_rejects_unknown_format() -> None:
    with pytest.raises(ValueError, match="Unrecognized"):
        parse_record_name("random.tdms")
