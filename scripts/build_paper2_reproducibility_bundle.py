"""Create and verify the self-auditing Paper 2 reproducibility bundle."""

from __future__ import annotations

import argparse
import hashlib
import json
import zipfile
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
PAPER_DIR = ROOT / "papers" / "paper2_torque_uq"
OUT_DIR = PAPER_DIR / "submission"
ZIP_OUT = OUT_DIR / "Paper2_Reproducibility_Bundle.zip"
MANIFEST_OUT = OUT_DIR / "Paper2_Reproducibility_Bundle_manifest.json"
BUNDLE_ROOT = "paper2_reproducibility"


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def bundle_sources() -> list[tuple[str, Path]]:
    explicit: list[tuple[str, Path]] = [
        ("environment", ROOT / "pyproject.toml"),
        ("project", ROOT / "README.md"),
        ("bibliography", ROOT / "references" / "key_papers.bib"),
        ("paper", PAPER_DIR / "manuscript.md"),
        ("paper", PAPER_DIR / "supplementary_material.md"),
        ("paper", PAPER_DIR / "README_REPRODUCE.md"),
        ("paper", PAPER_DIR / "SUBMISSION_CHECKLIST.md"),
        ("paper", PAPER_DIR / "outline.md"),
        ("submission", OUT_DIR / "Paper2_Manuscript_Anonymous.docx"),
        ("submission", OUT_DIR / "Paper2_Manuscript_Anonymous.pdf"),
        ("submission", OUT_DIR / "Paper2_Supplementary_Material.pdf"),
        ("submission", OUT_DIR / "build_metadata.json"),
        ("script", ROOT / "scripts" / "build_jeet_submission.py"),
    ]
    documentation = [
        ROOT / "docs" / name
        for name in [
            "paper2_additional_figure_contracts.md",
            "paper2_literature_gap.md",
            "paper2_protocol.md",
            "paper2_torque_data_quality.md",
            "paper2_weighted_conformal_diagnostic.md",
        ]
    ]
    scripts = sorted(
        path
        for path in (ROOT / "scripts").glob("*.py")
        if "torque" in path.name or "paper2" in path.name
    )
    tests = sorted(
        path
        for path in (ROOT / "tests").glob("*.py")
        if "torque" in path.name or "paper2" in path.name
    )
    modules = sorted((ROOT / "src" / "pmsm_sci" / "torque").glob("*.py"))
    figures = sorted((PAPER_DIR / "figures").glob("paper2_*.*"))
    result_files: list[Path] = []
    for directory in sorted((ROOT / "results").glob("paper2_*")):
        if directory.is_dir():
            result_files.extend(sorted(path for path in directory.rglob("*") if path.is_file()))
    sources = explicit.copy()
    sources.extend(("documentation", path) for path in documentation)
    sources.extend(("script", path) for path in scripts)
    sources.extend(("test", path) for path in tests)
    sources.extend(("module", path) for path in modules)
    sources.extend(("figure", path) for path in figures)
    sources.extend(("result", path) for path in result_files)

    deduplicated: dict[Path, str] = {}
    for category, path in sources:
        resolved = path.resolve()
        if resolved not in deduplicated:
            deduplicated[resolved] = category
    ordered = sorted(
        ((category, path) for path, category in deduplicated.items()),
        key=lambda item: str(item[1].relative_to(ROOT)).replace("\\", "/"),
    )
    missing = [str(path) for _, path in ordered if not path.is_file()]
    if missing:
        raise FileNotFoundError(f"missing bundle inputs: {missing}")
    if any("data/raw" in str(path.relative_to(ROOT)).replace("\\", "/") for _, path in ordered):
        raise AssertionError("raw data must not be included")
    return ordered


def source_manifest() -> dict[str, Any]:
    files: list[dict[str, Any]] = []
    for category, path in bundle_sources():
        relative = str(path.relative_to(ROOT)).replace("\\", "/")
        files.append(
            {
                "path": relative,
                "category": category,
                "bytes": path.stat().st_size,
                "sha256": sha256(path),
            }
        )
    categories: dict[str, int] = {}
    for item in files:
        categories[item["category"]] = categories.get(item["category"], 0) + 1
    return {
        "bundle": "Paper 2 reproducibility companion",
        "source_data_doi": "10.5281/zenodo.15688397",
        "raw_data_included": False,
        "file_count": len(files),
        "categories": dict(sorted(categories.items())),
        "files": files,
    }


def manifest_bytes(manifest: dict[str, Any]) -> bytes:
    return (json.dumps(manifest, indent=2, sort_keys=True) + "\n").encode("utf-8")


def add_bytes(archive: zipfile.ZipFile, name: str, data: bytes) -> None:
    info = zipfile.ZipInfo(name, date_time=(2026, 8, 21, 0, 0, 0))
    info.compress_type = zipfile.ZIP_DEFLATED
    info.external_attr = 0o644 << 16
    archive.writestr(info, data, compress_type=zipfile.ZIP_DEFLATED, compresslevel=9)


def build_bundle() -> dict[str, Any]:
    manifest = source_manifest()
    payload = manifest_bytes(manifest)
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(ZIP_OUT, mode="w") as archive:
        for item in manifest["files"]:
            source = ROOT / item["path"]
            add_bytes(archive, f"{BUNDLE_ROOT}/{item['path']}", source.read_bytes())
        add_bytes(archive, f"{BUNDLE_ROOT}/MANIFEST.json", payload)
    result = {
        "status": "built",
        "path": str(ZIP_OUT.relative_to(ROOT)),
        "sha256": sha256(ZIP_OUT),
        "bytes": ZIP_OUT.stat().st_size,
        "source_manifest_sha256": sha256_bytes(payload),
        "source_file_count": manifest["file_count"],
        "categories": manifest["categories"],
        "raw_data_included": False,
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
            raise AssertionError("bundle must contain exactly one manifest")
        manifest_payload = archive.read(manifest_name)
        if sha256_bytes(manifest_payload) != external["source_manifest_sha256"]:
            raise AssertionError("embedded manifest hash mismatch")
        manifest = json.loads(manifest_payload)
        expected_names = {manifest_name}
        for item in manifest["files"]:
            name = f"{BUNDLE_ROOT}/{item['path']}"
            expected_names.add(name)
            payload = archive.read(name)
            if len(payload) != item["bytes"] or sha256_bytes(payload) != item["sha256"]:
                raise AssertionError(f"bundle member failed integrity audit: {name}")
        if set(names) != expected_names:
            raise AssertionError("bundle member inventory differs from embedded manifest")
        if any("/data/raw/" in name.replace("\\", "/") for name in names):
            raise AssertionError("bundle unexpectedly contains raw data")
        if manifest["file_count"] != external["source_file_count"]:
            raise AssertionError("file count mismatch")
    return {
        "status": "pass",
        "path": str(ZIP_OUT.relative_to(ROOT)),
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
