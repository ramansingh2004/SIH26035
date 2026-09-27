"""Phase 25 Fix 3: version-aware external-review validator contracts."""

import csv
import json
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


def _runtime_row(output: Path, code: str):
    path = output / "06_runtime_schema_review.csv"
    rows = _read(path)
    return path, rows, next(row for row in rows if row["test_code"] == code)


def _complete_runtime_row(row, *, procedure="v2", observation="v2", independent="true"):
    row.update(
        selected_procedure_schema_version=procedure,
        selected_observation_schema_version=observation,
        evidence_reference="SYNTHETIC FIX3 REVIEW EVIDENCE",
        review_status="VERIFIED",
        reviewed_by="SYNTHETIC INDEPENDENT REVIEWER",
        reviewed_at="2026-09-27T15:30:00+00:00",
        independent_of_implementation=independent,
        review_notes="SYNTHETIC TEST FIXTURE ONLY",
    )


def test_export_reflects_fix1_weighing_v2_and_runtime_independence_column(tmp_path):
    output = tmp_path / "pack"
    export_pack(output)

    _, _, row = _runtime_row(output, "WEIGHING_PERFORMANCE")
    assert set(row["available_procedure_schema_versions"].split(";")) == {"v1", "v2"}
    assert set(row["available_observation_schema_versions"].split(";")) == {"v1", "v2"}
    assert row["independent_of_implementation"] == "false"


def test_validator_accepts_reviewed_registered_v2_without_version_label_prejudice(tmp_path):
    output = tmp_path / "pack"
    export_pack(output)
    path, rows, row = _runtime_row(output, "WEIGHING_PERFORMANCE")
    _complete_runtime_row(row)
    _write(path, rows)

    result = validate_pack(output)
    runtime = [item for item in result["blockers"] if "RUNTIME:WEIGHING_PERFORMANCE" in item]
    assert not any("AUTHORITATIVE_V1_REQUIRED" in item for item in result["blockers"])
    assert not any("SCHEMA_UNAVAILABLE" in item for item in runtime)
    assert not any("PAIR_UNAVAILABLE" in item for item in runtime)
    assert not any("INDEPENDENCE_REQUIRED" in item for item in runtime)


def test_validator_rejects_mixed_runtime_versions_without_matching_protocol(tmp_path):
    output = tmp_path / "pack"
    export_pack(output)
    path, rows, row = _runtime_row(output, "WEIGHING_PERFORMANCE")
    _complete_runtime_row(row, procedure="v2", observation="v1")
    _write(path, rows)

    result = validate_pack(output)
    assert "RUNTIME_SCHEMA_PAIR_UNAVAILABLE:RUNTIME:WEIGHING_PERFORMANCE" in result["blockers"]


def test_runtime_review_must_be_independent_and_candidate_columns_are_immutable(tmp_path):
    output = tmp_path / "pack"
    export_pack(output)
    path, rows, row = _runtime_row(output, "WEIGHING_PERFORMANCE")
    _complete_runtime_row(row, independent="false")
    row["available_procedure_schema_versions"] = "v1"
    _write(path, rows)

    result = validate_pack(output)
    assert "INDEPENDENCE_REQUIRED:RUNTIME:WEIGHING_PERFORMANCE" in result["blockers"]
    assert (
        "RUNTIME_SCHEMA_CANDIDATE_MISMATCH:RUNTIME:WEIGHING_PERFORMANCE:procedure"
        in result["blockers"]
    )


def test_supported_after_review_requires_boolean_semantics(tmp_path):
    output = tmp_path / "pack"
    export_pack(output)
    path = output / "04_test_review.csv"
    rows = _read(path)
    row = rows[0]
    row["supported_after_review"] = "maybe"
    _write(path, rows)

    result = validate_pack(output)
    assert (
        f"INVALID_BOOLEAN:TEST:{row['item_key']}:supported_after_review"
        in result["blockers"]
    )


def test_fix2_checklist_v2_policy_is_structurally_accepted(tmp_path):
    output = tmp_path / "pack"
    export_pack(output)
    path = output / "05_checklist_review.csv"
    rows = _read(path)
    row = rows[0]
    row["verified_applicability_policy_json"] = json.dumps(
        {
            "schema_version": "v2",
            "cases": [
                {
                    "when": {"kind": "boolean","feature":"printing_device_present","expected":True},
                    "decision": "REQUIRED",
                    "reason": "SYNTHETIC TEST FIXTURE ONLY",
                },
                {
                    "when": {"kind": "always"},
                    "decision": "NOT_APPLICABLE",
                    "reason": "SYNTHETIC TEST FIXTURE ONLY",
                },
            ],
        }
    )
    _write(path, rows)

    result = validate_pack(output)
    prefix = f"CHECKLIST:{row['item_key']}"
    assert f"INVALID_POLICY_SCHEMA:{prefix}" not in result["blockers"]
    assert f"INVALID_POLICY_STRUCTURE:{prefix}" not in result["blockers"]
    assert f"INVALID_POLICY_JSON:{prefix}" not in result["blockers"]
