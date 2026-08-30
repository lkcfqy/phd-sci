"""Audit all frozen PMSG MAT containers without deserializing signal values."""

from __future__ import annotations

import argparse
import hashlib
import json
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path

import pandas as pd
from scipy.io import whosmat

from pmsm_sci.faults.pmsg_confirmation import (
    ACCEPTED_SAMPLE_COUNTS,
    REQUIRED_MAT_VARIABLES,
    discover_pmsg_files,
    parse_pmsg_filename,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--input-dir",
        type=Path,
        default=Path("tmp/pmsg3_metadata_repo/PMSG-3phase-Dataset"),
    )
    parser.add_argument(
        "--inventory",
        type=Path,
        default=Path(
            "results/paper3_confirmation_preregistration/metadata_inventory.csv"
        ),
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("results/paper3_confirmation_reveal"),
    )
    return parser.parse_args()


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        while chunk := stream.read(8 * 1024 * 1024):
            digest.update(chunk)
    return digest.hexdigest()


def audit_schema(
    variables: list[tuple[str, tuple[int, ...], str]],
) -> tuple[int, dict[str, tuple[tuple[int, ...], str]]]:
    by_name = {name: (shape, dtype) for name, shape, dtype in variables}
    missing = set(REQUIRED_MAT_VARIABLES).difference(by_name)
    if missing:
        raise ValueError(f"Missing required PMSG variables: {sorted(missing)}")
    shapes = {by_name[name][0] for name in REQUIRED_MAT_VARIABLES}
    if len(shapes) != 1:
        raise ValueError("Required PMSG time/current variable shapes differ")
    shape = next(iter(shapes))
    if len(shape) != 2 or 1 not in shape:
        raise ValueError(f"Required PMSG variables are not vectors: {shape}")
    samples = max(shape)
    if samples not in ACCEPTED_SAMPLE_COUNTS:
        raise ValueError(f"Unexpected PMSG sample count: {samples}")
    dtypes = {by_name[name][1] for name in REQUIRED_MAT_VARIABLES}
    if dtypes != {"double"}:
        raise ValueError(f"Unexpected required-variable dtype set: {dtypes}")
    return samples, by_name


def main() -> None:
    args = parse_args()
    inventory = pd.read_csv(args.inventory)
    expected_names = set(inventory["filename"].astype(str))
    paths = discover_pmsg_files(args.input_dir)
    observed_names = {path.name for path in paths}
    if observed_names != expected_names:
        raise AssertionError("Checked-out PMSG filenames differ from the frozen inventory")
    rows: list[dict[str, object]] = []
    schema_counter: Counter[tuple[tuple[str, tuple[int, ...], str], ...]] = Counter()
    for index, path in enumerate(paths, start=1):
        variables = whosmat(path)
        samples, by_name = audit_schema(variables)
        label = parse_pmsg_filename(path)
        schema_counter[tuple(sorted(variables))] += 1
        rows.append(
            {
                "filename": path.name,
                "bytes": path.stat().st_size,
                "sha256": file_sha256(path),
                "is_healthy": label.is_healthy,
                "fault_family": label.fault_family,
                "speed_rpm": label.speed_rpm,
                "torque_setting_code": label.torque_setting_code,
                "samples": samples,
                "variables": len(variables),
                "required_shape": str(by_name["t"][0]),
                "required_dtype": by_name["t"][1],
                "has_fault_relay": "Fault_relay" in by_name,
                "has_fault_current": "Ifault" in by_name,
            }
        )
        if index % 25 == 0 or index == len(paths):
            print(f"audited {index}/{len(paths)} containers")
    frame = pd.DataFrame(rows)
    if frame["sha256"].duplicated().any():
        raise AssertionError("Unexpected duplicate PMSG file content hash")
    if not frame["has_fault_relay"].all() or not frame["has_fault_current"].all():
        raise AssertionError("Documented PMSG label variables are not present in every file")

    args.output_dir.mkdir(parents=True, exist_ok=True)
    table_path = args.output_dir / "container_audit.csv"
    frame.to_csv(table_path, index=False)
    summary = {
        "created_utc": datetime.now(UTC).isoformat(),
        "input_dir": str(args.input_dir.resolve()),
        "frozen_inventory": str(args.inventory.resolve()),
        "files": len(frame),
        "healthy_files": int(frame["is_healthy"].sum()),
        "fault_files": int((~frame["is_healthy"]).sum()),
        "sample_counts": frame["samples"].value_counts().sort_index().to_dict(),
        "variable_counts": frame["variables"].value_counts().sort_index().to_dict(),
        "required_variables": list(REQUIRED_MAT_VARIABLES),
        "required_schema": {
            "shape": frame["required_shape"].value_counts().to_dict(),
            "dtype": frame["required_dtype"].value_counts().to_dict(),
        },
        "unique_complete_schemas": len(schema_counter),
        "fault_relay_name_observed": "Fault_relay",
        "fault_relay_deserialized": False,
        "fault_current_deserialized": False,
        "signal_values_deserialized": False,
        "compatibility_patch_required": False,
        "container_table_sha256": file_sha256(table_path),
    }
    (args.output_dir / "container_audit.json").write_text(
        json.dumps(summary, indent=2), encoding="utf-8"
    )
    print(f"wrote {table_path.resolve()}")
    print(f"wrote {(args.output_dir / 'container_audit.json').resolve()}")


if __name__ == "__main__":
    main()
