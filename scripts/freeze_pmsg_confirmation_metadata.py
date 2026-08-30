"""Freeze the independent PMSG filename/tree inventory without opening MAT signals."""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
from datetime import UTC, datetime
from pathlib import Path

import pandas as pd

from pmsm_sci.faults.pmsg_confirmation import parse_pmsg_filename

DATASET_PREFIX = "PMSG-3phase-Dataset"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--repository",
        type=Path,
        default=Path("tmp/pmsg3_metadata_repo"),
    )
    parser.add_argument("--tag", default="v1.1.0")
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("results/paper3_confirmation_preregistration"),
    )
    return parser.parse_args()


def git(repository: Path, *arguments: str) -> str:
    result = subprocess.run(
        ["git", "-C", str(repository), *arguments],
        check=True,
        capture_output=True,
        text=True,
        encoding="utf-8",
    )
    return result.stdout.strip()


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        while chunk := stream.read(1024 * 1024):
            digest.update(chunk)
    return digest.hexdigest()


def parse_tree_line(line: str) -> tuple[str, str, str]:
    metadata, path = line.split("\t", maxsplit=1)
    mode, object_type, object_id = metadata.split()
    if mode != "100644" or object_type != "blob":
        raise ValueError(f"Unexpected dataset tree entry: {line}")
    return object_id, path, Path(path).name


def main() -> None:
    args = parse_args()
    if not (args.repository / ".git").is_dir():
        raise FileNotFoundError(f"Metadata repository not found: {args.repository}")
    commit = git(args.repository, "rev-parse", f"{args.tag}^{{commit}}")
    tree = git(args.repository, "rev-parse", f"{args.tag}^{{tree}}")
    raw_entries = git(
        args.repository,
        "ls-tree",
        "-r",
        args.tag,
        "--",
        DATASET_PREFIX,
    ).splitlines()
    rows: list[dict[str, object]] = []
    non_mat: list[str] = []
    for line in raw_entries:
        object_id, repository_path, filename = parse_tree_line(line)
        if not filename.endswith(".mat"):
            non_mat.append(repository_path)
            continue
        label = parse_pmsg_filename(filename)
        rows.append(
            {
                "repository_path": repository_path,
                "filename": filename,
                "git_blob_oid_sha1": object_id,
                "is_healthy": label.is_healthy,
                "speed_rpm": label.speed_rpm,
                "torque_setting_code": label.torque_setting_code,
                "fault_family": label.fault_family,
                "terminal_a": label.terminal_a,
                "terminal_b": label.terminal_b,
                "resistance_code": label.resistance_code,
                "fault_span_percent": label.fault_span_percent,
            }
        )
    inventory = pd.DataFrame(rows)
    if len(inventory) != 225:
        raise AssertionError(f"Expected 225 MAT entries, found {len(inventory)}")
    if int(inventory["is_healthy"].sum()) != 9:
        raise AssertionError("Expected nine standalone healthy files")
    family_counts = inventory.loc[~inventory["is_healthy"], "fault_family"].value_counts()
    if family_counts.to_dict() != {"turns": 108, "windings": 108}:
        raise AssertionError(f"Unexpected fault-family counts: {family_counts.to_dict()}")
    condition_counts = inventory.groupby(
        ["speed_rpm", "torque_setting_code", "is_healthy"], observed=True
    ).size()
    healthy_condition_counts = condition_counts[condition_counts.index.get_level_values(2)]
    fault_condition_counts = condition_counts[~condition_counts.index.get_level_values(2)]
    if not healthy_condition_counts.eq(1).all() or not fault_condition_counts.eq(24).all():
        raise AssertionError("Expected one healthy and 24 fault cases per operating condition")
    fault_cases = inventory.loc[~inventory["is_healthy"]].groupby(
        ["fault_family", "terminal_a", "terminal_b", "resistance_code"],
        observed=True,
    ).size()
    if len(fault_cases) != 24 or not fault_cases.eq(9).all():
        raise AssertionError("Expected 24 fault cases repeated on all nine conditions")

    args.output_dir.mkdir(parents=True, exist_ok=True)
    inventory_path = args.output_dir / "metadata_inventory.csv"
    inventory.to_csv(inventory_path, index=False)
    protocol_path = Path("docs/paper3_confirmation_protocol.md")
    selected_path = Path("results/paper3_development/selected_method.json")
    development_protocol_path = Path("results/paper3_development/protocol.json")
    freeze = {
        "created_utc": datetime.now(UTC).isoformat(),
        "dataset_article_doi": "10.1016/j.dib.2025.112040",
        "dataset_doi": "10.5281/zenodo.15741561",
        "repository_url": "https://github.com/InnovaPower/MitDev-Eletrica",
        "repository_tag": args.tag,
        "repository_commit": commit,
        "repository_tree": tree,
        "dataset_prefix": DATASET_PREFIX,
        "tree_entries": len(raw_entries),
        "mat_entries": len(inventory),
        "healthy_mat_entries": int(inventory["is_healthy"].sum()),
        "fault_mat_entries": int((~inventory["is_healthy"]).sum()),
        "fault_family_counts": family_counts.to_dict(),
        "fault_cases": len(fault_cases),
        "operating_conditions": 9,
        "non_mat_entries": non_mat,
        "inventory_sha256": sha256(inventory_path),
        "confirmation_protocol": str(protocol_path.resolve()),
        "confirmation_protocol_sha256": sha256(protocol_path),
        "selected_method": str(selected_path.resolve()),
        "selected_method_sha256": sha256(selected_path),
        "development_protocol": str(development_protocol_path.resolve()),
        "development_protocol_sha256": sha256(development_protocol_path),
        "reveal_state": {
            "working_tree_mat_files_present": len(
                list(args.repository.glob(f"{DATASET_PREFIX}/*.mat"))
            ),
            "signal_arrays_deserialized_or_plotted": False,
            "note": (
                "A prior git size query inadvertently fetched some MAT blob objects into "
                "the object store, but no MAT signal was checked out, deserialized, plotted, "
                "or summarized before this freeze."
            ),
        },
    }
    freeze_path = args.output_dir / "metadata_freeze.json"
    freeze_path.write_text(json.dumps(freeze, indent=2), encoding="utf-8")
    print(
        f"froze {len(inventory)} MAT paths at {args.tag}/{commit[:12]} without opening signals"
    )
    print(f"wrote {inventory_path.resolve()}")
    print(f"wrote {freeze_path.resolve()}")


if __name__ == "__main__":
    main()
