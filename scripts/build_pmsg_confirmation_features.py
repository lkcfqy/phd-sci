"""Build the frozen independent PMSG current-feature table after preregistration."""

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

from pmsm_sci.faults.paper3 import PAPER3_CONTEXT_FEATURES, PAPER3_OUTCOME_FEATURES
from pmsm_sci.faults.pmsg_confirmation import (
    REQUIRED_MAT_VARIABLES,
    discover_pmsg_files,
    extract_pmsg_feature_rows,
    load_pmsg_mat,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--input-dir",
        type=Path,
        default=Path("tmp/pmsg3_metadata_repo/PMSG-3phase-Dataset"),
    )
    parser.add_argument(
        "--container-audit",
        type=Path,
        default=Path("results/paper3_confirmation_reveal/container_audit.csv"),
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("data/processed/paper3_pmsg_confirmation_features.csv.gz"),
    )
    return parser.parse_args()


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        while chunk := stream.read(8 * 1024 * 1024):
            digest.update(chunk)
    return digest.hexdigest()


def main() -> None:
    args = parse_args()
    audit = pd.read_csv(args.container_audit).set_index("filename")
    paths = discover_pmsg_files(args.input_dir)
    rows: list[dict[str, object]] = []
    file_rows: list[dict[str, object]] = []
    for index, path in enumerate(paths, start=1):
        if path.name not in audit.index:
            raise AssertionError(f"File is absent from container audit: {path.name}")
        digest = str(audit.loc[path.name, "sha256"])
        if sha256(path) != digest:
            raise AssertionError(f"Post-audit hash mismatch: {path.name}")
        record = load_pmsg_mat(path)
        extracted = extract_pmsg_feature_rows(record, source_sha256=digest)
        rows.extend(extracted)
        file_rows.append(
            {
                "filename": path.name,
                "sha256": digest,
                "samples": len(record.time),
                "sample_rate_hz": record.sample_rate_hz,
                "is_healthy": record.label.is_healthy,
                "standalone_role": extracted[0]["standalone_role"],
                "feature_rows": len(extracted),
            }
        )
        if index % 25 == 0 or index == len(paths):
            print(f"extracted {index}/{len(paths)} records ({len(rows):,} rows)")

    frame = pd.DataFrame(rows)
    expected_segments = {
        "health_analysis": 117,
        "pre_fault": 648,
        "fault_active": 432,
        "recovery": 1_296,
    }
    observed_segments = frame["segment"].value_counts().to_dict()
    if observed_segments != expected_segments:
        raise AssertionError(
            f"Frozen PMSG segment counts differ: {observed_segments} != {expected_segments}"
        )
    if len(frame) != 2_493 or frame["record_id"].nunique() != 225:
        raise AssertionError("Expected 2,493 rows from 225 PMSG records")
    context_columns = ("speed_rpm", "torque_setting_code")
    if not np.isfinite(
        frame[list(context_columns) + list(PAPER3_OUTCOME_FEATURES)].to_numpy(
            dtype=np.float64
        )
    ).all():
        raise AssertionError("PMSG frozen context/outcome features must be finite")

    args.output.parent.mkdir(parents=True, exist_ok=True)
    frame.to_csv(args.output, index=False, compression="gzip")
    metadata_path = args.output.with_suffix(".metadata.json")
    metadata = {
        "created_utc": datetime.now(UTC).isoformat(),
        "python": platform.python_version(),
        "numpy": np.__version__,
        "pandas": pd.__version__,
        "scipy": scipy.__version__,
        "input_dir": str(args.input_dir.resolve()),
        "container_audit": str(args.container_audit.resolve()),
        "container_audit_sha256": sha256(args.container_audit),
        "output": str(args.output.resolve()),
        "output_sha256": sha256(args.output),
        "mat_variables_deserialized": list(REQUIRED_MAT_VARIABLES),
        "forbidden_variables_deserialized": False,
        "context_features": list(context_columns),
        "development_context_schema_names": list(PAPER3_CONTEXT_FEATURES),
        "outcome_features": list(PAPER3_OUTCOME_FEATURES),
        "rows": len(frame),
        "records": int(frame["record_id"].nunique()),
        "segment_rows": observed_segments,
        "standalone_roles": frame.loc[
            frame["segment"].eq("health_analysis"), "standalone_role"
        ].value_counts().to_dict(),
        "files": file_rows,
    }
    metadata_path.write_text(json.dumps(metadata, indent=2), encoding="utf-8")
    print(f"wrote {len(frame):,} rows to {args.output.resolve()}")
    print(f"wrote metadata to {metadata_path.resolve()}")


if __name__ == "__main__":
    main()
