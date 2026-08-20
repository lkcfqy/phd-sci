"""Build an independent 10 kHz anti-aliased KAIST current feature arm.

This is a post-reveal sampling-rate sensitivity analysis.  All signal and
feature settings are mechanical copies of the frozen primary protocol; no
external fault outcome is read by this script.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import platform
from datetime import UTC, datetime
from pathlib import Path

import numpy as np
import pandas as pd
import scipy

from pmsm_sci.faults.records import parse_record_name
from pmsm_sci.faults.resampling import (
    polyphase_downsample_current,
    polyphase_specification,
    resampled_window_ranges,
)
from pmsm_sci.faults.signal_features import current_features
from pmsm_sci.faults.tdms_io import inspect_current_tdms, iter_current_windows

SOURCE_RATE_HZ = 100_000
TARGET_RATE_HZ = 10_000
WINDOW_SECONDS = 0.2
STRIDE_SECONDS = 0.2
BLOCK_SECONDS = 3.0
DURATION_SECONDS = 120.0


def file_sha256(path: Path, chunk_size: int = 8 * 1024 * 1024) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        while chunk := stream.read(chunk_size):
            digest.update(chunk)
    return digest.hexdigest()


def deduplicate_healthy_aliases(
    paths: list[Path],
) -> tuple[list[Path], list[dict[str, str]]]:
    """Retain one canonical file for each byte-identical healthy alias pair."""

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


def load_analysis_record(path: Path, duration_seconds: float) -> np.ndarray:
    """Load exactly one complete leading analysis segment through the public reader."""

    windows = iter_current_windows(
        path,
        window_seconds=duration_seconds,
        stride_seconds=duration_seconds,
        block_seconds=duration_seconds,
        max_duration_seconds=duration_seconds,
    )
    try:
        index, values = next(windows)
    except StopIteration as error:
        raise ValueError(f"{path} does not contain a complete analysis segment") from error
    if index.block_id != 0 or index.window_id != 0 or index.start != 0:
        raise AssertionError("Unexpected full-record window index")
    try:
        next(windows)
    except StopIteration:
        return values
    raise AssertionError("Full-record loader yielded more than one analysis segment")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--input-dir", type=Path, default=Path("data/raw/kaist_faults/current_tdms")
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("data/processed/kaist_current_features_10khz.csv.gz"),
    )
    parser.add_argument("--motors", nargs="*", default=[])
    parser.add_argument("--max-records", type=int)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    primary_output = Path("data/processed/kaist_current_features.csv.gz").resolve()
    if args.output.resolve() == primary_output:
        raise ValueError("The sensitivity arm must not overwrite the primary feature table")

    paths = sorted(args.input_dir.rglob("*.tdms"))
    if args.motors:
        selected_motors = set(args.motors)
        paths = [
            path
            for path in paths
            if parse_record_name(path).motor_id in selected_motors
        ]
    paths, duplicate_aliases = deduplicate_healthy_aliases(paths)
    if args.max_records is not None:
        if args.max_records <= 0:
            raise ValueError("max-records must be positive")
        paths = paths[: args.max_records]
    if not paths:
        raise FileNotFoundError(f"No current TDMS files found in {args.input_dir}")

    specification = polyphase_specification(SOURCE_RATE_HZ, TARGET_RATE_HZ)
    rows: list[dict[str, object]] = []
    file_metadata: list[dict[str, object]] = []
    for position, path in enumerate(paths, start=1):
        record = parse_record_name(path)
        metadata = inspect_current_tdms(path)
        if not np.isclose(metadata.sample_rate_hz, SOURCE_RATE_HZ, rtol=0.0, atol=1e-6):
            raise ValueError(
                f"{path} has {metadata.sample_rate_hz:g} Hz, expected {SOURCE_RATE_HZ} Hz"
            )
        if metadata.duration_seconds + 1e-9 < DURATION_SECONDS:
            raise ValueError(f"{path} is shorter than {DURATION_SECONDS:g} seconds")
        print(f"[{position}/{len(paths)}] processing {record.record_id}", flush=True)
        native = load_analysis_record(path, DURATION_SECONDS)
        downsampled = polyphase_downsample_current(
            native,
            source_rate_hz=metadata.sample_rate_hz,
            target_rate_hz=TARGET_RATE_HZ,
        )
        expected_target_samples = round(DURATION_SECONDS * TARGET_RATE_HZ)
        if downsampled.shape != (expected_target_samples, 3):
            raise AssertionError(
                f"Unexpected resampled shape for {record.record_id}: {downsampled.shape}"
            )
        ranges = resampled_window_ranges(
            len(downsampled),
            sample_rate_hz=TARGET_RATE_HZ,
            window_seconds=WINDOW_SECONDS,
            stride_seconds=STRIDE_SECONDS,
            block_seconds=BLOCK_SECONDS,
        )
        if len(ranges) != 600 or len({index.block_id for index in ranges}) != 40:
            raise AssertionError("Frozen 120 s geometry must yield 600 windows in 40 blocks")
        for index in ranges:
            row = record.to_dict()
            row.update(
                block_id=index.block_id,
                window_id=index.window_id,
                start_sample=index.start,
                stop_sample=index.stop,
                **current_features(
                    downsampled[index.start : index.stop], TARGET_RATE_HZ
                ),
            )
            rows.append(row)
        file_metadata.append(
            record.to_dict()
            | {
                "path": str(path.resolve()),
                "sha256": file_sha256(path),
                "native_samples": metadata.samples,
                "native_sample_rate_hz": metadata.sample_rate_hz,
                "native_duration_seconds": metadata.duration_seconds,
                "analysis_native_samples": len(native),
                "analysis_target_samples": len(downsampled),
                "channels": list(metadata.channel_names),
            }
        )

    frame = pd.DataFrame(rows)
    expected_rows = 600 * len(paths)
    if len(frame) != expected_rows or frame["record_id"].nunique() != len(paths):
        raise AssertionError("Feature table record/window completeness check failed")
    args.output.parent.mkdir(parents=True, exist_ok=True)
    frame.to_csv(args.output, index=False, compression="gzip")
    metadata_path = args.output.with_suffix(".metadata.json")
    metadata_path.write_text(
        json.dumps(
            {
                "created_utc": datetime.now(UTC).isoformat(),
                "analysis_status": "post-reveal sampling-rate sensitivity",
                "external_fault_data_read": False,
                "python": platform.python_version(),
                "numpy": np.__version__,
                "scipy": scipy.__version__,
                "records": file_metadata,
                "duplicate_healthy_aliases": duplicate_aliases,
                "resampling": {
                    "implementation": "scipy.signal.resample_poly",
                    "source_rate_hz": specification.source_rate_hz,
                    "target_rate_hz": specification.target_rate_hz,
                    "up": specification.up,
                    "down": specification.down,
                    "window": list(specification.window),
                    "padtype": specification.padtype,
                    "scope": "complete leading 120 s record before windowing",
                },
                "window_seconds": WINDOW_SECONDS,
                "stride_seconds": STRIDE_SECONDS,
                "block_seconds": BLOCK_SECONDS,
                "duration_seconds_used": DURATION_SECONDS,
                "rows": len(frame),
                "columns": list(frame.columns),
                "feature_table_sha256": file_sha256(args.output),
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    print(f"wrote {len(frame)} windows to {args.output.resolve()}", flush=True)


if __name__ == "__main__":
    main()
