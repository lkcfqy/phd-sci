"""Create and verify the anonymous, hash-audited Paper 3 reproducibility bundle."""

from __future__ import annotations

import argparse
import hashlib
import json
import zipfile
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
PAPER_DIR = ROOT / "papers/paper3_calibration_transport"
OUT_DIR = PAPER_DIR / "submission"
ZIP_OUT = OUT_DIR / "Paper3_Reproducibility_Bundle.zip"
MANIFEST_OUT = OUT_DIR / "Paper3_Reproducibility_Bundle_manifest.json"
BUNDLE_ROOT = "paper3_reproducibility"
TEXT_SUFFIXES = {
    ".cfg",
    ".csv",
    ".ini",
    ".json",
    ".md",
    ".py",
    ".toml",
    ".txt",
    ".yaml",
    ".yml",
}
_DRIVE = b"c:"
_BACKSLASH = b"\\"
_FORWARD_SLASH = b"/"
FORBIDDEN_BYTES = (
    _DRIVE + _BACKSLASH + b"users",
    _DRIVE + 2 * _BACKSLASH + b"users",
    _DRIVE + _FORWARD_SLASH + b"users",
    _DRIVE + _BACKSLASH + b"lkc" + _BACKSLASH + b"phd sci",
    _DRIVE + 2 * _BACKSLASH + b"lkc" + 2 * _BACKSLASH + b"phd sci",
    _DRIVE + _FORWARD_SLASH + b"lkc/phd sci",
)


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _explicit_files() -> list[tuple[str, Path]]:
    return [
        ("environment", ROOT / "pyproject.toml"),
        ("bibliography", ROOT / "references/key_papers.bib"),
        ("paper", PAPER_DIR / "manuscript.md"),
        ("paper", PAPER_DIR / "supplementary_material.md"),
        ("paper", PAPER_DIR / "evidence_validation.json"),
        ("paper", PAPER_DIR / "README_REPRODUCE.md"),
        ("paper", PAPER_DIR / "SUBMISSION_CHECKLIST.md"),
        ("paper", PAPER_DIR / "outline.md"),
        ("submission", OUT_DIR / "Paper3_Manuscript_Anonymous.docx"),
        ("submission", OUT_DIR / "Paper3_Manuscript_Anonymous.pdf"),
        ("submission", OUT_DIR / "Paper3_Supplementary_Material.pdf"),
        ("submission", OUT_DIR / "build_metadata.json"),
    ]


def bundle_sources() -> list[tuple[str, Path]]:
    documentation_names = (
        "paper3_confirmation_protocol.md",
        "paper3_development_protocol.md",
        "paper3_literature_gap.md",
        "paper3_post_reveal_conditioned_anchor_protocol.md",
        "paper3_post_reveal_matched_calibration_protocol.md",
        "paper3_post_reveal_session_anchor_protocol.md",
        "paper3_reveal_log.md",
    )
    documentation = [("documentation", ROOT / "docs" / name) for name in documentation_names]
    scripts = [
        ("script", path)
        for path in sorted((ROOT / "scripts").glob("*.py"))
        if (
            "paper3" in path.name
            or "pmsg" in path.name
            or path.name
            in {
                "audit_external_pmsm_health.py",
                "audit_reference_metadata.py",
                "build_external_pmsm_health_features.py",
                "download_external_pmsm_validation.py",
            }
        )
    ]
    tests = [
        ("test", path)
        for path in sorted((ROOT / "tests").glob("*.py"))
        if (
            "paper3" in path.name
            or "pmsg" in path.name
            or "session_anchor" in path.name
            or path.name
            in {
                "test_conditional.py",
                "test_external_health_audit.py",
                "test_external_pmsm.py",
                "test_operating_context.py",
            }
        )
    ]
    modules = [
        ("module", path)
        for path in sorted((ROOT / "src/pmsm_sci/faults").glob("*.py"))
    ]
    figures = [
        ("figure", path) for path in sorted((PAPER_DIR / "figures").glob("paper3_*.*"))
    ]
    results: list[tuple[str, Path]] = []
    for directory in sorted((ROOT / "results").glob("paper3_*")):
        if directory.is_dir():
            results.extend(
                ("result", path)
                for path in sorted(item for item in directory.rglob("*") if item.is_file())
            )
    processed_metadata = [
        ("processed_metadata", path)
        for path in (
            ROOT / "data/processed/paper3_development_features.csv.metadata.json",
            ROOT / "data/processed/paper3_pmsg_confirmation_features.csv.metadata.json",
        )
    ]
    sources = _explicit_files() + documentation + scripts + tests + modules + figures + results + processed_metadata
    deduplicated: dict[Path, str] = {}
    for category, path in sources:
        deduplicated.setdefault(path.resolve(), category)
    ordered = sorted(
        ((category, path) for path, category in deduplicated.items()),
        key=lambda item: str(item[1].relative_to(ROOT)).replace("\\", "/"),
    )
    missing = [str(path) for _, path in ordered if not path.is_file()]
    if missing:
        raise FileNotFoundError(f"missing bundle inputs: {missing}")
    forbidden_roots = ("data/raw/", "tmp/")
    for _, path in ordered:
        relative = str(path.relative_to(ROOT)).replace("\\", "/").lower()
        if relative.startswith(forbidden_roots):
            raise AssertionError(f"raw or temporary input must not enter bundle: {relative}")
        if relative.endswith("features.csv.gz"):
            raise AssertionError(f"processed signal-feature table must not enter bundle: {relative}")
    return ordered


