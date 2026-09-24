"""Phase 16 Stage 3 report-integrity and phase-boundary contracts."""

from pathlib import Path

from app.reporting.context import (
    issuance_manifest,
    report_hash,
)


def test_report_hash_is_nonrecursive_and_format_order_independent():
    first = report_hash(
        "a" * 64,
        {
            "pdf": "b" * 64,
            "docx": "c" * 64,
        },
    )
    second = report_hash(
        "a" * 64,
        {
            "docx": "c" * 64,
            "pdf": "b" * 64,
        },
    )
    changed = report_hash(
        "a" * 64,
        {
            "pdf": "d" * 64,
            "docx": "c" * 64,
        },
    )
    assert first == second
    assert first != changed
    assert len(first) == 64


def test_issue_manifest_contains_hashes_but_no_self_hash():
    manifest = issuance_manifest(
        report_id="00000000-0000-0000-0000-000000000001",
        report_number="R76-2026-1",
        revision_no=1,
        generation_id="00000000-0000-0000-0000-000000000002",
        context_digest="a" * 64,
        file_hashes={
            "pdf": "b" * 64,
            "docx": "c" * 64,
        },
        final_report_hash="d" * 64,
        issued_by="00000000-0000-0000-0000-000000000003",
        issued_at="2026-09-24T10:00:00+00:00",
        predecessor_id=None,
    )
    assert manifest["report_hash"] == "d" * 64
    assert manifest["file_hashes"] == {
        "DOCX": "c" * 64,
        "PDF": "b" * 64,
    }
    assert "manifest_hash" not in manifest


def test_phase16_stage3_reporting_remains_independent_of_dashboard_layer():
    api = Path("app/api/v1/report.py").read_text()
    assert "/dashboard/summary" not in api


def test_official_reporting_service_never_imports_compliance_engine():
    source = Path("app/services/report.py").read_text()
    assert "R76Engine" not in source
    assert ".evaluate(" not in source
    assert "ApprovalSnapshotBuilder" in source  # preview only
    assert "snapshot.snapshot_json" in source  # official source


def test_reg17_gate_remains_explicit_in_issue_workflow():
    source = Path("app/services/report.py").read_text()
    assert '"TODO_REGULATORY_VALIDATION"' in source
    assert '"REG-17"' in source
    assert "SYNTHETIC_TEST_FIXTURE_ONLY" in source
