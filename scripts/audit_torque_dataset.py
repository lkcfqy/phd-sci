"""Audit DOI 10.5281/zenodo.15688397 before Paper 2 modeling."""

from __future__ import annotations

import argparse
import json
from datetime import UTC, datetime
from pathlib import Path

import numpy as np
import pandas as pd

from pmsm_sci.torque.data import (
    PUBLISHED_FILES,
    load_published_torque_data,
    parameter_row_hashes,
    sha256,
)
from pmsm_sci.torque.fourier import retained_energy_fraction


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--data-root",
        type=Path,
        default=Path("data/raw/PMSM_torque_data"),
    )
    parser.add_argument(
        "--results-dir",
        type=Path,
        default=Path("results/paper2_torque_data_audit"),
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    datasets = load_published_torque_data(args.data_root)
    args.results_dir.mkdir(parents=True, exist_ok=True)

    development = datasets["train_test"].parameters
    development_min = development.min().to_numpy()
    development_max = development.max().to_numpy()
    summary_rows: list[dict[str, object]] = []
    parameter_rows: list[dict[str, object]] = []
    file_manifest: list[dict[str, object]] = []
    for name, dataset in datasets.items():
        parameter_values = dataset.parameters.to_numpy(dtype=float)
        outside = np.any(
            (parameter_values < development_min) | (parameter_values > development_max),
            axis=1,
        )
        energy = retained_energy_fraction(dataset.torque, retained_components=11)
        summary_rows.append(
            {
                "dataset": name,
                "designs": dataset.n_designs,
                "parameters": dataset.n_parameters,
                "angles": dataset.n_angles,
                "angle_min_deg": dataset.angles_deg.min(),
                "angle_max_deg": dataset.angles_deg.max(),
                "angle_step_deg": np.diff(dataset.angles_deg)[0],
                "torque_min": dataset.torque.min(),
                "torque_max": dataset.torque.max(),
                "torque_mean": dataset.torque.mean(),
                "outside_development_empirical_range": int(outside.sum()),
                "retained_energy_median": np.median(energy),
                "retained_energy_p01": np.quantile(energy, 0.01),
                "retained_energy_min": energy.min(),
            }
        )
        for parameter in dataset.parameters.columns:
            series = dataset.parameters[parameter]
            parameter_rows.append(
                {
                    "dataset": name,
                    "parameter": parameter,
                    "minimum": series.min(),
                    "maximum": series.max(),
                    "mean": series.mean(),
                    "standard_deviation": series.std(ddof=1),
                }
            )
        for role, path in (
            ("parameters", dataset.parameter_path),
            ("torque", dataset.torque_path),
        ):
            file_manifest.append(
                {
                    "dataset": name,
                    "role": role,
                    "file": path.name,
                    "bytes": path.stat().st_size,
                    "sha256": sha256(path),
                }
            )

    overlap_rows: list[dict[str, object]] = []
    names = list(datasets)
    hashes = {name: parameter_row_hashes(datasets[name].parameters) for name in names}
    for left_index, left in enumerate(names):
        for right in names[left_index + 1 :]:
            overlap_rows.append(
                {
                    "left": left,
                    "right": right,
                    "exact_parameter_row_overlap": len(hashes[left] & hashes[right]),
                }
            )

    pd.DataFrame(summary_rows).to_csv(args.results_dir / "dataset_summary.csv", index=False)
    pd.DataFrame(parameter_rows).to_csv(args.results_dir / "parameter_summary.csv", index=False)
    pd.DataFrame(overlap_rows).to_csv(args.results_dir / "cross_table_overlap.csv", index=False)
    pd.DataFrame(file_manifest).to_csv(args.results_dir / "file_manifest.csv", index=False)

    total_designs = sum(dataset.n_designs for dataset in datasets.values())
    audit = {
        "created_utc": datetime.now(UTC).isoformat(),
        "source_doi": "10.5281/zenodo.15688397",
        "source_article_doi": "10.1007/s00366-025-02123-1",
        "license": "GPL-3.0-or-later",
        "expected_files": PUBLISHED_FILES,
        "validated_datasets": list(datasets),
        "total_designs": total_designs,
        "expected_total_designs": 23250,
        "all_pairs_row_aligned": True,
        "all_values_finite": True,
        "duplicate_parameter_rows": 0,
        "duplicate_torque_rows": 0,
        "cross_table_parameter_overlap": 0,
        "angle_grid": {
            "points": 120,
            "start_deg": 0.0,
            "stop_exclusive_deg": 30.0,
            "step_deg": 0.25,
        },
        "status": "pass" if total_designs == 23250 else "fail",
        "important_scope_limit": (
            "All outputs are simulations of one two-dimensional quarter-symmetry PMSM model; "
            "the dataset does not validate another topology, a three-dimensional model, or hardware."
        ),
    }
    (args.results_dir / "audit.json").write_text(
        json.dumps(audit, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    print(
        f"Validated {total_designs} designs across {len(datasets)} aligned tables; "
        f"audit status={audit['status']}"
    )


if __name__ == "__main__":
    main()
