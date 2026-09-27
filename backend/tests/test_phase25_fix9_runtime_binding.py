"""Phase 25 Fix 9: exact runtime binding and Stage 7 authority contracts."""

import csv
import json
from dataclasses import replace
from pathlib import Path

from app.compliance.runtime_binding import (
    RuntimeBindingError,
    runtime_binding_catalog_json,
    runtime_binding_hash,
    runtime_binding_options,
)
from app.compliance.suite import implemented_registry
from scripts.export_phase25_external_review import export_pack
from scripts.validate_phase25_external_review import validate_pack


def _read(path: Path):
    with path.open(encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def _write(path: Path, rows):
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def test_runtime_binding_covers_registered_v1_and_v2_pairs():
    registration = implemented_registry().resolve("WEIGHING_PERFORMANCE")
    options = runtime_binding_options(registration)
    pairs = {
        (
            item["procedure_schema_version"],
            item["observation_schema_version"],
        )
        for item in options
    }
    assert ("v1", "v1") in pairs
    assert ("v2", "v2") in pairs
    assert ("v1", "v2") not in pairs
    assert ("v2", "v1") not in pairs
    assert all(len(item["runtime_binding_sha256"]) == 64 for item in options)


def test_runtime_binding_changes_when_implementation_identity_changes():
    registration = implemented_registry().resolve("WEIGHING_PERFORMANCE")
    original = runtime_binding_hash(registration, "v1", "v1")
    changed = runtime_binding_hash(
        replace(
            registration,
            implementation_version=registration.implementation_version + "-changed",
        ),
        "v1",
        "v1",
    )
    assert original != changed


def test_runtime_binding_rejects_incompatible_pair():
    registration = implemented_registry().resolve("WEIGHING_PERFORMANCE")
    try:
        runtime_binding_hash(registration, "v2", "v1")
    except RuntimeBindingError:
        pass
    else:
        raise AssertionError("Expected incompatible runtime pair to fail closed")


def test_export_includes_immutable_runtime_binding_catalog(tmp_path):
    output = tmp_path / "pack"
    export_pack(output)
    rows = _read(output / "06_runtime_schema_review.csv")
    row = next(item for item in rows if item["test_code"] == "WEIGHING_PERFORMANCE")
    registration = implemented_registry().resolve("WEIGHING_PERFORMANCE")

    assert row["implementation_version"] == registration.implementation_version
    assert row["available_runtime_bindings_json"] == runtime_binding_catalog_json(
        registration
    )
    assert row["selected_runtime_binding_sha256"] == ""
    assert row["reviewer_role"] == ""
    assert row["reviewer_organization"] == ""


def test_validator_rejects_tampered_selected_runtime_binding(tmp_path):
    output = tmp_path / "pack"
    export_pack(output)
    path = output / "06_runtime_schema_review.csv"
    rows = _read(path)
    row = next(item for item in rows if item["test_code"] == "WEIGHING_PERFORMANCE")
    bindings = json.loads(row["available_runtime_bindings_json"])
    selected = next(
        item
        for item in bindings
        if item["procedure_schema_version"] == "v2"
        and item["observation_schema_version"] == "v2"
    )
    row.update(
        selected_procedure_schema_version="v2",
        selected_observation_schema_version="v2",
        selected_runtime_binding_sha256="f" * 64,
        evidence_reference="SYNTHETIC FIX9",
        review_status="VERIFIED",
        reviewed_by="SYNTHETIC REVIEWER",
        reviewer_role="SYNTHETIC ROLE",
        reviewer_organization="SYNTHETIC ORG",
        reviewed_at="2026-09-27T15:30:00+00:00",
        independent_of_implementation="true",
        review_notes="SYNTHETIC",
    )
    assert selected["runtime_binding_sha256"] != "f" * 64
    _write(path, rows)

    result = validate_pack(output)
    assert (
        "RUNTIME_BINDING_MISMATCH:RUNTIME:WEIGHING_PERFORMANCE"
        in result["blockers"]
    )
