"""Post-reveal sensitivity builder for implicit MATLAB uniform time metadata.

The primary frozen parser required an explicit time vector and failed all 21 records.
This separate entry point reconstructs time only from ``tsdata.timemetadata`` fields
``Start_``, ``Increment_``, and ``Length``.  It never overwrites the primary reveal.
"""

from __future__ import annotations

import argparse
import functools
import json
from pathlib import Path

from build_transient_pmsm_features import build_dataset, file_sha256

from pmsm_sci.faults.transient_external import load_transient_record


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
        default=Path(
            "data/processed/transient_pmsm_features_post_reveal_implicit_time.csv.gz"
        ),
    )
    parser.add_argument(
        "--results-dir",
        type=Path,
        default=Path("results/transient_feature_build_post_reveal_implicit_time"),
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    loader = functools.partial(
        load_transient_record,
        allow_implicit_uniform_time=True,
    )
    features, diagnostics, compatibility, metadata = build_dataset(
        args.input_dir,
        record_loader=loader,
        parser_mode="post_reveal_implicit_uniform_time_metadata",
    )
    metadata["status"] = "post_reveal_sensitivity_not_primary_reveal"
    metadata["primary_reveal_commit"] = "be0ca54"
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
        "POST-REVEAL implicit-time sensitivity: "
        f"attempted={metadata['records_attempted']}, "
        f"main-compatible={metadata['records_main_endpoint_compatible']}, "
        f"feature rows={len(features)}"
    )


if __name__ == "__main__":
    main()
