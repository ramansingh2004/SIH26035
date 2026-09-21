import pytest

from app.compliance.aggregation import (
    AggregationChild,
    AggregationInput,
    SectionResultAggregator,
    SessionComplianceAggregator,
)
from app.compliance.domain import Applicability, ComplianceOutcome, EvaluationStatus


def child(key, status="COMPLETE", outcome="COMPLIANT", **kwargs):
    return AggregationChild(
        semantic_key=key,
        evaluation_status=status,
        compliance_outcome=outcome,
        **(dict(applicability="REQUIRED") | kwargs),
    )


@pytest.mark.parametrize("aggregator", [SectionResultAggregator, SessionComplianceAggregator])
@pytest.mark.parametrize(
    "children,flags,status,outcome",
    [
        ((), {}, "NOT_STARTED", "UNDETERMINED"),
        ((child("a", "NOT_STARTED", "UNDETERMINED"),), {}, "NOT_STARTED", "UNDETERMINED"),
        (
            (child("a"), child("b", "NOT_STARTED", "UNDETERMINED")),
            {},
            "IN_PROGRESS",
            "UNDETERMINED",
        ),
        ((child("a"), child("b")), {}, "COMPLETE", "COMPLIANT"),
        ((child("a", "IN_PROGRESS", "UNDETERMINED"),), {}, "IN_PROGRESS", "UNDETERMINED"),
        (
            (child("a", "INCOMPLETE", "UNDETERMINED"), child("b", "IN_PROGRESS", "UNDETERMINED")),
            {},
            "INCOMPLETE",
            "UNDETERMINED",
        ),
        (
            (
                child("a", "REVIEW_REQUIRED", "UNDETERMINED"),
                child("b", "INCOMPLETE", "UNDETERMINED"),
            ),
            {},
            "REVIEW_REQUIRED",
            "UNDETERMINED",
        ),
        (
            (
                child("a", "STALE", "NONCOMPLIANT", current=False),
                child("b", "REVIEW_REQUIRED", "UNDETERMINED"),
            ),
            {},
            "STALE",
            "UNDETERMINED",
        ),
        (
            (child("a", "COMPLETE", "NONCOMPLIANT"), child("b", "INCOMPLETE", "UNDETERMINED")),
            {},
            "INCOMPLETE",
            "NONCOMPLIANT",
        ),
        (
            (child("a", "COMPLETE", "NONCOMPLIANT"), child("b", "NOT_STARTED", "UNDETERMINED")),
            {},
            "IN_PROGRESS",
            "NONCOMPLIANT",
        ),
        (
            (child("a", "COMPLETE", "NONCOMPLIANT"), child("b", "STALE", "UNDETERMINED")),
            {},
            "STALE",
            "NONCOMPLIANT",
        ),
        ((child("a"),), {"missing_mandatory_stages": True}, "INCOMPLETE", "UNDETERMINED"),
        ((child("a"),), {"unresolved_rule_ids": ("REG-02",)}, "REVIEW_REQUIRED", "UNDETERMINED"),
        (
            (child("a", "COMPLETE", "NOT_APPLICABLE", applicability="NOT_APPLICABLE"),),
            {},
            "COMPLETE",
            "NOT_APPLICABLE",
        ),
        (
            (child("a"), child("optional", "STALE", "NONCOMPLIANT", applicability="OPTIONAL")),
            {},
            "COMPLETE",
            "COMPLIANT",
        ),
        (
            (
                child("a"),
                child(
                    "optional", "COMPLETE", "NONCOMPLIANT", applicability="OPTIONAL", elected=True
                ),
            ),
            {},
            "COMPLETE",
            "NONCOMPLIANT",
        ),
        ((child("optional", applicability="OPTIONAL"),), {}, "NOT_STARTED", "UNDETERMINED"),
        (
            (child("review", "NOT_STARTED", "UNDETERMINED", applicability="REQUIRES_REVIEW"),),
            {},
            "REVIEW_REQUIRED",
            "UNDETERMINED",
        ),
    ],
)
def test_f05_aggregation(aggregator, children, flags, status, outcome):
    result = aggregator.aggregate(AggregationInput(children=children, **flags))
    assert result.evaluation_status == status
    assert result.compliance_outcome == outcome


def test_invalid_child_identity_and_election():
    with pytest.raises(ValueError, match="Duplicate"):
        AggregationInput(children=(child("a"), child("a")))
    with pytest.raises(ValueError, match="Only optional"):
        child("a", elected=True)


def test_negative_current_descendant_survives_stale_section_summary():
    section = SectionResultAggregator.aggregate(
        AggregationInput(
            children=(
                child("failure", "COMPLETE", "NONCOMPLIANT"),
                child("historical", "STALE", "UNDETERMINED"),
            )
        )
    )
    assert section.evaluation_status == "STALE" and section.has_current_failure
    summary = AggregationChild.from_aggregate(
        semantic_key="section-1", applicability="REQUIRED", result=section
    )
    session = SessionComplianceAggregator.aggregate(AggregationInput(children=(summary,)))
    assert session.evaluation_status == "STALE"
    assert session.compliance_outcome == "NONCOMPLIANT"


def test_status_axes_exact():
    from app.compliance.domain import WorkflowStatus

    assert {s.value for s in WorkflowStatus} == {
        "DRAFT",
        "INSTRUMENT_CONFIGURATION",
        "APPLICABILITY_CONFIRMED",
        "TESTING",
        "EXAMINATION",
        "UNDER_REVIEW",
        "APPROVED",
        "REPORT_ISSUED",
        "REJECTED",
        "CANCELLED",
    }
    assert {s.value for s in EvaluationStatus} == {
        "NOT_STARTED",
        "IN_PROGRESS",
        "INCOMPLETE",
        "STALE",
        "REVIEW_REQUIRED",
        "COMPLETE",
    }
    assert {s.value for s in ComplianceOutcome} == {
        "UNDETERMINED",
        "COMPLIANT",
        "NONCOMPLIANT",
        "NOT_APPLICABLE",
    }
    assert {s.value for s in Applicability} == {
        "REQUIRED",
        "OPTIONAL",
        "NOT_APPLICABLE",
        "REQUIRES_REVIEW",
    }
