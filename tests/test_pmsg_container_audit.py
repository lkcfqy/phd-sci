from __future__ import annotations

import pytest

from scripts.audit_pmsg_confirmation_container import audit_schema


def test_container_schema_audit_accepts_only_aligned_required_vectors() -> None:
    variables = [
        ("t", (60_001, 1), "double"),
        ("Ia", (60_001, 1), "double"),
        ("Ib", (60_001, 1), "double"),
        ("Ic", (60_001, 1), "double"),
        ("Ifault", (60_001, 1), "double"),
    ]
    samples, by_name = audit_schema(variables)
    assert samples == 60_001
    assert {"t", "Ia", "Ib", "Ic"}.issubset(by_name)

    malformed = list(variables)
    malformed[2] = ("Ib", (60_000, 1), "double")
    with pytest.raises(ValueError, match="shapes differ"):
        audit_schema(malformed)
