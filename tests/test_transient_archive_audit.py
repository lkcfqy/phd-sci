from __future__ import annotations

import io
import zipfile
from pathlib import Path

import numpy as np
import pytest
from scipy.io import savemat

from scripts.audit_transient_pmsm_archive import audit_archive


def synthetic_mat_bytes() -> bytes:
    stream = io.BytesIO()
    savemat(
        stream,
        {
            "ialbt_meas": np.zeros((100, 2), dtype=np.float32),
            "if_meas": np.zeros((100, 1), dtype=np.float32),
        },
    )
    return stream.getvalue()


def test_archive_audit_inventories_mat_metadata_without_signal_loading(
    tmp_path: Path,
) -> None:
    path = tmp_path / "synthetic.zip"
    with zipfile.ZipFile(path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("README.txt", "synthetic documentation")
        archive.writestr("motor/record.mat", synthetic_mat_bytes())
    members, variables, summary, documentation = audit_archive(
        path, verify_official=False
    )
    assert set(members["kind"]) == {"txt", "mat"}
    assert set(variables["variable"]) == {"ialbt_meas", "if_meas"}
    assert set(variables["shape"]) == {"100x1", "100x2"}
    assert summary["inventory"]["mat_records"] == 1
    assert summary["inventory"]["signal_values_loaded"] is False
    assert summary["inventory"]["loadmat_called"] is False
    assert "synthetic documentation" in documentation


def test_archive_audit_rejects_unsafe_member_path(tmp_path: Path) -> None:
    path = tmp_path / "unsafe.zip"
    with zipfile.ZipFile(path, "w") as archive:
        archive.writestr("../record.mat", synthetic_mat_bytes())
    with pytest.raises(ValueError, match="Unsafe ZIP member"):
        audit_archive(path, verify_official=False)


def test_official_verification_rejects_wrong_byte_count(tmp_path: Path) -> None:
    path = tmp_path / "OpenData.zip"
    with zipfile.ZipFile(path, "w") as archive:
        archive.writestr("record.mat", synthetic_mat_bytes())
    with pytest.raises(RuntimeError, match="byte-count mismatch"):
        audit_archive(path)
