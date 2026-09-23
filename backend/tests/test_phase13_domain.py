"""Pure Phase 13 ChecklistEngine tests."""

from app.compliance.checklist import (
    ChecklistApplicabilityPolicy,
    ChecklistAssessment,
    ChecklistEngine,
    ChecklistRuleInput,
)
from domain_tests.fixtures.synthetic import instrument


def verified_rule(
    *,
    key="GENERAL_TEST",
    group="GENERAL",
    expression=None,
    evidence_required=False,
):
    if expression is None:
        expression = ChecklistApplicabilityPolicy(
            schema_version="v1",
            mode="ALL",
            conditions=(),
            when_match="REQUIRED",
            when_not_match="NOT_APPLICABLE",
            match_reason="Synthetic verified applicable row",
            no_match_reason="Synthetic verified excluded row",
        ).model_dump(mode="json")
    return ChecklistRuleInput(
        rule_key=key,
        group_code=group,
        validation_status="VERIFIED",
        applicability_expression=expression,
        evidence_required=evidence_required,
    )


def assessment(
    *,
    key="GENERAL_TEST",
    result="NOT_EXAMINED",
    evidence_required=False,
    evidence_count=0,
):
    rule = verified_rule(
        key=key,
        evidence_required=evidence_required,
    )
    decision = ChecklistEngine.applicability(instrument(), rule)
    return ChecklistAssessment(
        rule_key=key,
        decision=decision,
        validation_status=rule.validation_status,
        evidence_required=rule.evidence_required,
        response_result=result,
        evidence_count=evidence_count,
    )


def test_phase13_verified_always_policy_is_required():
    decision = ChecklistEngine.applicability(
        instrument(),
        verified_rule(),
    )
    assert decision.applicability == "REQUIRED"


def test_phase13_boolean_feature_policy_can_exclude():
    policy = {
        "schema_version": "v1",
        "mode": "ALL",
        "conditions": [{"feature": "is_electronic", "equals": True}],
        "when_match": "REQUIRED",
        "when_not_match": "NOT_APPLICABLE",
        "match_reason": "Electronic",
        "no_match_reason": "Not electronic",
    }
    decision = ChecklistEngine.applicability(
        instrument(is_electronic=False),
        verified_rule(
            group="ELECTRONIC",
            expression=policy,
        ),
    )
    assert decision.applicability == "NOT_APPLICABLE"


def test_phase13_unknown_feature_requires_review():
    policy = {
        "schema_version": "v1",
        "mode": "ALL",
        "conditions": [{"feature": "is_electronic", "equals": True}],
        "when_match": "REQUIRED",
        "when_not_match": "NOT_APPLICABLE",
        "match_reason": "Electronic",
        "no_match_reason": "Not electronic",
    }
    decision = ChecklistEngine.applicability(
        instrument(is_electronic=None),
        verified_rule(
            group="ELECTRONIC",
            expression=policy,
        ),
    )
    assert decision.applicability == "REQUIRES_REVIEW"
    assert decision.unresolved_rule_ids == ("GENERAL_TEST",)


def test_phase13_unverified_rule_requires_review():
    rule = ChecklistRuleInput(
        rule_key="PENDING",
        group_code="GENERAL",
        validation_status="TODO_REGULATORY_VALIDATION",
        applicability_expression={
            "schema_version": 1,
            "status": "TODO_REGULATORY_VALIDATION",
        },
        evidence_required=None,
    )
    decision = ChecklistEngine.applicability(instrument(), rule)
    assert decision.applicability == "REQUIRES_REVIEW"


def test_phase13_missing_catalog_is_review_required():
    summary = ChecklistEngine.summarize(())
    assert summary["evaluation_status"] == "REVIEW_REQUIRED"
    assert summary["compliance_outcome"] == "UNDETERMINED"


def test_phase13_unexamined_required_row_is_not_started():
    summary = ChecklistEngine.summarize([assessment()])
    assert summary["evaluation_status"] == "NOT_STARTED"
    assert summary["not_examined"] == 1


def test_phase13_fail_is_answered_and_complete_negative():
    summary = ChecklistEngine.summarize(
        [assessment(result="FAIL")],
        completion_requested=True,
    )
    assert summary["evaluation_status"] == "COMPLETE"
    assert summary["compliance_outcome"] == "NONCOMPLIANT"
    assert summary["failed"] == 1


def test_phase13_missing_required_evidence_is_incomplete():
    summary = ChecklistEngine.summarize(
        [
            assessment(
                result="PASS",
                evidence_required=True,
                evidence_count=0,
            )
        ],
        completion_requested=True,
    )
    assert summary["evaluation_status"] == "INCOMPLETE"


def test_phase13_evidence_allows_complete_positive():
    summary = ChecklistEngine.summarize(
        [
            assessment(
                result="PASS",
                evidence_required=True,
                evidence_count=1,
            )
        ],
        completion_requested=True,
    )
    assert summary["evaluation_status"] == "COMPLETE"
    assert summary["compliance_outcome"] == "COMPLIANT"


def test_phase13_known_failure_survives_other_incomplete_row():
    summary = ChecklistEngine.summarize(
        [
            assessment(key="A", result="FAIL"),
            assessment(key="B", result="NOT_EXAMINED"),
        ],
        completion_requested=True,
    )
    assert summary["evaluation_status"] == "INCOMPLETE"
    assert summary["compliance_outcome"] == "NONCOMPLIANT"


def test_phase13_review_blocker_keeps_outcome_undetermined():
    pending = ChecklistAssessment(
        rule_key="PENDING",
        decision=ChecklistEngine.applicability(
            instrument(),
            ChecklistRuleInput(
                rule_key="PENDING",
                group_code="GENERAL",
                validation_status="TODO_REGULATORY_VALIDATION",
                applicability_expression={
                    "schema_version": 1,
                    "status": "TODO_REGULATORY_VALIDATION",
                },
                evidence_required=None,
            ),
        ),
        validation_status="TODO_REGULATORY_VALIDATION",
        evidence_required=None,
        response_result="NOT_EXAMINED",
    )
    summary = ChecklistEngine.summarize(
        [assessment(result="FAIL"), pending],
        completion_requested=True,
    )
    assert summary["evaluation_status"] == "REVIEW_REQUIRED"
    assert summary["compliance_outcome"] == "UNDETERMINED"


def test_phase13_retained_excluded_row_counts_not_applicable():
    policy = {
        "schema_version": "v1",
        "mode": "ALL",
        "conditions": [{"feature": "is_electronic", "equals": True}],
        "when_match": "REQUIRED",
        "when_not_match": "NOT_APPLICABLE",
        "match_reason": "Electronic",
        "no_match_reason": "Not electronic",
    }
    rule = verified_rule(
        key="ELECTRONIC_ONLY",
        group="ELECTRONIC",
        expression=policy,
    )
    decision = ChecklistEngine.applicability(
        instrument(is_electronic=False),
        rule,
    )
    summary = ChecklistEngine.summarize(
        [
            ChecklistAssessment(
                rule_key=rule.rule_key,
                decision=decision,
                validation_status="VERIFIED",
                evidence_required=False,
                response_result="NOT_APPLICABLE",
            )
        ],
        completion_requested=True,
    )
    assert summary["catalog_total"] == 1
    assert summary["not_applicable"] == 1
    assert summary["evaluation_status"] == "COMPLETE"
    assert summary["compliance_outcome"] == "NOT_APPLICABLE"
