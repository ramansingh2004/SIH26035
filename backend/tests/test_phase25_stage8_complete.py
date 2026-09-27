"""Phase 25 Stage 8 one-step engineering acceptance contracts."""

import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from app.compliance.stage8_acceptance import (
    REQUIRED_HTTP_STEPS,
    RUN_RECORD_NAME,
    Stage8AuthoritativeRunRecord,
    inspect_stage8_evidence,
    stage8_preflight,
)
from app.core.config import Settings
from app.main import create_app
from scripts.verify_phase25_stage8 import verify_stage8

REPO = Path(__file__).resolve().parents[2]


def _valid_record():
    return {
        "schema_version": 1,
        "status": "COMPLETE",
        "stage7_verified_artifact_ready": True,
        "synthetic_fixture": False,
        "ruleset_status": "ACTIVE",
        "ruleset_id": "ruleset-1",
        "ruleset_configuration_hash": "a" * 64,
        "stage7_manifest_hash": "b" * 64,
        "test_session_id": "session-1",
        "regulatory_revision": 7,
        "workflow_status": "REPORT_ISSUED",
        "evaluation_status": "COMPLETE",
        "compliance_outcome": "COMPLIANT",
        "approval_snapshot_hash": "c" * 64,
        "sections": [
            {
                "section_number": number,
                "applicability_status": "REQUIRED",
                "evaluation_status": "COMPLETE",
                "compliance_outcome": "COMPLIANT",
            }
            for number in range(1, 18)
        ],
        "report_id": "report-1",
        "report_number": "R76-2026-1",
        "report_revision_no": 1,
        "report_status": "ISSUED",
        "generation_id": "generation-1",
        "report_hash": "d" * 64,
        "files": [
            {
                "format": "PDF",
                "attachment_id": "pdf-attachment",
                "sha256": "e" * 64,
                "object_version": "pdf-v1",
            },
            {
                "format": "DOCX",
                "attachment_id": "docx-attachment",
                "sha256": "f" * 64,
                "object_version": "docx-v1",
            },
        ],
        "audit_evidence_reference": "acceptance/audit-export.json",
        "acceptance_evidence_package_sha256": "1" * 64,
    }


def test_stage8_preflight_fails_closed_until_stage7_is_ready():
    result = stage8_preflight()

    assert result.engineering_ready is True
    assert result.authoritative_ready is False
    assert "STAGE8:STAGE7_VERIFIED_ARTIFACT_REQUIRED" in result.blockers


def test_stage8_current_external_evidence_is_incomplete():
    result = inspect_stage8_evidence()

    assert result.complete is False
    assert any(RUN_RECORD_NAME in blocker for blocker in result.blockers)


def test_stage8_required_http_steps_are_unique():
    ids = [step.step_id for step in REQUIRED_HTTP_STEPS]
    routes = [(step.method, step.path) for step in REQUIRED_HTTP_STEPS]

    assert len(ids) == len(set(ids))
    assert len(routes) == len(set(routes))
    assert len(REQUIRED_HTTP_STEPS) >= 30


def test_stage8_all_required_http_routes_exist():
    schema = create_app(
        Settings(
            _env_file=None,
            environment="test",
            database_url=None,
        )
    ).openapi()

    for step in REQUIRED_HTTP_STEPS:
        assert step.path in schema["paths"], step
        assert step.method.lower() in schema["paths"][step.path], step


def test_stage8_authoritative_record_requires_exact_17_sections_and_two_formats():
    record = Stage8AuthoritativeRunRecord.model_validate(_valid_record())

    assert len(record.sections) == 17
    assert {item.section_number for item in record.sections} == set(range(1, 18))
    assert {item.format for item in record.files} == {"PDF", "DOCX"}
    assert len(record.record_hash) == 64


def test_stage8_authoritative_record_rejects_synthetic_fixture():
    value = _valid_record()
    value["synthetic_fixture"] = True

    with pytest.raises(ValidationError):
        Stage8AuthoritativeRunRecord.model_validate(value)


def test_stage8_authoritative_record_rejects_missing_section():
    value = _valid_record()
    value["sections"].pop()

    with pytest.raises(ValidationError):
        Stage8AuthoritativeRunRecord.model_validate(value)


def test_stage8_authoritative_record_rejects_duplicate_document_format():
    value = _valid_record()
    value["files"][1]["format"] = "PDF"

    with pytest.raises(ValidationError):
        Stage8AuthoritativeRunRecord.model_validate(value)


def test_stage8_template_is_explicitly_pending_and_not_completion_evidence():
    path = (
        REPO
        / "backend"
        / "app"
        / "compliance"
        / "rules"
        / "oiml_r76_2006_verified"
        / "stage8_authoritative_run.template.json"
    )
    value = json.loads(path.read_text(encoding="utf-8"))

    assert value["status"] == "PENDING_STAGE7_EXTERNAL_SIGNOFF"
    assert value["stage7_verified_artifact_ready"] is False
    assert value["report_hash"] is None

    with pytest.raises(ValidationError):
        Stage8AuthoritativeRunRecord.model_validate(value)


def test_stage8_runbook_preserves_real_retest_semantics():
    text = (
        REPO
        / "docs"
        / "regulatory"
        / "PHASE25_STAGE8_AUTHORITATIVE_RUNBOOK.md"
    ).read_text(encoding="utf-8")

    assert "Do not invent a retest" in text
    assert "ADMIN alone must not be used" in text
    assert "PDF" in text and "DOCX" in text


def test_stage8_docs_do_not_claim_authoritative_completion():
    root = (REPO / "PHASE25_STAGE8.md").read_text(encoding="utf-8")
    final = (
        REPO
        / "docs"
        / "regulatory"
        / "PHASE25_STAGE8_FINAL_ACCEPTANCE.md"
    ).read_text(encoding="utf-8")

    assert "STAGE 8 AUTHORITATIVE ACCEPTANCE HARNESS = COMPLETE" in root
    assert "does **not** mean" in root
    assert "**NOT YET EXECUTED.**" in final
    assert "candidate-v1" in final
    assert "SIH synthetic demo artifact" in final


def test_stage8_verifier_reports_current_stage7_block():
    result = verify_stage8()

    assert result["engineering_status"] == "COMPLETE"
    assert result["authoritative_status"] == "BLOCKED_STAGE7_EXTERNAL_SIGNOFF"
    assert result["authoritative_gate"] == "BLOCKED"
    assert result["stage7_authoritative_ready"] is False
    assert result["required_http_steps"] == len(REQUIRED_HTTP_STEPS)
    assert result["route_blockers"] == ()
    assert len(result["candidate_hash"]) == 64
