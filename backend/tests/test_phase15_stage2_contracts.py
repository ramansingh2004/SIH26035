"""Phase 15 Stage 2 review gate and correction-scope contracts."""

from types import SimpleNamespace
from uuid import uuid4

from app.services.review import submission_blockers
from app.services.review_scope import ALLOWED_CORRECTION_FIELDS


def session(*, evaluation="COMPLETE", outcome="COMPLIANT"):
    return SimpleNamespace(
        evaluation_status=evaluation,
        compliance_outcome=outcome,
    )


def sections(*, required_outcome="COMPLIANT"):
    values = []
    for number in range(1, 18):
        values.append(
            SimpleNamespace(
                section_number=number,
                applicability_status="REQUIRED" if number == 1 else "NOT_APPLICABLE",
                evaluation_status="COMPLETE",
                compliance_outcome=(required_outcome if number == 1 else "NOT_APPLICABLE"),
            )
        )
    return values


def requirement(*, outcome="COMPLIANT"):
    run_id = uuid4()
    result_id = uuid4()
    req = SimpleNamespace(
        requirement_key="SYNTHETIC_REQUIRED",
        applicability_status="REQUIRED",
        is_elected=False,
        selected_run_id=run_id,
        slot_snapshot={
            "section_number": 1,
            "test_code": "SYNTHETIC_TEST",
            "parent_test_code": None,
        },
    )
    run = SimpleNamespace(
        id=run_id,
        test_session_id=uuid4(),
        evaluation_status="COMPLETE",
        compliance_outcome=outcome,
        completed_at=object(),
        current_result_id=result_id,
        input_revision=3,
    )
    result = SimpleNamespace(
        id=result_id,
        test_run_id=run_id,
        source_input_revision=3,
        evaluation_status="COMPLETE",
        compliance_outcome=outcome,
    )
    return req, run, result


def blockers_for(*, outcome="COMPLIANT", evaluation="COMPLETE"):
    req, run, result = requirement(outcome=outcome)
    return submission_blockers(
        session(evaluation=evaluation, outcome=outcome),
        sections=sections(required_outcome=outcome),
        requirements=[req],
        runs={run.id: run},
        results={result.id: result},
    )


def test_phase15_complete_compliant_is_reviewable():
    assert blockers_for() == []


def test_phase15_complete_noncompliant_is_reviewable():
    assert blockers_for(outcome="NONCOMPLIANT") == []


def test_phase15_stale_is_not_reviewable():
    blockers = blockers_for(
        outcome="UNDETERMINED",
        evaluation="STALE",
    )
    assert "SESSION_EVALUATION:STALE" in blockers
    assert "SESSION_OUTCOME:UNDETERMINED" in blockers


def test_phase15_unverified_required_section_is_not_reviewable():
    req, run, result = requirement()
    rows = sections()
    rows[0].applicability_status = "REQUIRES_REVIEW"
    blockers = submission_blockers(
        session(),
        sections=rows,
        requirements=[req],
        runs={run.id: run},
        results={result.id: result},
    )
    assert "SECTION_1:APPLICABILITY_REVIEW_REQUIRED" in blockers


def test_phase15_missing_current_result_is_not_reviewable():
    req, run, _ = requirement()
    blockers = submission_blockers(
        session(),
        sections=sections(),
        requirements=[req],
        runs={run.id: run},
        results={},
    )
    assert "SYNTHETIC_REQUIRED:CURRENT_RESULT_REQUIRED" in blockers


def test_phase15_open_correction_blocks_resubmission():
    req, run, result = requirement()
    blockers = submission_blockers(
        session(),
        sections=sections(),
        requirements=[req],
        runs={run.id: run},
        results={result.id: result},
        open_corrections=[object()],
    )
    assert "SESSION:OPEN_CORRECTION_REQUEST" in blockers


def test_phase15_correction_field_allowlist_is_bounded():
    assert ALLOWED_CORRECTION_FIELDS["test_runs"] >= {
        "procedure_context",
        "retest",
        "observations",
        "environment",
        "equipment",
    }
    assert "password_hash" not in set().union(*ALLOWED_CORRECTION_FIELDS.values())
