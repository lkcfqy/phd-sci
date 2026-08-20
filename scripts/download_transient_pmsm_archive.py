"""Resumably download and verify the official transient PMSM archive."""

from __future__ import annotations

import argparse
import concurrent.futures
import hashlib
import shutil
import urllib.request
from pathlib import Path

OFFICIAL_URL = "https://zenodo.org/api/records/15631383/files/OpenData.zip/content"
OFFICIAL_BYTES = 91_533_036
OFFICIAL_MD5 = "b9b03b6e31a33ea08f49cd1cbeed12b2"
CHUNK_BYTES = 1024 * 1024


def range_plan(start: int, stop: int, workers: int) -> list[tuple[int, int]]:
    """Partition inclusive byte offsets into contiguous, non-empty ranges."""

    if start < 0 or stop < start or workers < 1:
        raise ValueError("invalid byte range or worker count")
    total = stop - start + 1
    workers = min(workers, total)
    base, remainder = divmod(total, workers)
    ranges: list[tuple[int, int]] = []
    cursor = start
    for index in range(workers):
        length = base + (1 if index < remainder else 0)
        ranges.append((cursor, cursor + length - 1))
        cursor += length
    if cursor != stop + 1:
        raise AssertionError("range partition does not cover the requested bytes")
    return ranges


def file_md5(path: Path) -> str:
    digest = hashlib.md5(usedforsecurity=False)
    with path.open("rb") as stream:
        while chunk := stream.read(8 * CHUNK_BYTES):
            digest.update(chunk)
    return digest.hexdigest()


def _download_range(url: str, target: Path, start: int, stop: int) -> Path:
    expected = stop - start + 1
    if target.is_file() and target.stat().st_size == expected:
        return target
    request = urllib.request.Request(
        url,
        headers={
            "Range": f"bytes={start}-{stop}",
            "User-Agent": "pmsm-sci-reproducibility-audit/1.0",
        },
    )
    with urllib.request.urlopen(request, timeout=120) as response:
        status = getattr(response, "status", None)
        content_range = response.headers.get("Content-Range", "")
        if status != 206 or not content_range.startswith(f"bytes {start}-{stop}/"):
            raise RuntimeError(
                f"Server did not honor range {start}-{stop}: "
                f"status={status}, Content-Range={content_range!r}"
            )
        with target.open("wb") as stream:
            shutil.copyfileobj(response, stream, length=CHUNK_BYTES)
    if target.stat().st_size != expected:
        raise RuntimeError(
            f"Range {start}-{stop} has {target.stat().st_size} bytes, expected {expected}"
        )
    print(f"downloaded bytes {start}-{stop}")
    return target


def complete_download(
    target: Path,
    *,
    url: str = OFFICIAL_URL,
    expected_bytes: int = OFFICIAL_BYTES,
    expected_md5: str = OFFICIAL_MD5,
    workers: int = 4,
) -> None:
    """Resume a partial file with parallel HTTP ranges and verify the result."""

    target.parent.mkdir(parents=True, exist_ok=True)
    current = target.stat().st_size if target.exists() else 0
    if current > expected_bytes:
        raise RuntimeError("partial file is larger than the official archive")
    if current < expected_bytes:
        ranges = range_plan(current, expected_bytes - 1, workers)
        parts = [
            target.with_name(f"{target.name}.part-{start}-{stop}")
            for start, stop in ranges
        ]
        with concurrent.futures.ThreadPoolExecutor(max_workers=len(ranges)) as pool:
            futures = [
                pool.submit(_download_range, url, part, start, stop)
                for part, (start, stop) in zip(parts, ranges, strict=True)
            ]
            for future in concurrent.futures.as_completed(futures):
                future.result()
        if target.exists() and target.stat().st_size != current:
            raise RuntimeError("partial archive changed while ranges were downloading")
        with target.open("ab") as destination:
            for part in parts:
                with part.open("rb") as source:
                    shutil.copyfileobj(source, destination, length=CHUNK_BYTES)
        if target.stat().st_size != expected_bytes:
            raise RuntimeError("assembled archive has the wrong byte count")
        for part in parts:
            part.unlink()
    digest = file_md5(target)
    if digest != expected_md5:
        raise RuntimeError(f"Official MD5 mismatch: {digest}")
    print(f"verified {target.resolve()} ({expected_bytes} bytes, MD5 {digest})")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--target",
        type=Path,
        default=Path("data/raw/transient_cross_capacity/OpenData.zip"),
    )
    parser.add_argument("--workers", type=int, default=4)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    complete_download(args.target, workers=args.workers)


if __name__ == "__main__":
    main()
