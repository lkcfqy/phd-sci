"""Audit the KAIST ZIP central directories and write a reproducible inventory."""

from __future__ import annotations

import argparse
import json
import zipfile
from pathlib import Path

import pandas as pd

from pmsm_sci.faults.records import inventory_archive, validate_motor_inventory


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--archive-dir", type=Path, default=Path("data/raw/kaist_faults"))
    parser.add_argument("--results-dir", type=Path, default=Path("results/data_audit"))
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    archives = sorted(args.archive_dir.glob("*.zip"))
    if not archives:
        raise FileNotFoundError(f"No completed ZIP archives found in {args.archive_dir}")
    args.results_dir.mkdir(parents=True, exist_ok=True)

    record_rows: list[dict[str, object]] = []
    archive_rows: list[dict[str, object]] = []
    duplicate_rows: list[dict[str, object]] = []
    for path in archives:
        records = inventory_archive(path)
        validate_motor_inventory(records)
        with zipfile.ZipFile(path) as archive:
            infos = [
                info for info in archive.infolist() if info.filename.lower().endswith(".tdms")
            ]
        info_by_name = {info.filename: info for info in infos}
        for record in records:
            info = info_by_name[record.member_path]
            record_rows.append(
                record.to_dict()
                | {
                    "archive": path.name,
                    "uncompressed_bytes": info.file_size,
                    "compressed_bytes": info.compress_size,
                    "zip_crc32": f"{info.CRC:08x}",
                }
            )
        duplicate_groups: dict[tuple[int, int], list[str]] = {}
        for info in infos:
            duplicate_groups.setdefault((info.file_size, info.CRC), []).append(info.filename)
        for (file_size, crc), names in duplicate_groups.items():
            if len(names) > 1:
                duplicate_rows.append(
                    {
                        "archive": path.name,
                        "uncompressed_bytes": file_size,
                        "zip_crc32": f"{crc:08x}",
                        "members": names,
                    }
                )
        archive_rows.append(
            {
                "archive": path.name,
                "zip_bytes": path.stat().st_size,
                "tdms_records": len(infos),
                "tdms_compressed_bytes": sum(info.compress_size for info in infos),
                "tdms_uncompressed_bytes": sum(info.file_size for info in infos),
                "current_uncompressed_bytes": sum(
                    info.file_size for info in infos if "current" in info.filename.lower()
                ),
                "vibration_uncompressed_bytes": sum(
                    info.file_size for info in infos if "vibration" in info.filename.lower()
                ),
            }
        )

    records_frame = pd.DataFrame(record_rows).sort_values(
        ["motor_watts", "fault_family", "modality", "severity_percent"]
    )
    records_frame.to_csv(args.results_dir / "kaist_records.csv", index=False)
    (args.results_dir / "kaist_archives.json").write_text(
        json.dumps(archive_rows, indent=2), encoding="utf-8"
    )
    (args.results_dir / "kaist_duplicate_members.json").write_text(
        json.dumps(duplicate_rows, indent=2), encoding="utf-8"
    )
    print(records_frame.groupby(["motor_id", "fault_family", "modality"]).size())
    print(f"wrote audit to {args.results_dir.resolve()}")


if __name__ == "__main__":
    main()
