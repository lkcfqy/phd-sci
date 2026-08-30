"""Attach fault-independent operating context to the Paper 3 development bench."""

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

from pmsm_sci.faults.operating_context import (
    OPERATING_CONTEXT_VARIABLES,
    attach_external_operating_context,
)
from pmsm_sci.faults.paper3 import PAPER3_CONTEXT_FEATURES, PAPER3_OUTCOME_FEATURES


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--features",
        type=Path,
        default=Path("data/processed/external_dual_three_phase_health_features.csv.gz"),
    )
    parser.add_argument(
        "--input-dir",
        type=Path,
        default=Path("data/raw/external_validation/dual_three_phase_health"),
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("data/processed/paper3_development_features.csv.gz"),
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
    frame = pd.read_csv(args.features)
    required = set(PAPER3_CONTEXT_FEATURES).difference({"commanded_speed_rpm"}) | set(
        PAPER3_OUTCOME_FEATURES
    )
    missing = required.difference(frame.columns)
    if missing:
        raise ValueError(f"Input feature table lacks frozen Paper 3 columns: {sorted(missing)}")
    output = attach_external_operating_context(frame, args.input_dir, verify_hashes=True)
    if len(output) != 13_440 or output["record_id"].nunique() != 56:
        raise AssertionError("Paper 3 development table must contain 56 records/13,440 rows")
    if output[list(PAPER3_CONTEXT_FEATURES) + list(PAPER3_OUTCOME_FEATURES)].isna().any().any():
        raise AssertionError("Paper 3 context/outcome columns contain missing values")

    args.output.parent.mkdir(parents=True, exist_ok=True)
    output.to_csv(args.output, index=False, compression="gzip")
    metadata_path = args.output.with_suffix(".metadata.json")
    metadata = {
        "created_utc": datetime.now(UTC).isoformat(),
        "python": platform.python_version(),
        "numpy": np.__version__,
        "pandas": pd.__version__,
        "scipy": scipy.__version__,
        "input_features": str(args.features.resolve()),
        "input_features_sha256": sha256(args.features),
        "input_mat_dir": str(args.input_dir.resolve()),
        "output": str(args.output.resolve()),
        "output_sha256": sha256(args.output),
        "operating_context_variables_deserialized": list(OPERATING_CONTEXT_VARIABLES),
        "fault_sensitive_context_variables_deserialized": False,
        "context_features": list(PAPER3_CONTEXT_FEATURES),
        "outcome_features": list(PAPER3_OUTCOME_FEATURES),
        "absolute_current_scale_excluded": True,
        "current_derived_fundamental_hz_excluded": True,
        "rows": len(output),
        "physical_records": int(output["record_id"].nunique()),
        "healthy_records": int(output.loc[output["is_healthy"], "record_id"].nunique()),
        "fault_records": int(output.loc[~output["is_healthy"], "record_id"].nunique()),
        "subsystems": sorted(output["subsystem"].unique().tolist()),
        "loads_nm": sorted(output["load_nm"].unique().tolist()),
        "commanded_speed_rpm_min": float(output["commanded_speed_rpm"].min()),
        "commanded_speed_rpm_max": float(output["commanded_speed_rpm"].max()),
    }
    metadata_path.write_text(json.dumps(metadata, indent=2), encoding="utf-8")
    print(
        f"wrote {len(output):,} rows from {metadata['physical_records']} records to "
        f"{args.output.resolve()}"
    )
    print(
        "context range: "
        f"{metadata['commanded_speed_rpm_min']:.2f}--"
        f"{metadata['commanded_speed_rpm_max']:.2f} rpm"
    )
    print(f"wrote metadata to {metadata_path.resolve()}")


if __name__ == "__main__":
    main()
