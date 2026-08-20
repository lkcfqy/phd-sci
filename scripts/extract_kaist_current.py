"""Extract selected current TDMS members from verified KAIST ZIP archives."""

from __future__ import annotations

import argparse
import json
import shutil
import zipfile
from pathlib import Path

from pmsm_sci.faults.records import inventory_archive, validate_motor_inventory


def extract_archive(
    archive_path: Path,
    output_dir: Path,
    *,
    healthy_only: bool,
    keep_duplicate_aliases: bool,
) -> list[dict[str, object]]:
    records = inventory_archive(archive_path)
    validate_motor_inventory(records)
    selected = [
        record
        for record in records
        if record.modality == "current" and (record.is_healthy or not healthy_only)
    ]
    extracted: list[dict[str, object]] = []
    with zipfile.ZipFile(archive_path) as archive:
        info_by_name = {info.filename: info for info in archive.infolist()}
        seen_content: set[tuple[int, int]] = set()
        for record in selected:
            info = info_by_name[record.member_path]
            content_key = (info.file_size, info.CRC)
            if content_key in seen_content and not keep_duplicate_aliases:
                print(f"skipped exact duplicate alias {record.filename}")
                continue
            seen_content.add(content_key)
            motor_dir = output_dir / record.motor_id
            motor_dir.mkdir(parents=True, exist_ok=True)
            destination = motor_dir / record.filename
            partial = destination.with_suffix(destination.suffix + ".part")

            if destination.exists() and destination.stat().st_size == info.file_size:
                print(f"verified existing {destination}")
            else:
                if destination.exists():
                    raise RuntimeError(f"Existing file has wrong size: {destination}")
                with archive.open(info) as source, partial.open("wb") as target:
                    shutil.copyfileobj(source, target, length=8 * 1024 * 1024)
                if partial.stat().st_size != info.file_size:
                    raise RuntimeError(f"Extraction size mismatch: {record.filename}")
                partial.replace(destination)
                print(f"extracted {destination}")

            row = record.to_dict()
            row.update(bytes=info.file_size, zip_crc32=f"{info.CRC:08x}")
            extracted.append(row)
    return extracted


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--archive-dir", type=Path, default=Path("data/raw/kaist_faults"))
    parser.add_argument(
        "--output-dir", type=Path, default=Path("data/raw/kaist_faults/current_tdms")
    )
    parser.add_argument("--healthy-only", action="store_true")
    parser.add_argument("--keep-duplicate-aliases", action="store_true")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    archives = sorted(args.archive_dir.glob("*.zip"))
    if not archives:
        raise FileNotFoundError(f"No completed ZIP archives found in {args.archive_dir}")
    rows: list[dict[str, object]] = []
    for archive in archives:
        rows.extend(
            extract_archive(
                archive,
                args.output_dir,
                healthy_only=args.healthy_only,
                keep_duplicate_aliases=args.keep_duplicate_aliases,
            )
        )
    manifest = args.output_dir / "records.json"
    manifest.write_text(json.dumps(rows, indent=2), encoding="utf-8")
    print(f"wrote {manifest.resolve()}")


if __name__ == "__main__":
    main()
