"""Audit the eight health-only dual-three-phase PMSM MAT records.

This script is deliberately offline.  It opens only the eight predeclared
``flt0z`` files and refuses to run if any other MAT file is present in the
input directory.  No fault record is downloaded or inspected.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import re
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
from scipy.io import loadmat, whosmat

ZENODO_RECORD = "13889418"
ZENODO_DOI = "10.5281/zenodo.13889418"
ZENODO_API = f"https://zenodo.org/api/records/{ZENODO_RECORD}"
LICENSE = "CC BY 4.0"

LOADS_NM = (0, 5, 10, 15, 20, 25, 30, 35)
HEALTH_TEST_LOADS_NM = (5, 15, 25, 35)
CALIBRATION_LOADS_NM = (10, 20, 30)
ADAPTATION_LOAD_NM = 0

WINDOW_SECONDS = 0.2
BLOCK_SECONDS = 3.0
ALPHA = 0.05
ANALYSIS_BLOCK_IDS = tuple(range(4, 12))
ADAPTATION_BLOCK_IDS = tuple(range(4, 8))
FEATURE_FREQUENCY_BAND_HZ = (20.0, 500.0)
EXPECTED_SAMPLE_RATE_HZ = 10_000.0

OFFICIAL_MD5 = {
    0: "68c12378db1a4c1f8b9599a3d370a4bd",
    5: "c0e11a2bfbb9ac300dd868e92714930f",
    10: "706f5a6aec4ca05f2a0cb5a568e8607e",
    15: "6adce23cb2b583ee0bd1e214fe42e0b7",
    20: "2b5e9f199e5ceb3ac76b98242370b2e7",
    25: "c5cd94592549ed56a5fb1b7a0c1fef6d",
    30: "50a60b832327e8c8052c76d63fb5a268",
    35: "8d6c9e847d6ea60413d5564c52101a77",
}

EXPECTED_VARIABLES = (
    "Currents_SubSys1_A",
    "Currents_SubSys1_B",
    "Currents_SubSys1_C",
    "Currents_SubSys1_d",
    "Currents_SubSys1_q",
    "Currents_SubSys2_A",
    "Currents_SubSys2_B",
    "Currents_SubSys2_C",
    "Currents_SubSys2_d",
    "Currents_SubSys2_q",
    "SinCos_Electrical_Cos",
    "SinCos_Electrical_Sin",
    "Speed_rad_el",
    "Speed_requred_rad_el",
    "Speed_requred_rpm",
    "Speed_rpm",
    "Time",
    "Voltage_SubSys1_d",
    "Voltage_SubSys1_q",
    "Voltage_SubSys2_d",
    "Voltage_SubSys2_q",
)

CURRENT_CHANNELS = (
    "Currents_SubSys1_A",
    "Currents_SubSys1_B",
    "Currents_SubSys1_C",
    "Currents_SubSys2_A",
    "Currents_SubSys2_B",
    "Currents_SubSys2_C",
)

AUDIT_VECTORS = CURRENT_CHANNELS + (
    "Speed_rad_el",
    "Speed_requred_rad_el",
    "Speed_requred_rpm",
    "Speed_rpm",
    "Time",
)

HEALTH_FILENAME = re.compile(r"^spd10-5000rpm_flt0z_(\d+)NM\.mat$")


def expected_filename(load_nm: int) -> str:
    """Return the only allowed health filename for a load."""

    return f"spd10-5000rpm_flt0z_{load_nm}NM.mat"


def parse_load_nm(path: Path) -> int:
    """Extract load torque from an exact health-record filename."""

    match = HEALTH_FILENAME.fullmatch(path.name)
    if match is None:
        raise ValueError(f"Not a declared health filename: {path.name}")
    load_nm = int(match.group(1))
    if load_nm not in LOADS_NM:
        raise ValueError(f"Unexpected healthy load: {load_nm} Nm")
    return load_nm


def file_digest(path: Path, algorithm: str) -> str:
    """Hash a file without materializing it in memory."""

    if algorithm == "md5":
        digest = hashlib.md5(usedforsecurity=False)
    elif algorithm == "sha256":
        digest = hashlib.sha256()
    else:
        raise ValueError(f"Unsupported digest: {algorithm}")
    with path.open("rb") as stream:
        while chunk := stream.read(8 * 1024 * 1024):
            digest.update(chunk)
    return digest.hexdigest()


def vector_digest(values: np.ndarray) -> str:
    """Return a stable digest for comparison of numeric traces."""

    canonical = np.ascontiguousarray(np.asarray(values, dtype="<f8").reshape(-1))
    return hashlib.sha256(canonical.tobytes()).hexdigest()


def minimum_calibration_blocks(alpha: float) -> int:
    """Fewest calibration units that can resolve an upper-tail level."""

    if not 0.0 < alpha < 1.0:
        raise ValueError("alpha must lie strictly between zero and one")
    return max(1, math.ceil((1.0 / alpha) - 1.0 - 1e-12))


def calibration_feasibility(calibration_blocks: int, alpha: float = ALPHA) -> dict[str, Any]:
    """Summarize finite conformal resolution without asserting exchangeability."""

    if calibration_blocks < 1:
        raise ValueError("calibration_blocks must be positive")
    rank = math.ceil((calibration_blocks + 1) * (1.0 - alpha) - 1e-12)
    minimum_p = 1.0 / (calibration_blocks + 1.0)
    return {
        "alpha": alpha,
        "calibration_blocks": calibration_blocks,
        "minimum_required_blocks": minimum_calibration_blocks(alpha),
        "minimum_attainable_p_value": minimum_p,
        "upper_threshold_order_statistic_rank": rank,
        "finite_upper_threshold": rank <= calibration_blocks,
        "alarm_is_numerically_resolvable": minimum_p <= alpha + 1e-12,
    }


def variable_role(name: str) -> str:
    """Assign a compact semantic role to an audited MAT variable."""

    if name in CURRENT_CHANNELS:
        return "primary_abc_current"
    if name.startswith("Currents_SubSys"):
        return "dq_current_not_scored"
    if name.startswith("Voltage_SubSys"):
        return "dq_control_voltage_not_scored"
    if name == "Time":
        return "timebase"
    if name.startswith("Speed"):
        return "speed_qc_not_scored"
    if name.startswith("SinCos_Electrical"):
        return "electrical_position_not_scored"
    return "other"


def protocol_role(load_nm: int, block_id: int) -> str:
    """Return the frozen record-disjoint role for one complete block."""

    if load_nm == ADAPTATION_LOAD_NM and block_id in ADAPTATION_BLOCK_IDS:
        return "adaptation"
    if load_nm in CALIBRATION_LOADS_NM and block_id in ANALYSIS_BLOCK_IDS:
        return "calibration"
    if load_nm in HEALTH_TEST_LOADS_NM and block_id in ANALYSIS_BLOCK_IDS:
        return "health_test"
    return "unused"


def _numeric_vector(data: dict[str, Any], name: str) -> np.ndarray:
    if name not in data:
        raise ValueError(f"MAT file is missing {name}")
    vector = np.asarray(data[name]).reshape(-1)
    if not np.issubdtype(vector.dtype, np.number):
        raise TypeError(f"{name} is not numeric")
    if vector.size == 0 or not np.isfinite(vector).all():
        raise ValueError(f"{name} is empty or contains non-finite values")
    return vector


def audit_health_file(path: Path) -> tuple[dict[str, Any], list[dict[str, Any]], list[dict[str, Any]]]:
    """Audit one declared health MAT file and enumerate its complete blocks."""

    load_nm = parse_load_nm(path)
    inventory = whosmat(path)
    names = {name for name, _, _ in inventory}
    missing = sorted(set(EXPECTED_VARIABLES).difference(names))
    if missing:
        raise ValueError(f"{path.name} is missing expected variables: {missing}")

    variable_rows = [
        {
            "file": path.name,
            "load_nm": load_nm,
            "variable": name,
            "shape": "x".join(str(item) for item in shape),
            "elements": math.prod(shape),
            "matlab_class": matlab_class,
            "role": variable_role(name),
        }
        for name, shape, matlab_class in inventory
    ]

    loaded = loadmat(
        path,
        variable_names=list(AUDIT_VECTORS),
        squeeze_me=True,
        struct_as_record=False,
    )
    vectors = {name: _numeric_vector(loaded, name) for name in AUDIT_VECTORS}
    time = np.asarray(vectors["Time"], dtype=np.float64)
    n_samples = time.size
    unequal = {name: vector.size for name, vector in vectors.items() if vector.size != n_samples}
    if unequal:
        raise ValueError(f"Signals do not share the Time length in {path.name}: {unequal}")
    differences = np.diff(time)
    if differences.size == 0 or np.any(differences <= 0):
        raise ValueError(f"Time must be strictly increasing in {path.name}")
    median_step = float(np.median(differences))
    sample_rate_hz = 1.0 / median_step
    relative_step_deviation = float(np.max(np.abs(differences - median_step)) / median_step)
    duration_seconds = float(time[-1] - time[0])
    complete_windows = math.floor((duration_seconds + 1e-10) / WINDOW_SECONDS)
    complete_blocks = math.floor((duration_seconds + 1e-10) / BLOCK_SECONDS)
    samples_per_block = round(sample_rate_hz * BLOCK_SECONDS)
    speed_rpm = np.asarray(vectors["Speed_rpm"], dtype=np.float64)
    electrical_hz = np.asarray(vectors["Speed_rad_el"], dtype=np.float64) / (2.0 * np.pi)
    required_speed_rpm = np.asarray(vectors["Speed_requred_rpm"], dtype=np.float64)

    valid_ratio = np.abs(speed_rpm) >= 100.0
    pole_pair_ratio = np.asarray([], dtype=np.float64)
    if valid_ratio.any():
        mechanical_hz = speed_rpm[valid_ratio] / 60.0
        pole_pair_ratio = electrical_hz[valid_ratio] / mechanical_hz

    low_hz, high_hz = FEATURE_FREQUENCY_BAND_HZ
    block_rows: list[dict[str, Any]] = []
    for block_id in range(complete_blocks):
        start = block_id * samples_per_block
        stop = start + samples_per_block
        if stop > n_samples:
            raise ValueError(f"Sample/time block counts disagree in {path.name}")
        block_electrical_hz = electrical_hz[start:stop]
        block_speed_rpm = speed_rpm[start:stop]
        in_band = (block_electrical_hz >= low_hz) & (block_electrical_hz <= high_hz)
        block_rows.append(
            {
                "file": path.name,
                "load_nm": load_nm,
                "block_id": block_id,
                "start_seconds": block_id * BLOCK_SECONDS,
                "stop_seconds": (block_id + 1) * BLOCK_SECONDS,
                "start_sample": start,
                "stop_sample_exclusive": stop,
                "samples": samples_per_block,
                "windows_0p2s": round(BLOCK_SECONDS / WINDOW_SECONDS),
                "speed_rpm_min": float(np.min(block_speed_rpm)),
                "speed_rpm_median": float(np.median(block_speed_rpm)),
                "speed_rpm_max": float(np.max(block_speed_rpm)),
                "electrical_hz_min": float(np.min(block_electrical_hz)),
                "electrical_hz_median": float(np.median(block_electrical_hz)),
                "electrical_hz_max": float(np.max(block_electrical_hz)),
                "feature_band_fraction": float(np.mean(in_band)),
                "fully_inside_20_500hz_feature_band": bool(np.all(in_band)),
                "inside_frozen_12_36s_segment": block_id in ANALYSIS_BLOCK_IDS,
                "protocol_role": protocol_role(load_nm, block_id),
            }
        )

    file_row: dict[str, Any] = {
        "file": path.name,
        "load_nm": load_nm,
        "bytes": path.stat().st_size,
        "md5": file_digest(path, "md5"),
        "sha256": file_digest(path, "sha256"),
        "variables": len(inventory),
        "samples": n_samples,
        "time_start_seconds": float(time[0]),
        "time_stop_seconds": float(time[-1]),
        "duration_seconds": duration_seconds,
        "sample_rate_hz": sample_rate_hz,
        "maximum_relative_time_step_deviation": relative_step_deviation,
        "complete_0p2s_windows": complete_windows,
        "complete_3s_blocks": complete_blocks,
        "tail_after_complete_blocks_seconds": duration_seconds - complete_blocks * BLOCK_SECONDS,
        "speed_rpm_min": float(np.min(speed_rpm)),
        "speed_rpm_max": float(np.max(speed_rpm)),
        "required_speed_rpm_min": float(np.min(required_speed_rpm)),
        "required_speed_rpm_max": float(np.max(required_speed_rpm)),
        "electrical_hz_min": float(np.min(electrical_hz)),
        "electrical_hz_max": float(np.max(electrical_hz)),
        "pole_pair_ratio_median_above_100rpm": (
            float(np.median(pole_pair_ratio)) if pole_pair_ratio.size else float("nan")
        ),
        "time_trace_sha256": vector_digest(time),
        "required_speed_trace_sha256": vector_digest(required_speed_rpm),
        "all_required_vectors_finite": True,
    }
    return file_row, variable_rows, block_rows


def audit_dataset(
    input_dir: Path, *, verify_official_hashes: bool = True
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, dict[str, Any]]:
    """Audit exactly eight health files and construct the frozen split summary."""

    expected_paths = [input_dir / expected_filename(load_nm) for load_nm in LOADS_NM]
    missing = [path.name for path in expected_paths if not path.is_file()]
    if missing:
        raise FileNotFoundError(f"Missing health files: {missing}")
    expected_names = {path.name for path in expected_paths}
    unexpected_mat = sorted(path.name for path in input_dir.glob("*.mat") if path.name not in expected_names)
    if unexpected_mat:
        raise RuntimeError(
            "Health-only audit refuses a directory containing undeclared MAT files: "
            f"{unexpected_mat}"
        )

    file_rows: list[dict[str, Any]] = []
    variable_rows: list[dict[str, Any]] = []
    block_rows: list[dict[str, Any]] = []
    for path in expected_paths:
        file_row, file_variables, file_blocks = audit_health_file(path)
        if verify_official_hashes and file_row["md5"] != OFFICIAL_MD5[file_row["load_nm"]]:
            raise RuntimeError(f"Official MD5 mismatch for {path.name}")
        file_rows.append(file_row)
        variable_rows.extend(file_variables)
        block_rows.extend(file_blocks)

    files = pd.DataFrame(file_rows).sort_values("load_nm").reset_index(drop=True)
    variables = pd.DataFrame(variable_rows).sort_values(["load_nm", "variable"]).reset_index(drop=True)
    blocks = pd.DataFrame(block_rows).sort_values(["load_nm", "block_id"]).reset_index(drop=True)

    if not np.allclose(files["sample_rate_hz"], EXPECTED_SAMPLE_RATE_HZ, rtol=1e-9, atol=1e-6):
        raise RuntimeError("At least one health file is not sampled at 10 kHz")
    if files["samples"].nunique() != 1 or files["duration_seconds"].nunique() != 1:
        raise RuntimeError("Health-file lengths are inconsistent")
    analysis = blocks[blocks["inside_frozen_12_36s_segment"]]
    if len(analysis) != len(LOADS_NM) * len(ANALYSIS_BLOCK_IDS):
        raise RuntimeError("The frozen [12, 36) s segment is incomplete")
    if not analysis["fully_inside_20_500hz_feature_band"].all():
        raise RuntimeError("The frozen [12, 36) s segment leaves the 20-500 Hz feature band")

    role_counts = blocks["protocol_role"].value_counts().astype(int).to_dict()
    expected_role_counts = {"adaptation": 4, "calibration": 24, "health_test": 32}
    for role, count in expected_role_counts.items():
        if role_counts.get(role, 0) != count:
            raise RuntimeError(f"Expected {count} {role} blocks, got {role_counts.get(role, 0)}")

    calibration = calibration_feasibility(role_counts["calibration"], ALPHA)
    common_segment = {
        "speed_rpm_min": float(analysis["speed_rpm_min"].min()),
        "speed_rpm_max": float(analysis["speed_rpm_max"].max()),
        "electrical_hz_min": float(analysis["electrical_hz_min"].min()),
        "electrical_hz_max": float(analysis["electrical_hz_max"].max()),
        "pole_pair_ratio_median_above_100rpm": float(
            files["pole_pair_ratio_median_above_100rpm"].median()
        ),
    }
    summary: dict[str, Any] = {
        "dataset": {
            "title": "Measurement of interturn short-circuits emulation on dual three-phase PMS motor",
            "doi": ZENODO_DOI,
            "record": ZENODO_RECORD,
            "official_api": ZENODO_API,
            "license": LICENSE,
        },
        "audit_scope": {
            "health_files_expected": len(LOADS_NM),
            "health_files_audited": len(files),
            "fault_files_read": 0,
            "unexpected_mat_files_allowed": False,
            "official_md5_verified": verify_official_hashes,
        },
        "common_structure": {
            "samples_per_file": int(files["samples"].iloc[0]),
            "sample_rate_hz": float(files["sample_rate_hz"].median()),
            "duration_seconds": float(files["duration_seconds"].iloc[0]),
            "complete_0p2s_windows_per_file": int(files["complete_0p2s_windows"].iloc[0]),
            "complete_3s_blocks_per_file": int(files["complete_3s_blocks"].iloc[0]),
            "variables_per_file": int(files["variables"].iloc[0]),
            "variable_schema_identical": bool(
                variables.groupby("load_nm")["variable"].apply(tuple).nunique() == 1
            ),
            "time_trace_unique_hashes": int(files["time_trace_sha256"].nunique()),
            "required_speed_trace_unique_hashes": int(
                files["required_speed_trace_sha256"].nunique()
            ),
        },
        "frozen_protocol": {
            "window_seconds": WINDOW_SECONDS,
            "block_seconds": BLOCK_SECONDS,
            "block_aggregation": "system maximum after subsystem maximum",
            "analysis_interval_seconds_half_open": [12.0, 36.0],
            "analysis_block_ids": list(ANALYSIS_BLOCK_IDS),
            "adaptation": {
                "loads_nm": [ADAPTATION_LOAD_NM],
                "block_ids": list(ADAPTATION_BLOCK_IDS),
                "blocks": role_counts["adaptation"],
                "seconds": role_counts["adaptation"] * BLOCK_SECONDS,
            },
            "calibration": {
                "loads_nm": list(CALIBRATION_LOADS_NM),
                "block_ids_per_record": list(ANALYSIS_BLOCK_IDS),
                "blocks": role_counts["calibration"],
            },
            "health_test": {
                "loads_nm": list(HEALTH_TEST_LOADS_NM),
                "block_ids_per_record": list(ANALYSIS_BLOCK_IDS),
                "blocks": role_counts["health_test"],
                "records": len(HEALTH_TEST_LOADS_NM),
            },
        },
        "common_segment_observed_range": common_segment,
        "calibration_feasibility": {
            **calibration,
            "one_file_complete_3s_blocks": int(files["complete_3s_blocks"].iloc[0]),
            "one_file_common_segment_blocks": len(ANALYSIS_BLOCK_IDS),
            "one_file_can_supply_20_blocks": False,
            "calibration_records_pooled": len(CALIBRATION_LOADS_NM),
            "ordinary_exchangeable_conformal_guarantee_claimed": False,
            "interpretation": "empirical block-risk calibration across record-disjoint loads",
        },
        "health_record_independence": {
            "distinct_files": len(files),
            "distinct_loads": len(files),
            "independent_machines": 1,
            "replicates_per_load": 1,
            "sessions_documented_by_repository_metadata": False,
            "identical_time_trace_across_files": files["time_trace_sha256"].nunique() == 1,
            "identical_required_speed_trace_across_files": (
                files["required_speed_trace_sha256"].nunique() == 1
            ),
            "statistical_independence_claimed": False,
        },
    }
    return files, variables, blocks, summary


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--input-dir",
        type=Path,
        default=Path("data/raw/external_validation/dual_three_phase_health"),
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("results/external_health_audit"),
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    files, variables, blocks, summary = audit_dataset(args.input_dir)
    args.output_dir.mkdir(parents=True, exist_ok=True)
    files.to_csv(args.output_dir / "health_files.csv", index=False)
    variables.to_csv(args.output_dir / "mat_variables.csv", index=False)
    blocks.to_csv(args.output_dir / "block_inventory.csv", index=False)
    (args.output_dir / "summary.json").write_text(
        json.dumps(summary, indent=2, sort_keys=True), encoding="utf-8"
    )
    print(
        f"audited {len(files)} health files; wrote {args.output_dir.resolve()} "
        f"({summary['frozen_protocol']['calibration']['blocks']} calibration blocks)"
    )


if __name__ == "__main__":
    main()
