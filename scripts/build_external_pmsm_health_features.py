"""Build frozen external dual-three-phase PMSM current features.

The current input directory contains only healthy ``flt0z`` files. The filename
grammar is already frozen for future ``flt1..6z{u|v}`` files, allowing a later
one-time reveal to use this exact same parser and feature code.
"""

from __future__ import annotations

import argparse
import json
import platform
from datetime import UTC, datetime
from pathlib import Path

import numpy as np
import pandas as pd
import scipy

from pmsm_sci.faults.external_pmsm import (
    ANALYSIS_START_SECONDS,
    ANALYSIS_STOP_SECONDS,
    BLOCK_SECONDS,
    EXPECTED_SAMPLE_RATE_HZ,
    EXPECTED_SAMPLES,
    REQUIRED_MAT_VARIABLES,
    SUBSYSTEM_VARIABLES,
    WINDOW_SECONDS,
    discover_external_pmsm_files,
    extract_feature_rows,
    file_sha256,
    load_external_pmsm_mat,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--input-dir",
        type=Path,
        default=Path("data/raw/external_validation/dual_three_phase_health"),
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path(
            "data/processed/external_dual_three_phase_health_features.csv.gz"
        ),
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    paths = discover_external_pmsm_files(args.input_dir)
    rows: list[dict[str, object]] = []
    file_metadata: list[dict[str, object]] = []
    for path in paths:
        digest = file_sha256(path)
        record = load_external_pmsm_mat(path)
        extracted = extract_feature_rows(record, source_sha256=digest)
        rows.extend(extracted)
        file_metadata.append(
            {
                "path": str(path.resolve()),
                "filename": path.name,
                "bytes": path.stat().st_size,
                "sha256": digest,
                "load_nm": record.label.load_nm,
                "fault_turns": record.label.fault_turns,
                "fault_phase": record.label.fault_phase,
                "is_healthy": record.label.is_healthy,
                "samples": record.samples,
                "sample_rate_hz": record.sample_rate_hz,
                "time_start_s": float(record.time[0]),
                "time_stop_s": float(record.time[-1]),
                "subsystems": list(SUBSYSTEM_VARIABLES),
                "windows_per_subsystem": 120,
                "macroblocks_per_subsystem": 8,
            }
        )
        print(
            f"processed {path.name}: condition={record.label.condition_token}, "
            f"load={record.label.load_nm:g} Nm, rows={len(extracted)}"
        )

    frame = pd.DataFrame(rows)
    expected_rows = len(paths) * len(SUBSYSTEM_VARIABLES) * 120
    if len(frame) != expected_rows:
        raise AssertionError(f"Expected {expected_rows} rows, built {len(frame)}")
    counts = frame.groupby(["record_id", "subsystem"], observed=True).agg(
        windows=("window_id", "nunique"),
        blocks=("block_id", "nunique"),
    )
    if not (counts["windows"].eq(120) & counts["blocks"].eq(8)).all():
        raise AssertionError("Each record/subsystem stream must contain 120 windows/8 blocks")
    physical_records = int(frame["record_id"].nunique())
    record_subsystem_streams = len(counts)
    if physical_records != len(paths):
        raise AssertionError("Each MAT file must map to exactly one physical record_id")
    if record_subsystem_streams != len(paths) * len(SUBSYSTEM_VARIABLES):
        raise AssertionError("Each physical record must contain both subsystem streams")

    args.output.parent.mkdir(parents=True, exist_ok=True)
    frame.to_csv(args.output, index=False, compression="gzip")
    metadata_path = args.output.with_suffix(".metadata.json")
    metadata_path.write_text(
        json.dumps(
            {
                "created_utc": datetime.now(UTC).isoformat(),
                "python": platform.python_version(),
                "numpy": np.__version__,
                "pandas": pd.__version__,
                "scipy": scipy.__version__,
                "input_dir": str(args.input_dir.resolve()),
                "output": str(args.output.resolve()),
                "filename_grammar": (
                    "spd10-5000rpm_flt0z_XXNM.mat or "
                    "spd10-5000rpm_flt{1..6}z{u|v}_XXNM.mat"
                ),
                "mat_variables_deserialized": list(REQUIRED_MAT_VARIABLES),
                "voltage_or_dq_variables_deserialized": False,
                "expected_samples": EXPECTED_SAMPLES,
                "sample_rate_hz": EXPECTED_SAMPLE_RATE_HZ,
                "analysis_interval_half_open_s": [
                    ANALYSIS_START_SECONDS,
                    ANALYSIS_STOP_SECONDS,
                ],
                "processed_block_ids": list(range(8)),
                "full_record_block_ids": list(range(4, 12)),
                "block_id_mapping": "processed_block_id = full_record_block_id - 4",
                "window_seconds": WINDOW_SECONDS,
                "stride_seconds": WINDOW_SECONDS,
                "block_seconds": BLOCK_SECONDS,
                "physical_records": physical_records,
                "record_subsystem_streams": record_subsystem_streams,
                "windows_per_record_subsystem_stream": 120,
                "blocks_per_record_subsystem_stream": 8,
                "files": file_metadata,
                "health_files": sum(item["is_healthy"] for item in file_metadata),
                "fault_files": sum(not item["is_healthy"] for item in file_metadata),
                "rows": len(frame),
                "columns": list(frame.columns),
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    print(f"wrote {len(frame)} rows to {args.output.resolve()}")
    print(f"wrote metadata to {metadata_path.resolve()}")


if __name__ == "__main__":
    main()
