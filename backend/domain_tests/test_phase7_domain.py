"""Pure Phase 7 evaluator tests using synthetic-only regulatory fixtures."""

import pytest

from app.compliance.domain import ComplianceOutcome, EvaluationStatus
from app.compliance.phase7 import (
    CREEP_POLICY,
    DISCRIMINATION_POLICY,
    SENSITIVITY_POLICY,
    STABILITY_POLICY,
    ZERO_RETURN_POLICY,
)
from app.compliance.ruleset import TODO
from domain_tests.fixtures.phase7_functional_time import (
    creep_context,
    creep_observations,
    creep_rules,
    discrimination_observations,
    discrimination_rules,
    evaluate_creep,
    evaluate_discrimination,
    evaluate_sensitivity,
    evaluate_stability,
    evaluate_zero_return,
    sensitivity_rules,
    stability_observations,
    stability_rules,
    zero_return_context,
    zero_return_observations,
    zero_return_rules,
)
from domain_tests.fixtures.synthetic import instrument


@pytest.mark.parametrize("mode", ["DIGITAL", "ANALOG"])
def test_discrimination_equality_boundary_is_compliant(mode):
    result = evaluate_discrimination(mode=mode)
    assert result.evaluation_status == EvaluationStatus.COMPLETE
    assert result.compliance_outcome == ComplianceOutcome.COMPLIANT
    assert result.synthetic_fixture is True


@pytest.mark.parametrize(
    ("mode", "observations"),
    [
        (
            "DIGITAL",
            lambda: discrimination_observations(
                mode="DIGITAL",
                indication_change="9",
            ),
        ),
        (
            "ANALOG",
            lambda: discrimination_observations(
                mode="ANALOG",
                displacement_mm="1",
            ),
        ),
    ],
)
def test_discrimination_below_verified_fixture_response_fails(mode, observations):
    result = evaluate_discrimination(mode=mode, observations=observations())
    assert result.evaluation_status == EvaluationStatus.COMPLETE
    assert result.compliance_outcome == ComplianceOutcome.NONCOMPLIANT
    assert result.failed_conditions[0].code == "DISCRIMINATION_RESPONSE_INSUFFICIENT"


def test_discrimination_unverified_policy_is_review_required():
    result = evaluate_discrimination(
        ruleset=discrimination_rules(
            mode="DIGITAL",
            unverified=DISCRIMINATION_POLICY,
        )
    )
    assert result.evaluation_status == EvaluationStatus.REVIEW_REQUIRED
    assert result.compliance_outcome == ComplianceOutcome.UNDETERMINED
    assert result.issue_code == TODO
    assert DISCRIMINATION_POLICY in result.unresolved_rule_ids


def test_sensitivity_non_self_indicating_boundary_is_compliant():
    result = evaluate_sensitivity()
    assert result.evaluation_status == EvaluationStatus.COMPLETE
    assert result.compliance_outcome == ComplianceOutcome.COMPLIANT


def test_sensitivity_self_indicating_is_explicitly_not_applicable():
    result = evaluate_sensitivity(instrument_snapshot=instrument(is_self_indicating=True))
    assert result.evaluation_status == EvaluationStatus.COMPLETE
    assert result.compliance_outcome == ComplianceOutcome.NOT_APPLICABLE


def test_sensitivity_unverified_exact_procedure_stays_regulatory_blocked():
    result = evaluate_sensitivity(ruleset=sensitivity_rules(unverified=SENSITIVITY_POLICY))
    assert result.evaluation_status == EvaluationStatus.REVIEW_REQUIRED
    assert result.issue_code == TODO
    assert SENSITIVITY_POLICY in result.unresolved_rule_ids


def test_zero_return_equality_boundary_is_compliant():
    result = evaluate_zero_return()
    assert result.evaluation_status == EvaluationStatus.COMPLETE
    assert result.compliance_outcome == ComplianceOutcome.COMPLIANT


def test_zero_return_over_limit_is_noncompliant():
    result = evaluate_zero_return(observations=zero_return_observations(zero_after_g="6"))
    assert result.evaluation_status == EvaluationStatus.COMPLETE
    assert result.compliance_outcome == ComplianceOutcome.NONCOMPLIANT
    assert result.failed_conditions[0].code == "ZERO_RETURN_LIMIT_EXCEEDED"


