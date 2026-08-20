"""Build the frozen secondary PMSM feature table after the reveal checkpoint."""

from __future__ import annotations

import argparse
import hashlib
import importlib.metadata
import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from pmsm_sci.faults.signal_features import current_features
from pmsm_sci.faults.transient_external import (
    TransientMetadata,
    TransientRecord,
    fault_current_onset,
    load_transient_record,
    parse_transient_record_path,
    post_fault_window_bounds,
    pre_fault_window_bounds,
    pseudo_three_phase,
    validate_transient_inventory,
)

WINDOW_SECONDS = 0.2
PRE_FAULT_GUARD_SECONDS = 0.2
PRIMARY_POST_SECONDS = 1.0
MAXIMUM_POST_SECONDS = 2.0
PRIMARY_POST_WINDOWS = round(PRIMARY_POST_SECONDS / WINDOW_SECONDS)
FORBIDDEN_ZERO_SEQUENCE_FEATURES = {
    "zero_sequence_rms",
    "zero_sequence_ratio",
}


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        while chunk := stream.read(8 * 1024 * 1024):
            digest.update(chunk)
    return digest.hexdigest()


def metadata_fields(metadata: TransientMetadata) -> dict[str, object]:
    return {
        "record_id": metadata.record_id,
        "filename": metadata.path.name,
        "motor_id": metadata.motor_id,
        "motor_watts": metadata.motor_watts,
        "condition": metadata.condition,
        "setpoint_rad_s": metadata.setpoint_rad_s,
        "fault_turns": metadata.fault_turns,
        "winding_turns": metadata.winding_turns,
        "nominal_severity": metadata.nominal_severity,
        "fault_phase": metadata.fault_phase,
    }


def build_record_features(
    record: TransientRecord,
) -> tuple[list[dict[str, object]], dict[str, object]]:
    """Apply the frozen onset, guard, and 0.2 s feature protocol to one record."""

    onset = fault_current_onset(record.fault_current, record.sample_rate_hz)
    pre_bounds = pre_fault_window_bounds(
        len(record.time),
        onset.onset_index,
        record.sample_rate_hz,
        window_seconds=WINDOW_SECONDS,
        guard_seconds=PRE_FAULT_GUARD_SECONDS,
    )
    post_bounds = post_fault_window_bounds(
        len(record.time),
        onset.onset_index,
        record.sample_rate_hz,
        window_seconds=WINDOW_SECONDS,
        horizon_seconds=MAXIMUM_POST_SECONDS,
    )
    common = metadata_fields(record.metadata)
    rows: list[dict[str, object]] = []
    for segment, bounds in (("pre_fault", pre_bounds), ("post_fault", post_bounds)):
        for window_id, (start, stop) in enumerate(bounds):
            abc = pseudo_three_phase(record.alpha_beta[start:stop])
            features = current_features(abc, record.sample_rate_hz)
            for forbidden in FORBIDDEN_ZERO_SEQUENCE_FEATURES:
                features.pop(forbidden)
            rows.append(
                {
                    **common,
                    "segment": segment,
                    "window_id": window_id,
                    "start_sample": start,
                    "stop_sample": stop,
                    "start_seconds": float(record.time[start]),
                    "stop_seconds": float(
                        record.time[stop - 1] + 1.0 / record.sample_rate_hz
                    ),
                    "relative_start_seconds": (
                        start - onset.onset_index
                    )
                    / record.sample_rate_hz,
                    "relative_stop_seconds": (
                        stop - onset.onset_index
                    )
                    / record.sample_rate_hz,
                    "primary_post_window": bool(
                        segment == "post_fault" and window_id < PRIMARY_POST_WINDOWS
                    ),
                    "electrical_speed_rad_s_median_qc": float(
                        np.median(record.electrical_speed_rad_s[start:stop])
                    ),
                    **features,
                }
            )
    diagnostics: dict[str, object] = {
        **common,
        "samples": len(record.time),
        "duration_seconds": float(
            record.time[-1] - record.time[0] + 1.0 / record.sample_rate_hz
        ),
        "sample_rate_hz": record.sample_rate_hz,
        "fault_onset_index": onset.onset_index,
        "fault_onset_seconds": float(record.time[onset.onset_index]),
        "baseline_stop_index": onset.baseline_stop_index,
        "baseline_median_fault_current_rms": onset.baseline_median,
        "baseline_robust_sigma_fault_current_rms": onset.baseline_robust_sigma,
        "peak_fault_current_rms": onset.peak_rms,
        "fault_current_onset_threshold": onset.threshold,
        "pre_fault_windows": len(pre_bounds),
        "post_fault_windows_up_to_2s": len(post_bounds),
        "primary_post_windows_required": PRIMARY_POST_WINDOWS,
        "main_endpoint_compatible": bool(
            len(pre_bounds) >= 1 and len(post_bounds) >= PRIMARY_POST_WINDOWS
        ),
        "electrical_speed_rad_s_at_onset_qc": float(
            record.electrical_speed_rad_s[onset.onset_index]
        ),
        "property_paths": json.dumps(record.property_paths, sort_keys=True),
    }
    return rows, diagnostics


