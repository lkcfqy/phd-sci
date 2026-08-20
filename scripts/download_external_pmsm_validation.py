"""Download and verify the staged external PMSM validation files from Zenodo.

The default stage downloads the compact 200 W/20 kW transient dataset and all
eight healthy files from the dual-three-phase PMSM dataset. The 48 fault records
are available only through the explicit ``dual_three_phase_fault_reveal`` choice,
which must not be used until the health-only protocol and scoring code are frozen.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import requests

DATASETS = {
    "transient_cross_capacity": {
        "record": "15631383",
        "files": ("OpenData.zip",),
        "doi": "10.5281/zenodo.15631383",
        "license": "CC BY 4.0",
    },
    "dual_three_phase_health": {
        "record": "13889418",
        "files": tuple(
            f"spd10-5000rpm_flt0z_{load}NM.mat"
            for load in (0, 5, 10, 15, 20, 25, 30, 35)
        ),
        "doi": "10.5281/zenodo.13889418",
        "license": "CC BY 4.0",
    },
    "dual_three_phase_fault_reveal": {
        "record": "13889418",
        "files": tuple(
            f"spd10-5000rpm_flt{turns}z{phase}_{load}NM.mat"
            for turns, phase in ((1, "u"), (2, "v"), (3, "u"), (4, "v"), (5, "u"), (6, "u"))
            for load in (0, 5, 10, 15, 20, 25, 30, 35)
        ),
        "doi": "10.5281/zenodo.13889418",
        "license": "CC BY 4.0",
        "output_subdir": "dual_three_phase_health",
    },
}
DEFAULT_DATASETS = ("transient_cross_capacity", "dual_three_phase_health")


def file_md5(path: Path, chunk_size: int = 8 * 1024 * 1024) -> str:
    digest = hashlib.md5(usedforsecurity=False)
    with path.open("rb") as stream:
        while chunk := stream.read(chunk_size):
            digest.update(chunk)
    return digest.hexdigest()


def fetch_files(record: str) -> dict[str, dict[str, object]]:
    response = requests.get(f"https://zenodo.org/api/records/{record}", timeout=60)
    response.raise_for_status()
    files = response.json().get("files")
    if not isinstance(files, list):
        raise TypeError(f"Zenodo record {record} did not return a file list")
    return {str(item["key"]): item for item in files}


def download_file(
    metadata: dict[str, object], output_dir: Path, *, max_retries: int
) -> dict[str, object]:
    filename = str(metadata["key"])
    expected_size = int(metadata["size"])
    checksum = str(metadata["checksum"])
    algorithm, expected_hash = checksum.split(":", maxsplit=1)
    if algorithm != "md5":
        raise ValueError(f"Unexpected Zenodo checksum algorithm: {algorithm}")
    links = metadata["links"]
    if not isinstance(links, dict):
        raise TypeError("Zenodo file links must be a mapping")
    url = str(links["self"])
    destination = output_dir / filename
    partial = destination.with_suffix(destination.suffix + ".part")

    if destination.exists():
        actual_hash = file_md5(destination)
        if destination.stat().st_size == expected_size and actual_hash == expected_hash:
            print(f"verified existing {destination}")
            return {
                "file": filename,
                "bytes": expected_size,
                "md5": actual_hash,
                "source_url": url,
            }
        raise RuntimeError(f"Existing file failed verification: {destination}")

    retries = 0
    while (partial.stat().st_size if partial.exists() else 0) < expected_size:
        offset = partial.stat().st_size if partial.exists() else 0
        headers = {"Range": f"bytes={offset}-"} if offset else {}
        try:
            with requests.get(
                url, headers=headers, stream=True, timeout=(60, 300)
            ) as response:
                response.raise_for_status()
                if offset and response.status_code != 206:
                    raise RuntimeError("Zenodo did not honor the resume Range request")
                mode = "ab" if offset else "wb"
                with partial.open(mode) as stream:
                    for chunk in response.iter_content(chunk_size=8 * 1024 * 1024):
                        if chunk:
                            stream.write(chunk)
                            offset += len(chunk)
                            print(
                                f"\r{filename}: {offset / 1e6:.1f}/"
                                f"{expected_size / 1e6:.1f} MB",
                                end="",
                                flush=True,
                            )
        except requests.RequestException as error:
            retries += 1
            if retries > max_retries:
                raise RuntimeError(
                    f"Download failed after {max_retries} retries: {filename}"
                ) from error
            resumed = partial.stat().st_size if partial.exists() else 0
            print(f"\nconnection interrupted; retry {retries} from byte {resumed}")
    print()

    if partial.stat().st_size != expected_size:
        raise RuntimeError(f"Size mismatch for {filename}")
    actual_hash = file_md5(partial)
    if actual_hash != expected_hash:
        raise RuntimeError(f"MD5 mismatch for {filename}: {actual_hash}")
    partial.replace(destination)
    return {
        "file": filename,
        "bytes": expected_size,
        "md5": actual_hash,
        "source_url": url,
    }


def planned_file(metadata: dict[str, object]) -> dict[str, object]:
    """Return immutable Zenodo metadata without opening the file content URL."""

    filename = str(metadata["key"])
    checksum = str(metadata["checksum"])
    algorithm, expected_hash = checksum.split(":", maxsplit=1)
    if algorithm != "md5":
        raise ValueError(f"Unexpected Zenodo checksum algorithm: {algorithm}")
    links = metadata["links"]
    if not isinstance(links, dict):
        raise TypeError("Zenodo file links must be a mapping")
    return {
        "file": filename,
        "bytes": int(metadata["size"]),
        "md5": expected_hash,
        "source_url": str(links["self"]),
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--output-dir", type=Path, default=Path("data/raw/external_validation")
    )
    parser.add_argument(
        "--datasets",
        nargs="+",
        choices=sorted(DATASETS),
        default=list(DEFAULT_DATASETS),
    )
    parser.add_argument("--max-retries", type=int, default=10)
    parser.add_argument(
        "--workers",
        type=int,
        default=1,
        help="parallel file downloads; each file is still verified independently",
    )
    parser.add_argument(
        "--plan-only",
        action="store_true",
        help="write the official file/size/MD5 plan without downloading content",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    if not 1 <= args.workers <= 8:
        raise ValueError("workers must lie between 1 and 8")
    manifest_name = "fault_reveal_plan.json" if args.plan_only else "staged_download_manifest.json"
    manifest_path = args.output_dir / manifest_name
    manifest: list[dict[str, object]] = []
    if manifest_path.exists() and not args.plan_only:
        existing = json.loads(manifest_path.read_text(encoding="utf-8"))
        if not isinstance(existing, list):
            raise TypeError("The staged download manifest must contain a list")
        selected = set(args.datasets)
        manifest.extend(
            item
            for item in existing
            if isinstance(item, dict) and item.get("dataset") not in selected
        )
    for name in args.datasets:
        specification = DATASETS[name]
        record = str(specification["record"])
        files = fetch_files(record)
        dataset_dir = args.output_dir / str(specification.get("output_subdir", name))
        if not args.plan_only:
            dataset_dir.mkdir(parents=True, exist_ok=True)
        requested_files = list(specification["files"])
        for filename in requested_files:
            if filename not in files:
                raise FileNotFoundError(f"{filename} is absent from Zenodo record {record}")

        def retrieve(
            filename: str,
            record_files: dict[str, dict[str, object]] = files,
            destination: Path = dataset_dir,
        ) -> dict[str, object]:
            if args.plan_only:
                return planned_file(record_files[filename])
            return download_file(
                record_files[filename], destination, max_retries=args.max_retries
            )

        if args.workers == 1 or args.plan_only:
            results = map(retrieve, requested_files)
        else:
            executor = ThreadPoolExecutor(max_workers=args.workers)
            results = executor.map(retrieve, requested_files)
        for result in results:
            manifest.append(
                {
                    "dataset": name,
                    "doi": specification["doi"],
                    "license": specification["license"],
                    **result,
                }
            )
        if args.workers > 1 and not args.plan_only:
            executor.shutdown()
    manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    print(f"wrote {manifest_path.resolve()}")


if __name__ == "__main__":
    main()
