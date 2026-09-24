"""Phase 16 Stage 2 context/render/storage contract tests."""

import hashlib
from io import BytesIO
from pathlib import Path
from uuid import uuid4
from zipfile import ZipFile

import pytest

from app.reporting.context import context_hash, preview_context
from app.reporting.renderers import (
    DOCX_MIME,
    PDF_MIME,
    build_plan,
    render_pair,
)
from app.storage.objects import StoredObject, safe_key, verify_content


def minimal_record():
    return {
        "schema_version": 1,
        "session": {
            "id": str(uuid4()),
            "application_number": None,
            "workflow_status": "DRAFT",
            "evaluation_status": "NOT_STARTED",
            "compliance_outcome": "UNDETERMINED",
        },
        "laboratory": {"name": "Synthetic Lab"},
        "manufacturer": {"name": "Synthetic Manufacturer"},
        "instrument_master_at_approval": {"model_name": "Synthetic Model"},
        "instrument_ranges_at_approval": [],
        "instrument_components_at_approval": [],
        "evaluation_instrument_snapshot": {},
        "ruleset_record": {
            "standard_code": "OIML R 76",
            "edition": "candidate",
            "version": "test",
            "verification_status": "DRAFT",
            "configuration_hash": "a" * 64,
        },
        "ruleset_snapshot": {},
        "sections": [
            {
                "section_number": number,
                "section_name": f"Section {number}",
                "applicability_status": "REQUIRES_REVIEW",
                "applicability_reason": "Synthetic preview",
                "evaluation_status": "NOT_STARTED",
                "compliance_outcome": "UNDETERMINED",
            }
            for number in range(1, 18)
        ],
        "requirements": [],
        "runs": [],
        "observations": [],
        "environment_readings": [],
        "equipment_links": [],
        "results": [],
        "result_events": [],
        "selection_events": [],
        "construction": {"examination": None, "items": [], "rules": []},
        "checklist": [],
        "evidence": [],
        "approval_actions": [],
        "actors": [],
    }


def test_preview_context_is_unofficial_numberless_and_hashable():
    context = preview_context(
        minimal_record(),
        requested_by=str(uuid4()),
        source_regulatory_revision=7,
    )
    assert context["document_kind"] == "UNOFFICIAL_PREVIEW"
    assert context["document_control"]["report_number"] is None
    assert context["document_control"]["revision_no"] is None
    assert context["document_control"]["report_status"] == "UNOFFICIAL_PREVIEW"
    assert len(context_hash(context)) == 64


def test_both_renderers_consume_one_plan_with_all_17_sections():
    context = preview_context(
        minimal_record(),
        requested_by=str(uuid4()),
        source_regulatory_revision=1,
    )
    plan = build_plan(context)
    assert plan.watermark == "UNOFFICIAL PREVIEW"
    summary = next(
        section
        for section in plan.sections
        if section.title == "Executive Summary - All 17 Sections"
    )
    assert len(summary.tables[0].rows) == 17

    rendered = render_pair(context)
    pdf, pdf_mime = rendered["pdf"]
    docx, docx_mime = rendered["docx"]

    assert pdf_mime == PDF_MIME
    assert docx_mime == DOCX_MIME
    assert pdf.startswith(b"%PDF-")
    assert b"%%EOF" in pdf[-2048:]
    assert docx.startswith(b"PK")
    with ZipFile(BytesIO(docx)) as archive:
        assert "word/document.xml" in archive.namelist()
        xml = archive.read("word/document.xml")
        assert b"UNOFFICIAL PREVIEW" in xml


@pytest.mark.parametrize("prefix", ["reports", "previews"])
def test_generated_document_storage_keys_are_server_shapes(prefix):
    key = f"{prefix}/{uuid4()}/{uuid4()}/{uuid4().hex}"
    assert safe_key(key) == key


def test_docx_content_integrity_validation():
    context = preview_context(
        minimal_record(),
        requested_by=str(uuid4()),
        source_regulatory_revision=1,
    )
    body, mime = render_pair(context)["docx"]
    digest = hashlib.sha256(body).hexdigest()
    assert (
        verify_content(
            StoredObject(body, mime, "v1"),
            len(body),
            mime,
            digest,
        )
        == digest
    )


def test_large_frozen_snapshot_renders_without_truncation():
    record = minimal_record()
    payload = "X" * 100_000
    record["ruleset_snapshot"] = {"synthetic_large_regression_value": payload}
    context = preview_context(
        record,
        requested_by=str(uuid4()),
        source_regulatory_revision=1,
    )

    plan = build_plan(context)
    manifest = next(
        section for section in plan.sections if section.title == "Reproducibility Manifest"
    )
    assert payload in manifest.tables[0].rows[-1][1]

    rendered = render_pair(context)
    assert rendered["pdf"][0].startswith(b"%PDF-")
    assert rendered["docx"][0].startswith(b"PK")


def test_report_renderers_do_not_import_engine_or_database_layers():
    source = Path("app/reporting/renderers.py").read_text()
    assert "R76Engine" not in source
    assert "sqlalchemy" not in source
    assert "app.repositories" not in source
    assert "app.services" not in source
