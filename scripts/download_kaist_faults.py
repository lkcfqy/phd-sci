"""Download and verify the three KAIST PMSM stator-fault archives.

The archives total about 7 GB. Downloads are resumable and are written to a
``.part`` file until their SHA-256 digest matches the published metadata.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

import requests

DATASET_ID = "rgn5brrgrn"
VERSION = 5
API_URL = (
    "https://data.mendeley.com/public-api/datasets/"
    f"{DATASET_ID}/files?folder_id=root&version={VERSION}"
)
DOWNLOAD_URL = (
    "https://data.mendeley.com/public-files/datasets/"
    f"{DATASET_ID}/files/{{file_id}}/file_downloaded"
)


def sha256(path: Path, chunk_size: int = 8 * 1024 * 1024) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        while chunk := stream.read(chunk_size):
            digest.update(chunk)
    return digest.hexdigest()


def fetch_manifest() -> list[dict[str, object]]:
    response = requests.get(API_URL, timeout=60)
    response.raise_for_status()
    records = response.json()
    if not isinstance(records, list) or len(records) != 3:
        raise RuntimeError(f"Unexpected Mendeley manifest: {records!r}")
    return records


def download(
    record: dict[str, object], output_dir: Path, *, max_retries: int
) -> dict[str, object]:
    filename = str(record["filename"])
    expected_size = int(record["size"])
    details = record["content_details"]
    if not isinstance(details, dict):
        raise TypeError("content_details must be a mapping")
    expected_hash = str(details["sha256_hash"])
    destination = output_dir / filename
    partial = destination.with_suffix(destination.suffix + ".part")

    if destination.exists():
        actual_hash = sha256(destination)
        if destination.stat().st_size == expected_size and actual_hash == expected_hash:
            print(f"verified existing {filename}")
            return {"file": filename, "bytes": expected_size, "sha256": actual_hash}
        raise RuntimeError(f"Existing file failed verification: {destination}")

    url = DOWNLOAD_URL.format(file_id=record["id"])
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
                    raise RuntimeError("Server did not honor the resume Range request")
                mode = "ab" if offset else "wb"
                with partial.open(mode) as stream:
                    for chunk in response.iter_content(chunk_size=8 * 1024 * 1024):
                        if chunk:
                            stream.write(chunk)
                            offset += len(chunk)
                            print(
                                f"\r{filename}: "
                                f"{offset / 1e9:.2f}/{expected_size / 1e9:.2f} GB",
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
        raise RuntimeError(
            f"Size mismatch for {filename}: {partial.stat().st_size} != {expected_size}"
        )
    actual_hash = sha256(partial)
    if actual_hash != expected_hash:
        raise RuntimeError(f"SHA-256 mismatch for {filename}: {actual_hash}")
    partial.replace(destination)
    return {"file": filename, "bytes": expected_size, "sha256": actual_hash}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, default=Path("data/raw/kaist_faults"))
    parser.add_argument(
        "--motors",
        nargs="+",
        default=["1.0kW", "1.5kW", "3.0kW"],
        choices=["1.0kW", "1.5kW", "3.0kW"],
    )
    parser.add_argument("--max-retries", type=int, default=20)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    args.output_dir.mkdir(parents=True, exist_ok=True)
    selected = {f"{motor}.zip" for motor in args.motors}
    records = [record for record in fetch_manifest() if record["filename"] in selected]
    results = [
        download(record, args.output_dir, max_retries=args.max_retries)
        for record in records
    ]
    manifest_path = args.output_dir / "download_manifest.json"
    manifest_path.write_text(json.dumps(results, indent=2), encoding="utf-8")
    print(f"wrote {manifest_path.resolve()}")


if __name__ == "__main__":
    main()
