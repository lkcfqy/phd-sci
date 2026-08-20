"""Download and provenance-track the public Electric Motor Temperature dataset."""

from __future__ import annotations

import hashlib
import json
import shutil
from datetime import UTC, datetime
from pathlib import Path

import kagglehub

DATASET_HANDLE = "wkirgsn/electric-motor-temperature"
EXPECTED_LICENSE = "CC BY-SA 4.0"


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def main() -> None:
    cache_dir = Path(kagglehub.dataset_download(DATASET_HANDLE))
    destination = Path("data/raw/electric_motor_temperature")
    destination.mkdir(parents=True, exist_ok=True)

    copied: list[dict[str, str | int]] = []
    for source in sorted(cache_dir.rglob("*")):
        if not source.is_file():
            continue
        target = destination / source.name
        shutil.copy2(source, target)
        copied.append(
            {
                "file": target.name,
                "bytes": target.stat().st_size,
                "sha256": sha256(target),
            }
        )

    provenance = {
        "dataset_handle": DATASET_HANDLE,
        "source_url": f"https://www.kaggle.com/datasets/{DATASET_HANDLE}",
        "license": EXPECTED_LICENSE,
        "downloaded_utc": datetime.now(UTC).isoformat(),
        "kaggle_cache": str(cache_dir),
        "files": copied,
    }
    (destination / "provenance.json").write_text(
        json.dumps(provenance, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    print(f"Copied {len(copied)} files to {destination.resolve()}")


if __name__ == "__main__":
    main()
