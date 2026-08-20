"""Filename parsing and archive inventory for the KAIST PMSM dataset."""

from __future__ import annotations

import re
import zipfile
from dataclasses import asdict, dataclass
from pathlib import Path, PurePosixPath

RECORD_PATTERN = re.compile(
    r"^(?P<watts>\d+)W_"
    r"(?P<severity_whole>\d+)[_.](?P<severity_fraction>\d+)_"
    r"(?P<modality>current|vibration)_"
    r"(?P<fault_family>interturn|intercoil|coil)\.tdms$",
    flags=re.IGNORECASE,
)


@dataclass(frozen=True)
class FaultRecord:
    """Metadata encoded in one raw TDMS filename."""

    member_path: str
    filename: str
    motor_watts: int
    severity_percent: float
    modality: str
    fault_family: str

    @property
    def motor_id(self) -> str:
        return f"{self.motor_watts / 1000:g}kW"

    @property
    def is_healthy(self) -> bool:
        return self.severity_percent == 0.0

    @property
    def record_id(self) -> str:
        family = self.fault_family.replace("inter", "")
        severity = f"{self.severity_percent:.6g}".replace(".", "p")
        return f"{self.motor_id}_{family}_{self.modality}_{severity}pct"

    def to_dict(self) -> dict[str, object]:
        result = asdict(self)
        result.update(
            motor_id=self.motor_id,
            is_healthy=self.is_healthy,
            record_id=self.record_id,
        )
        return result


def parse_record_name(path: str | Path) -> FaultRecord:
    """Parse the motor, severity, modality, and fault family from a TDMS path."""

    normalized = str(path).replace("\\", "/")
    filename = PurePosixPath(normalized).name
    match = RECORD_PATTERN.fullmatch(filename)
    if match is None:
        raise ValueError(f"Unrecognized KAIST TDMS filename: {filename}")

    fraction_text = match.group("severity_fraction")
    severity = float(f"{match.group('severity_whole')}.{fraction_text}")
    family = match.group("fault_family").lower()
    if family == "coil":
        family = "intercoil"
    return FaultRecord(
        member_path=normalized,
        filename=filename,
        motor_watts=int(match.group("watts")),
        severity_percent=severity,
        modality=match.group("modality").lower(),
        fault_family=family,
    )


def inventory_archive(path: Path) -> list[FaultRecord]:
    """Return parsed TDMS records from a ZIP without extracting its payload."""

    with zipfile.ZipFile(path) as archive:
        members = [name for name in archive.namelist() if name.lower().endswith(".tdms")]
    records = [parse_record_name(member) for member in members]
    if not records:
        raise ValueError(f"No TDMS records found in {path}")
    return sorted(
        records,
        key=lambda item: (
            item.motor_watts,
            item.fault_family,
            item.modality,
            item.severity_percent,
        ),
    )


def validate_motor_inventory(records: list[FaultRecord]) -> None:
    """Enforce the expected paired 2-family × 8-state × 2-modality structure."""

    if len(records) != 32:
        raise ValueError(f"Expected 32 TDMS records for one motor, found {len(records)}")
    motors = {record.motor_watts for record in records}
    if len(motors) != 1:
        raise ValueError(f"Archive must contain exactly one motor, found {sorted(motors)}")

    for family in ("interturn", "intercoil"):
        current = [
            record
            for record in records
            if record.fault_family == family and record.modality == "current"
        ]
        vibration = [
            record
            for record in records
            if record.fault_family == family and record.modality == "vibration"
        ]
        if len(current) != 8 or len(vibration) != 8:
            raise ValueError(
                f"Expected 8 current and 8 vibration records for {family}; "
                f"found {len(current)} and {len(vibration)}"
            )
        if [item.severity_percent for item in current] != [
            item.severity_percent for item in vibration
        ]:
            raise ValueError(f"Current/vibration severities do not match for {family}")
