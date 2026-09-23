"""Pure Phase 11 endurance tests using synthetic-only verified rules."""

import pytest

from app.compliance.domain import ComplianceOutcome, EvaluationStatus
from app.compliance.phase11 import (
    ENDURANCE_MPE,
    ENDURANCE_POLICY,
)
from app.compliance.ruleset import TODO
from domain_tests.fixtures.phase11_endurance import (
    endurance_context,
    endurance_instrument,
    endurance_observations,
    endurance_rules,
    evaluate_endurance,
)


def test_endurance_required_branch_completes_at_exact_durability_boundary():
    result = evaluate_endurance()
    assert result.evaluation_status == EvaluationStatus.COMPLETE
    assert result.compliance_outcome == ComplianceOutcome.COMPLIANT
    assert result.synthetic_fixture is True
    assert len(result.acceptance_limits) == 2
    durability = [
        row.value for row in result.calculations if row.name.endswith(":durability_error")
    ]
    assert durability == [10, 10]


def test_endurance_beyond_verified_durability_boundary_is_noncompliant():
    result = evaluate_endurance(
        observations=endurance_observations(
            final_errors=("11", "10"),
        )
    )
    assert result.evaluation_status == EvaluationStatus.COMPLETE
    assert result.compliance_outcome == ComplianceOutcome.NONCOMPLIANT
    assert result.failed_conditions[0].code == ("ENDURANCE_DURABILITY_LIMIT_EXCEEDED")


@pytest.mark.parametrize(
    ("accuracy_class", "capacity"),
    [
        ("I", "20000"),
        ("III", "30000"),
    ],
)
def test_endurance_class_or_capacity_exclusion_is_not_applicable(
    accuracy_class,
    capacity,
):
    result = evaluate_endurance(
        instrument_snapshot=endurance_instrument(
            accuracy_class=accuracy_class,
            max_capacity_g=capacity,
        )
    )
    assert result.evaluation_status == EvaluationStatus.COMPLETE
    assert result.compliance_outcome == ComplianceOutcome.NOT_APPLICABLE


def test_incomplete_cycling_cannot_produce_completed_outcome():
    result = evaluate_endurance(
        procedure_context=endurance_context(
            completed_cycles=9,
        )
    )
    assert result.evaluation_status == EvaluationStatus.INCOMPLETE
    assert result.compliance_outcome == ComplianceOutcome.UNDETERMINED
    assert result.issue_code == "MISSING_REQUIRED_OBSERVATIONS"
    assert any(issue.category == "COUNT" for issue in result.procedure_issues)


def test_planned_cycle_count_mismatch_is_invalid_procedure():
    result = evaluate_endurance(
        procedure_context=endurance_context(
            planned_cycles=11,
        )
    )
    assert result.evaluation_status == EvaluationStatus.INCOMPLETE
    assert any(issue.category == "COUNT" for issue in result.procedure_issues)


def test_missing_cycle_timestamps_is_incomplete():
    result = evaluate_endurance(
        procedure_context=endurance_context(
            cycle_started_at=None,
            cycle_ended_at=None,
        )
    )
    assert result.evaluation_status == EvaluationStatus.INCOMPLETE
    assert any(issue.category == "TIMING" for issue in result.procedure_issues)


def test_too_short_cycle_duration_is_incomplete():
    result = evaluate_endurance(
        procedure_context=endurance_context(
            cycle_started_at="2000-01-02T00:00:00Z",
            cycle_ended_at="2000-01-02T00:00:30Z",
        )
    )
    assert result.evaluation_status == EvaluationStatus.INCOMPLETE
    assert any(issue.category == "TIMING" for issue in result.procedure_issues)


def test_missing_final_performance_point_is_incomplete():
    result = evaluate_endurance(
        observations=endurance_observations(
            omit_final=True,
        )
    )
    assert result.evaluation_status == EvaluationStatus.INCOMPLETE
    assert result.issue_code == "MISSING_REQUIRED_OBSERVATIONS"


def test_out_of_order_final_points_are_invalid():
    result = evaluate_endurance(
        observations=endurance_observations(
            reverse_final=True,
        )
    )
    assert result.evaluation_status == EvaluationStatus.INCOMPLETE
    assert any(issue.category == "ORDER" for issue in result.procedure_issues)


def test_initial_final_loads_must_match_for_each_point():
    result = evaluate_endurance(
        observations=endurance_observations(
            mismatched_pair=True,
        )
    )
    assert result.evaluation_status == EvaluationStatus.INCOMPLETE
    assert any(issue.category == "LOAD_COVERAGE" for issue in result.procedure_issues)


def test_initial_measurements_must_precede_cycling_and_final_follow_it():
    result = evaluate_endurance(
        observations=endurance_observations(
            final_before_cycle_end=True,
        )
    )
    assert result.evaluation_status == EvaluationStatus.INCOMPLETE
    assert any(issue.category == "TIMING" for issue in result.procedure_issues)


def test_same_reference_weights_are_required_when_policy_demands_them():
    result = evaluate_endurance(
        procedure_context=endurance_context(
            same_reference_weights_confirmed=False,
        )
    )
    assert result.evaluation_status == EvaluationStatus.INCOMPLETE
    assert any(issue.category == "EQUIPMENT" for issue in result.procedure_issues)


@pytest.mark.parametrize(
    ("field", "category"),
    [
        ("environment", "ENVIRONMENT"),
        ("equipment", "EQUIPMENT"),
        ("evidence_hashes", "EVIDENCE"),
    ],
)
def test_endurance_traceability_prerequisites_are_enforced(
    field,
    category,
):
    result = evaluate_endurance(
        procedure_context=endurance_context(
            **{field: ()},
        )
    )
    assert result.evaluation_status == EvaluationStatus.INCOMPLETE
    assert any(issue.category == category for issue in result.procedure_issues)


def test_equipment_certificate_evidence_is_required():
    context = endurance_context()
    equipment = [item.model_dump(mode="python") for item in context.equipment]
    equipment[0]["certificate_content_hash"] = None
    result = evaluate_endurance(
        procedure_context=endurance_context(
            equipment=equipment,
        )
    )
    assert result.evaluation_status == EvaluationStatus.INCOMPLETE
    assert any(issue.category == "EQUIPMENT" for issue in result.procedure_issues)


def test_unresolved_abnormal_event_blocks_completion():
    result = evaluate_endurance(
        procedure_context=endurance_context(
            abnormal_events=("SYNTHETIC_EVENT",),
            abnormal_events_resolved=False,
        )
    )
    assert result.evaluation_status == EvaluationStatus.INCOMPLETE
    assert any(issue.category == "FUNCTIONAL" for issue in result.procedure_issues)


@pytest.mark.parametrize(
    "rule_id",
    [
        ENDURANCE_POLICY,
        ENDURANCE_MPE,
    ],
)
def test_unverified_endurance_rule_requires_review(rule_id):
    result = evaluate_endurance(
        ruleset=endurance_rules(
            unverified=rule_id,
        )
    )
    assert result.evaluation_status == EvaluationStatus.REVIEW_REQUIRED
    assert result.compliance_outcome == ComplianceOutcome.UNDETERMINED
    assert result.issue_code == TODO
    assert rule_id in result.unresolved_rule_ids
