"""Phase 25 Fix 4: document-level controlled-source evidence contracts."""

import csv
from pathlib import Path

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


def test_export_separates_source_family_signoff_from_actual_document_hashes(tmp_path):
    output = tmp_path / "pack"
    result = export_pack(output)

    families = _read(output / "01_source_evidence.csv")
    documents = _read(output / "01a_source_documents.csv")

    assert result["sources"] == 5
    assert result["source_documents_seeded"] == 2
    assert {row["source_id"] for row in documents} == {
        "SRC-R76-1-2006-E",
        "SRC-R76-2-2007-E",
    }
    assert "sha256" not in families[0]
    assert "acquired_at" not in families[0]
    assert all(row["amendment_set_complete"] == "false" for row in families)


def test_validator_requires_document_rows_for_each_logical_source_family(tmp_path):
    output = tmp_path / "pack"
    export_pack(output)

    result = validate_pack(output)

    for source_id in (
        "SRC-INDIA-APPROVAL-MODELS-2011",
        "SRC-INDIA-LM-GENERAL",
        "SRC-INDIA-GATC",
    ):
        assert f"SOURCE_DOCUMENTS_REQUIRED:SOURCE:{source_id}" in result["blockers"]


def test_validator_requires_explicit_amendment_set_completeness_attestation(tmp_path):
    output = tmp_path / "pack"
    export_pack(output)

    result = validate_pack(output)

    assert (
        "AMENDMENT_SET_COMPLETENESS_REQUIRED:SOURCE:SRC-INDIA-LM-GENERAL"
        in result["blockers"]
    )


def test_validator_rejects_duplicate_document_identity_within_source_family(tmp_path):
    output = tmp_path / "pack"
    export_pack(output)
    path = output / "01a_source_documents.csv"
    rows = _read(path)
    duplicate = dict(rows[0])
    rows.append(duplicate)
    _write(path, rows)

    result = validate_pack(output)

    assert (
        "DUPLICATE_SOURCE_DOCUMENT:SOURCE_DOCUMENT:SRC-R76-1-2006-E:principal"
        in result["blockers"]
    )


def test_validator_rejects_invalid_document_digest(tmp_path):
    output = tmp_path / "pack"
    export_pack(output)
    path = output / "01a_source_documents.csv"
    rows = _read(path)
    rows[0]["sha256"] = "not-a-sha"
    _write(path, rows)

    result = validate_pack(output)

    assert (
        "INVALID_SHA256:SOURCE_DOCUMENT:SRC-R76-1-2006-E:principal:sha256"
        in result["blockers"]
    )


def test_source_family_candidate_columns_cannot_be_silently_rewritten(tmp_path):
    output = tmp_path / "pack"
    export_pack(output)
    path = output / "01_source_evidence.csv"
    rows = _read(path)
    rows[0]["edition"] = "tampered"
    _write(path, rows)

    result = validate_pack(output)

    assert (
        f"SOURCE_CANDIDATE_MISMATCH:SOURCE:{rows[0]['source_id']}:edition"
        in result["blockers"]
    )
