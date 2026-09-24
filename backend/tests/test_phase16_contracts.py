"""Phase 16 Stage 1 persistence and strict report-contract tests."""

from datetime import date
from pathlib import Path
from uuid import uuid4

import pytest
from pydantic import ValidationError
from sqlalchemy import CheckConstraint, Index, UniqueConstraint

from app.models.report import (
    GENERATION_STATUSES,
    PREVIEW_STATUSES,
    REPORT_FORMATS,
    REPORT_STATUSES,
    Report,
    ReportFile,
    ReportGeneration,
    ReportNumberCounter,
    ReportPreview,
)
from app.schemas.report import (
    ReportGenerateRequest,
    ReportIssueRequest,
    ReportRevisionRequest,
)

MIGRATION = Path("alembic/versions/0009_phase16.py").read_text()


def names(table, kind):
    values = set()
    for item in table.constraints | table.indexes:
        if isinstance(item, kind):
            values.add(item.name)
    return values


def test_phase16_models_register_frozen_tables():
    assert ReportNumberCounter.__tablename__ == "report_number_counters"
    assert Report.__tablename__ == "reports"
    assert ReportGeneration.__tablename__ == "report_generations"
    assert ReportFile.__tablename__ == "report_files"
    assert ReportPreview.__tablename__ == "report_previews"


def test_phase16_status_constants_match_frozen_contract():
    assert REPORT_STATUSES == ("UNISSUED", "ISSUED", "SUPERSEDED")
    assert GENERATION_STATUSES == ("GENERATING", "READY", "FAILED")
    assert REPORT_FORMATS == ("PDF", "DOCX")
    assert PREVIEW_STATUSES == ("GENERATING", "READY", "FAILED")


def test_phase16_report_lineage_and_current_issue_constraints_exist():
    assert "uq_report_session" in names(Report.__table__, UniqueConstraint)
    assert "uq_report_number_revision" in names(
        Report.__table__,
        UniqueConstraint,
    )
    assert "ck_report_lineage" in names(Report.__table__, CheckConstraint)
    assert "uq_report_current_issued" in names(Report.__table__, Index)


def test_phase16_generation_requires_frozen_context_and_attempt_identity():
    assert "uq_report_generation_attempt" in names(
        ReportGeneration.__table__,
        UniqueConstraint,
    )
    assert "ck_report_generation_context" in names(
        ReportGeneration.__table__,
        CheckConstraint,
    )
    assert "ck_report_generation_completion" in names(
        ReportGeneration.__table__,
        CheckConstraint,
    )


def test_phase16_report_file_pair_contract_is_unique_by_format():
    assert "uq_report_file_format" in names(
        ReportFile.__table__,
        UniqueConstraint,
    )
    assert "ck_report_file_format" in names(
        ReportFile.__table__,
        CheckConstraint,
    )


def test_phase16_request_contracts_are_strict():
    issuer = uuid4()
    generated = ReportGenerateRequest(
        intended_issuer_id=issuer,
        planned_issue_date=date(2026, 9, 24),
    )
    assert generated.intended_issuer_id == issuer

    with pytest.raises(ValidationError):
        ReportGenerateRequest(
            intended_issuer_id=issuer,
            planned_issue_date=date(2026, 9, 24),
            extra_field=True,
        )

    issue = ReportIssueRequest(
        generation_id=uuid4(),
        expected_predecessor_id=None,
    )
    assert issue.expected_predecessor_id is None

    with pytest.raises(ValidationError):
        ReportRevisionRequest(
            test_session_id=uuid4(),
            intended_issuer_id=issuer,
            planned_issue_date=date(2026, 9, 24),
            revision_reason=" ",
        )


def test_phase16_migration_follows_phase15_head():
    assert 'revision = "0009_phase16"' in MIGRATION
    assert 'down_revision = "0008_phase15"' in MIGRATION


def test_phase16_migration_requires_both_formats_before_ready():
    assert "READY generation requires exactly one PDF and one DOCX" in MIGRATION
    assert "count(*) FILTER (WHERE format = 'PDF')" in MIGRATION
    assert "count(*) FILTER (WHERE format = 'DOCX')" in MIGRATION


def test_phase16_migration_preserves_report_and_generation_history():
    assert "Report history is immutable" in MIGRATION
    assert "Report generation history is immutable" in MIGRATION
    assert "Report files are immutable" in MIGRATION
    assert "Completed report preview is immutable" in MIGRATION


def test_phase16_migration_keeps_issue_separate_from_generation():
    assert "Official report requires an approved session" in MIGRATION
    assert "Issued report requires the selected READY generation" in MIGRATION
    assert "uq_report_current_issued" in MIGRATION
