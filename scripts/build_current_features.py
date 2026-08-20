"""Convert extracted KAIST current TDMS records into a window-level feature table."""

from __future__ import annotations

import argparse
import hashlib
import json
import platform
from datetime import UTC, datetime
from pathlib import Path

import numpy as np
import pandas as pd

from pmsm_sci.faults.records import parse_record_name
from pmsm_sci.faults.signal_features import current_features
from pmsm_sci.faults.tdms_io import inspect_current_tdms, iter_current_windows


def file_sha256(path: Path, chunk_size: int = 8 * 1024 * 1024) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        while chunk := stream.read(chunk_size):
            digest.update(chunk)
    return digest.hexdigest()


def deduplicate_healthy_aliases(paths: list[Path]) -> tuple[list[Path], list[dict[str, str]]]:
    """Remove byte-identical healthy aliases without hiding non-identical repeats."""

    healthy_by_motor: dict[str, list[Path]] = {}
    selected: list[Path] = []
    for path in paths:
        record = parse_record_name(path)
        if record.is_healthy:
            healthy_by_motor.setdefault(record.motor_id, []).append(path)
        else:
            selected.append(path)

    aliases: list[dict[str, str]] = []
    for motor_id, candidates in sorted(healthy_by_motor.items()):
        candidates = sorted(candidates)
        canonical = candidates[0]
        canonical_hash = file_sha256(canonical)
        selected.append(canonical)
        for alias in candidates[1:]:
            alias_hash = file_sha256(alias)
            if alias_hash != canonical_hash:
                raise RuntimeError(
                    f"Healthy files for {motor_id} are not identical; protocol review required"
                )
            aliases.append(
                {
                    "motor_id": motor_id,
                    "canonical": str(canonical.resolve()),
                    "alias": str(alias.resolve()),
                    "sha256": canonical_hash,
                }
            )
    return sorted(selected), aliases


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--input-dir", type=Path, default=Path("data/raw/kaist_faults/current_tdms")
    )
    parser.add_argument(
        "--output", type=Path, default=Path("data/processed/kaist_current_features.csv.gz")
    )
    parser.add_argument("--window-seconds", type=float, default=0.2)
    parser.add_argument("--stride-seconds", type=float, default=0.2)
    parser.add_argument("--block-seconds", type=float, default=3.0)
    parser.add_argument("--duration-seconds", type=float, default=120.0)
    parser.add_argument("--motors", nargs="*", default=[])
    parser.add_argument("--max-records", type=int)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    paths = sorted(args.input_dir.rglob("*.tdms"))
    if args.motors:
        selected = set(args.motors)
        paths = [path for path in paths if parse_record_name(path).motor_id in selected]
    paths, duplicate_aliases = deduplicate_healthy_aliases(paths)
    if args.max_records is not None:
        paths = paths[: args.max_records]
    if not paths:
        raise FileNotFoundError(f"No current TDMS files found in {args.input_dir}")

    rows: list[dict[str, object]] = []
    file_metadata: list[dict[str, object]] = []
    for path in paths:
        record = parse_record_name(path)
        metadata = inspect_current_tdms(path)
        file_metadata.append(
            record.to_dict()
            | {
                "path": str(path.resolve()),
                "samples": metadata.samples,
                "sample_rate_hz": metadata.sample_rate_hz,
                "duration_seconds": metadata.duration_seconds,
                "channels": list(metadata.channel_names),
            }
        )
        print(f"processing {record.record_id}")
        for index, current in iter_current_windows(
            path,
            window_seconds=args.window_seconds,
            stride_seconds=args.stride_seconds,
            block_seconds=args.block_seconds,
            max_duration_seconds=args.duration_seconds,
        ):
            row = record.to_dict()
            row.update(
                block_id=index.block_id,
                window_id=index.window_id,
                start_sample=index.start,
                stop_sample=index.stop,
                **current_features(current, metadata.sample_rate_hz),
            )
            rows.append(row)

    frame = pd.DataFrame(rows)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    frame.to_csv(args.output, index=False, compression="gzip")
    metadata_path = args.output.with_suffix(".metadata.json")
    metadata_path.write_text(
        json.dumps(
            {
                "created_utc": datetime.now(UTC).isoformat(),
                "python": platform.python_version(),
                "numpy": np.__version__,
                "records": file_metadata,
                "duplicate_healthy_aliases": duplicate_aliases,
                "window_seconds": args.window_seconds,
                "stride_seconds": args.stride_seconds,
                "block_seconds": args.block_seconds,
                "duration_seconds_used": args.duration_seconds,
                "rows": len(frame),
                "columns": list(frame.columns),
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    print(f"wrote {len(frame)} windows to {args.output.resolve()}")


if __name__ == "__main__":
    main()