def discover_official_records(input_dir: Path) -> list[TransientMetadata]:
    paths = sorted(input_dir.rglob("*.mat"))
    records = [parse_transient_record_path(path) for path in paths]
    validate_transient_inventory(records)
    return sorted(records, key=lambda item: (item.motor_watts, item.record_id))


def build_dataset(
    input_dir: Path,
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, dict[str, Any]]:
    """Reveal and process all 21 official records without selective exclusion."""

    records = discover_official_records(input_dir)
    feature_rows: list[dict[str, object]] = []
    diagnostic_rows: list[dict[str, object]] = []
    compatibility_rows: list[dict[str, object]] = []
    file_hashes: dict[str, str] = {}
    expected_errors = (
        IndexError,
        KeyError,
        OSError,
        RuntimeError,
        TypeError,
        ValueError,
    )
    for metadata in records:
        file_hashes[metadata.record_id] = file_sha256(metadata.path)
        status = metadata_fields(metadata)
        try:
            record = load_transient_record(metadata.path)
            rows, diagnostics = build_record_features(record)
            feature_rows.extend(rows)
            diagnostic_rows.append(diagnostics)
            status.update(
                parser_compatible=True,
                main_endpoint_compatible=diagnostics["main_endpoint_compatible"],
                incompatible_reason="",
            )
        except expected_errors as error:
            status.update(
                parser_compatible=False,
                main_endpoint_compatible=False,
                incompatible_reason=f"{type(error).__name__}: {error}",
            )
        compatibility_rows.append(status)

    features = pd.DataFrame(feature_rows)
    diagnostics = pd.DataFrame(diagnostic_rows)
    compatibility = pd.DataFrame(compatibility_rows).sort_values(
        ["motor_watts", "record_id"]
    )
    if not features.empty:
        features = features.sort_values(
            ["motor_watts", "record_id", "segment", "window_id"]
        ).reset_index(drop=True)
    compatible_fraction = (
        compatibility.groupby("motor_id", sort=True)["main_endpoint_compatible"]
        .mean()
        .to_dict()
    )
    metadata: dict[str, Any] = {
        "created_utc": datetime.now(UTC).isoformat(),
        "dataset_doi": "10.5281/zenodo.15631383",
        "records_attempted": len(records),
        "records_parser_compatible": int(compatibility["parser_compatible"].sum()),
        "records_main_endpoint_compatible": int(
            compatibility["main_endpoint_compatible"].sum()
        ),
        "main_endpoint_compatible_fraction_by_motor": compatible_fraction,
        "minimum_required_compatible_fraction_by_motor": 0.8,
        "window_seconds": WINDOW_SECONDS,
        "pre_fault_guard_seconds": PRE_FAULT_GUARD_SECONDS,
        "primary_post_fault_seconds": PRIMARY_POST_SECONDS,
        "maximum_post_fault_seconds": MAXIMUM_POST_SECONDS,
        "forbidden_zero_sequence_features": sorted(
            FORBIDDEN_ZERO_SEQUENCE_FEATURES
        ),
        "loaded_mat_variables": ["ialbt_meas", "if_meas", "we"],
        "scoring_mat_variables": ["ialbt_meas"],
        "label_only_mat_variables": ["if_meas"],
        "qc_only_mat_variables": ["we"],
        "mat_io_version": importlib.metadata.version("mat-io"),
        "file_sha256": file_hashes,
        "selective_record_exclusion": False,
    }
    return features, diagnostics, compatibility, metadata


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--input-dir",
        type=Path,
        default=Path("data/raw/transient_cross_capacity/extracted/OpenData"),
    )
    parser.add_argument(
        "--features",
        type=Path,
        default=Path("data/processed/transient_pmsm_features.csv.gz"),
    )
    parser.add_argument(
        "--results-dir",
        type=Path,
        default=Path("results/transient_feature_build"),
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    features, diagnostics, compatibility, metadata = build_dataset(args.input_dir)
    args.features.parent.mkdir(parents=True, exist_ok=True)
    args.results_dir.mkdir(parents=True, exist_ok=True)
    features.to_csv(
        args.features,
        index=False,
        compression={"method": "gzip", "compresslevel": 1, "mtime": 0},
    )
    diagnostics.to_csv(args.results_dir / "onset_diagnostics.csv", index=False)
    compatibility.to_csv(args.results_dir / "record_compatibility.csv", index=False)
    metadata["feature_rows"] = len(features)
    metadata["feature_table_sha256"] = file_sha256(args.features)
    (args.results_dir / "run_metadata.json").write_text(
        json.dumps(metadata, indent=2, sort_keys=True), encoding="utf-8"
    )
    print(
        f"processed all {metadata['records_attempted']} records; "
        f"main-compatible={metadata['records_main_endpoint_compatible']}, "
        f"feature rows={len(features)}"
    )


if __name__ == "__main__":
    main()