def test_zero_return_cannot_complete_before_verified_hold_time():
    result = evaluate_zero_return(procedure_context=zero_return_context(hold_seconds="59"))
    assert result.evaluation_status == EvaluationStatus.INCOMPLETE
    assert result.compliance_outcome == ComplianceOutcome.UNDETERMINED
    assert any(issue.category == "TIMING" for issue in result.procedure_issues)


def test_zero_return_unverified_policy_is_review_required():
    result = evaluate_zero_return(ruleset=zero_return_rules(unverified=ZERO_RETURN_POLICY))
    assert result.evaluation_status == EvaluationStatus.REVIEW_REQUIRED
    assert ZERO_RETURN_POLICY in result.unresolved_rule_ids


@pytest.mark.parametrize("mode", ["SHORT", "EXTENDED"])
def test_creep_short_and_extended_equality_boundaries_are_compliant(mode):
    result = evaluate_creep(mode=mode)
    assert result.evaluation_status == EvaluationStatus.COMPLETE
    assert result.compliance_outcome == ComplianceOutcome.COMPLIANT


@pytest.mark.parametrize("mode", ["SHORT", "EXTENDED"])
def test_creep_limit_failure_is_noncompliant(mode):
    result = evaluate_creep(
        mode=mode,
        observations=creep_observations(mode=mode, final_change="6"),
    )
    assert result.evaluation_status == EvaluationStatus.COMPLETE
    assert result.compliance_outcome == ComplianceOutcome.NONCOMPLIANT
    assert result.failed_conditions[-1].code == "CREEP_LIMIT_EXCEEDED"


@pytest.mark.parametrize("mode", ["SHORT", "EXTENDED"])
def test_creep_missing_required_checkpoint_is_incomplete(mode):
    result = evaluate_creep(
        mode=mode,
        observations=creep_observations(mode=mode, omit_final=True),
    )
    assert result.evaluation_status == EvaluationStatus.INCOMPLETE
    assert result.compliance_outcome == ComplianceOutcome.UNDETERMINED
    assert any(
        issue.code == "MISSING_REQUIRED_OBSERVATIONS" and issue.category in {"COUNT", "TIMING"}
        for issue in result.procedure_issues
    )


def test_creep_cannot_complete_before_planned_verified_duration():
    result = evaluate_creep(
        procedure_context=creep_context(
            mode="SHORT",
            planned_duration_s="1799",
        )
    )
    assert result.evaluation_status == EvaluationStatus.INCOMPLETE
    assert any(issue.category == "TIMING" for issue in result.procedure_issues)


def test_creep_unverified_policy_is_review_required():
    result = evaluate_creep(ruleset=creep_rules(mode="SHORT", unverified=CREEP_POLICY))
    assert result.evaluation_status == EvaluationStatus.REVIEW_REQUIRED
    assert CREEP_POLICY in result.unresolved_rule_ids


def test_stability_print_store_zero_tare_pass_when_behavior_matches_policy():
    result = evaluate_stability()
    assert result.evaluation_status == EvaluationStatus.COMPLETE
    assert result.compliance_outcome == ComplianceOutcome.COMPLIANT
    assert len(result.calculations) == 8


def test_stability_unstable_operation_is_noncompliant():
    result = evaluate_stability(observations=stability_observations(failing_function="PRINTING"))
    assert result.evaluation_status == EvaluationStatus.COMPLETE
    assert result.compliance_outcome == ComplianceOutcome.NONCOMPLIANT
    assert result.failed_conditions[0].code == ("STABILITY_EQUILIBRIUM_FUNCTION_FAILED")


def test_stability_missing_required_zero_or_tare_subpart_is_incomplete():
    result = evaluate_stability(observations=stability_observations(omit_function="TARE"))
    assert result.evaluation_status == EvaluationStatus.INCOMPLETE
    assert result.compliance_outcome == ComplianceOutcome.UNDETERMINED
    assert any(issue.category == "COUNT" for issue in result.procedure_issues)


def test_stability_unverified_policy_is_review_required():
    result = evaluate_stability(ruleset=stability_rules(unverified=STABILITY_POLICY))
    assert result.evaluation_status == EvaluationStatus.REVIEW_REQUIRED
    assert STABILITY_POLICY in result.unresolved_rule_ids