def archive_payload(path: Path) -> bytes:
    data = path.read_bytes()
    if path.suffix.lower() not in TEXT_SUFFIXES:
        return data
    text = data.decode("utf-8")
    root_windows = str(ROOT)
    replacements = {
        root_windows.replace("\\", "\\\\"),
        root_windows,
        root_windows.replace("\\", "/"),
    }
    for local_root in sorted(replacements, key=len, reverse=True):
        text = text.replace(local_root, ".")
    payload = text.encode("utf-8")
    lowered = payload.lower()
    if any(token in lowered for token in FORBIDDEN_BYTES):
        raise AssertionError(f"identity-bearing local path remains in {path}")
    return payload


def source_manifest() -> tuple[dict[str, Any], dict[str, bytes]]:
    files: list[dict[str, Any]] = []
    payloads: dict[str, bytes] = {}
    for category, path in bundle_sources():
        relative = str(path.relative_to(ROOT)).replace("\\", "/")
        payload = archive_payload(path)
        payloads[relative] = payload
        files.append(
            {
                "path": relative,
                "category": category,
                "bytes": len(payload),
                "sha256": sha256_bytes(payload),
            }
        )
    categories: dict[str, int] = {}
    for item in files:
        categories[item["category"]] = categories.get(item["category"], 0) + 1
    manifest = {
        "bundle": "Paper 3 reproducibility companion",
        "development_data_doi": "10.5281/zenodo.13889418",
        "confirmation_data_dois": [
            "10.1016/j.dib.2025.112040",
            "10.5281/zenodo.15741561",
        ],
        "raw_signal_data_included": False,
        "processed_signal_features_included": False,
        "file_count": len(files),
        "categories": dict(sorted(categories.items())),
        "files": files,
    }
    return manifest, payloads


def manifest_bytes(manifest: dict[str, Any]) -> bytes:
    return (json.dumps(manifest, indent=2, sort_keys=True) + "\n").encode("utf-8")


def add_bytes(archive: zipfile.ZipFile, name: str, data: bytes) -> None:
    info = zipfile.ZipInfo(name, date_time=(2026, 8, 21, 0, 0, 0))
    info.compress_type = zipfile.ZIP_DEFLATED
    info.external_attr = 0o644 << 16
    archive.writestr(info, data, compress_type=zipfile.ZIP_DEFLATED, compresslevel=9)


def build_bundle() -> dict[str, Any]:
    manifest, payloads = source_manifest()
    embedded = manifest_bytes(manifest)
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(ZIP_OUT, mode="w") as archive:
        for item in manifest["files"]:
            relative = str(item["path"])
            add_bytes(archive, f"{BUNDLE_ROOT}/{relative}", payloads[relative])
        add_bytes(archive, f"{BUNDLE_ROOT}/MANIFEST.json", embedded)
    result = {
        "status": "built",
        "path": str(ZIP_OUT.relative_to(ROOT)).replace("\\", "/"),
        "sha256": sha256(ZIP_OUT),
        "bytes": ZIP_OUT.stat().st_size,
        "source_manifest_sha256": sha256_bytes(embedded),
        "source_file_count": manifest["file_count"],
        "categories": manifest["categories"],
        "raw_signal_data_included": False,
        "processed_signal_features_included": False,
    }
    MANIFEST_OUT.write_text(
        json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    return result


def audit_bundle() -> dict[str, Any]:
    if not ZIP_OUT.is_file() or not MANIFEST_OUT.is_file():
        raise FileNotFoundError("bundle or external manifest is missing")
    external = json.loads(MANIFEST_OUT.read_text(encoding="utf-8"))
    if external["sha256"] != sha256(ZIP_OUT):
        raise AssertionError("bundle hash does not match external manifest")
    with zipfile.ZipFile(ZIP_OUT) as archive:
        names = archive.namelist()
        manifest_name = f"{BUNDLE_ROOT}/MANIFEST.json"
        if names.count(manifest_name) != 1:
            raise AssertionError("bundle must contain exactly one embedded manifest")
        embedded = archive.read(manifest_name)
        if sha256_bytes(embedded) != external["source_manifest_sha256"]:
            raise AssertionError("embedded manifest hash mismatch")
        manifest = json.loads(embedded)
        expected_names = {manifest_name}
        for item in manifest["files"]:
            name = f"{BUNDLE_ROOT}/{item['path']}"
            expected_names.add(name)
            payload = archive.read(name)
            if len(payload) != item["bytes"] or sha256_bytes(payload) != item["sha256"]:
                raise AssertionError(f"bundle member failed integrity audit: {name}")
            lowered = payload.lower()
            if any(token in lowered for token in FORBIDDEN_BYTES):
                raise AssertionError(f"local identity-bearing path in bundle member: {name}")
        if set(names) != expected_names:
            raise AssertionError("bundle inventory differs from embedded manifest")
        normalized = [name.lower().replace("\\", "/") for name in names]
        if any("/data/raw/" in name or "/tmp/" in name for name in normalized):
            raise AssertionError("bundle unexpectedly contains raw or temporary data")
        if any(name.endswith("features.csv.gz") for name in normalized):
            raise AssertionError("bundle unexpectedly contains processed signal features")
        if manifest["file_count"] != external["source_file_count"]:
            raise AssertionError("bundle file count mismatch")
    return {
        "status": "pass",
        "path": str(ZIP_OUT.relative_to(ROOT)).replace("\\", "/"),
        "sha256": external["sha256"],
        "source_file_count": external["source_file_count"],
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    result = audit_bundle() if args.check else build_bundle()
    print(json.dumps(result, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
