"""Audit the official 200 W/20 kW PMSM archive without loading signal values."""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import tempfile
import zipfile
from pathlib import Path, PurePosixPath
from typing import Any

import pandas as pd
from matio import whosmat

ZENODO_RECORD = "15631383"
ZENODO_DOI = "10.5281/zenodo.15631383"
OFFICIAL_FILENAME = "OpenData.zip"
OFFICIAL_BYTES = 91_533_036
OFFICIAL_MD5 = "b9b03b6e31a33ea08f49cd1cbeed12b2"
EXPECTED_MAT_RECORDS = 21
README_LIMIT_BYTES = 2 * 1024 * 1024


def file_digest(path: Path, algorithm: str) -> str:
    """Hash a file in bounded chunks."""

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


def _safe_member_name(name: str) -> str:
    normalized = name.replace("\\", "/")
    path = PurePosixPath(normalized)
    if path.is_absolute() or ".." in path.parts or not path.parts:
        raise ValueError(f"Unsafe ZIP member path: {name}")
    return normalized


def _readme_text(archive: zipfile.ZipFile, info: zipfile.ZipInfo) -> str:
    if info.file_size > README_LIMIT_BYTES:
        raise ValueError(f"Documentation member is unexpectedly large: {info.filename}")
    raw = archive.read(info)
    for encoding in ("utf-8-sig", "utf-16", "cp1252"):
        try:
            return raw.decode(encoding)
        except UnicodeDecodeError:
            continue
    return raw.decode("utf-8", errors="replace")


def audit_archive(
    archive_path: Path, *, verify_official: bool = True
) -> tuple[pd.DataFrame, pd.DataFrame, dict[str, Any], str]:
    """Inventory ZIP/MAT metadata while never calling ``loadmat``."""

    if not archive_path.is_file():
        raise FileNotFoundError(archive_path)
    archive_bytes = archive_path.stat().st_size
    archive_md5 = file_digest(archive_path, "md5")
    archive_sha256 = file_digest(archive_path, "sha256")
    if verify_official:
        if archive_path.name != OFFICIAL_FILENAME:
            raise ValueError(f"Expected archive name {OFFICIAL_FILENAME}")
        if archive_bytes != OFFICIAL_BYTES:
            raise RuntimeError(
                f"Official byte-count mismatch: {archive_bytes} != {OFFICIAL_BYTES}"
            )
        if archive_md5 != OFFICIAL_MD5:
            raise RuntimeError(f"Official MD5 mismatch: {archive_md5}")

    member_rows: list[dict[str, object]] = []
    variable_rows: list[dict[str, object]] = []
    documentation: list[str] = []
    with zipfile.ZipFile(archive_path) as archive, tempfile.TemporaryDirectory() as temp:
        bad_member = archive.testzip()
        if bad_member is not None:
            raise RuntimeError(f"ZIP CRC failure: {bad_member}")
        infos = archive.infolist()
        normalized_names = [_safe_member_name(info.filename) for info in infos]
        if len(normalized_names) != len(set(normalized_names)):
            raise RuntimeError("ZIP contains duplicate normalized member names")
        for info, normalized in zip(infos, normalized_names, strict=True):
            if info.flag_bits & 0x1:
                raise RuntimeError(f"Encrypted ZIP member is unsupported: {normalized}")
            suffix = PurePosixPath(normalized).suffix.lower()
            kind = "directory" if info.is_dir() else suffix.removeprefix(".") or "file"
            member_rows.append(
                {
                    "member": normalized,
                    "kind": kind,
                    "uncompressed_bytes": info.file_size,
                    "compressed_bytes": info.compress_size,
                    "zip_crc32": f"{info.CRC:08x}",
                }
            )
            lowered = normalized.lower()
            if not info.is_dir() and (
                "readme" in lowered or suffix in {".txt", ".md"}
            ):
                documentation.append(
                    f"===== {normalized} =====\n{_readme_text(archive, info).rstrip()}"
                )
            if suffix != ".mat" or info.is_dir():
                continue
            temporary_mat = Path(temp) / f"record_{len(variable_rows):02d}.mat"
            with archive.open(info) as source, temporary_mat.open("wb") as destination:
                shutil.copyfileobj(source, destination, length=1024 * 1024)
            try:
                inventory = whosmat(temporary_mat)
                inventory_error = ""
            except (NotImplementedError, OSError, TypeError, ValueError) as error:
                inventory = []
                inventory_error = f"{type(error).__name__}: {error}"
            if inventory_error:
                variable_rows.append(
                    {
                        "member": normalized,
                        "variable": "",
                        "shape": "",
                        "elements": 0,
                        "matlab_class": "",
                        "inventory_error": inventory_error,
                    }
                )
            else:
                for name, (shape, matlab_class) in inventory.items():
                    elements = 1
                    for dimension in shape:
                        elements *= dimension
                    variable_rows.append(
                        {
                            "member": normalized,
                            "variable": name,
                            "shape": "x".join(str(value) for value in shape),
                            "elements": elements,
                            "matlab_class": matlab_class,
                            "inventory_error": "",
                        }
                    )

    members = pd.DataFrame(member_rows).sort_values("member").reset_index(drop=True)
    variables = pd.DataFrame(variable_rows).sort_values(
        ["member", "variable"]
    ).reset_index(drop=True)
    mat_members = members.loc[members["kind"].eq("mat"), "member"]
    if verify_official and len(mat_members) != EXPECTED_MAT_RECORDS:
        raise RuntimeError(
            f"Expected {EXPECTED_MAT_RECORDS} MAT records, found {len(mat_members)}"
        )
    summary: dict[str, Any] = {
        "dataset": {
            "doi": ZENODO_DOI,
            "record": ZENODO_RECORD,
            "license": "CC BY 4.0",
        },
        "archive": {
            "path": str(archive_path.resolve()),
            "bytes": archive_bytes,
            "md5": archive_md5,
            "sha256": archive_sha256,
            "official_integrity_verified": verify_official,
        },
        "inventory": {
            "members": len(members),
            "mat_records": len(mat_members),
            "documentation_members": len(documentation),
            "mat_inventory_errors": int(
                variables["inventory_error"].astype(bool).sum()
            ),
            "signal_values_loaded": False,
            "loadmat_called": False,
        },
    }
    return members, variables, summary, "\n\n".join(documentation) + "\n"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--archive",
        type=Path,
        default=Path("data/raw/transient_cross_capacity/OpenData.zip"),
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("results/transient_archive_audit"),
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    members, variables, summary, documentation = audit_archive(args.archive)
    args.output_dir.mkdir(parents=True, exist_ok=True)
    members.to_csv(args.output_dir / "archive_members.csv", index=False)
    variables.to_csv(args.output_dir / "mat_variables.csv", index=False)
    (args.output_dir / "summary.json").write_text(
        json.dumps(summary, indent=2, sort_keys=True), encoding="utf-8"
    )
    (args.output_dir / "documentation.txt").write_text(
        documentation, encoding="utf-8"
    )
    print(
        f"audited {summary['inventory']['mat_records']} MAT records without "
        f"loading signal values; wrote {args.output_dir.resolve()}"
    )


if __name__ == "__main__":
    main()
