"""Pure Phase 9 evaluator tests using synthetic-only regulatory fixtures."""

from decimal import Decimal

import pytest

from app.compliance.domain import ComplianceOutcome, EvaluationStatus
from app.compliance.phase9 import (
    DAMP_HEAT_POLICY,
    SPAN_STABILITY_POLICY,
)
from app.compliance.ruleset import TODO
from domain_tests.fixtures.phase9_climatic import (
    damp_heat_observations,
    damp_heat_rules,
    evaluate_damp_heat,
    evaluate_span,
    span_context,
    span_observations,
    span_rules,
)


def test_damp_heat_all_stages_and_loads_pass_at_mpe_boundary():
    result = evaluate_damp_heat()
    assert result.evaluation_status == EvaluationStatus.COMPLETE
    assert result.compliance_outcome == ComplianceOutcome.COMPLIANT
    assert result.synthetic_fixture is True
    assert len(result.calculations) == 12


def test_damp_heat_class_i_synthetic_policy_is_not_applicable():
    result = evaluate_damp_heat(accuracy_class="I")
    assert result.evaluation_status == EvaluationStatus.COMPLETE
    assert result.compliance_outcome == ComplianceOutcome.NOT_APPLICABLE


def test_damp_heat_over_mpe_is_noncompliant():
    result = evaluate_damp_heat(observations=damp_heat_observations(error_g="11"))
    assert result.evaluation_status == EvaluationStatus.COMPLETE
    assert result.compliance_outcome == ComplianceOutcome.NONCOMPLIANT
    assert any(item.code == "DAMP_HEAT_ERROR_LIMIT_EXCEEDED" for item in result.failed_conditions)


def test_damp_heat_functional_failure_is_noncompliant_not_incomplete():
    result = evaluate_damp_heat(observations=damp_heat_observations(functional_failure=True))
    assert result.evaluation_status == EvaluationStatus.COMPLETE
    assert result.compliance_outcome == ComplianceOutcome.NONCOMPLIANT
    assert any(
        item.code == "DAMP_HEAT_FUNCTIONAL_BEHAVIOR_FAILED" for item in result.failed_conditions
    )


@pytest.mark.parametrize(
    ("observations", "category"),
    [
        (
            lambda: damp_heat_observations(bad_environment_stage="HIGH_HUMIDITY"),
            "ENVIRONMENT",
        ),
        (
            lambda: damp_heat_observations(short_exposure_stage="HIGH_HUMIDITY"),
            "TIMING",
        ),
        (
            lambda: damp_heat_observations(reverse_final_loads=True),
            "ORDER",
        ),
        (
            lambda: damp_heat_observations(omit_last=True),
            "COUNT",
        ),
    ],
)
def test_damp_heat_procedure_incompleteness_is_blocked(
    observations,
    category,
):
    result = evaluate_damp_heat(observations=observations())
    assert result.evaluation_status == EvaluationStatus.INCOMPLETE
    assert result.compliance_outcome == ComplianceOutcome.UNDETERMINED
    assert any(issue.category == category for issue in result.procedure_issues)


def test_damp_heat_unverified_procedure_is_review_required():
    result = evaluate_damp_heat(ruleset=damp_heat_rules(unverified=DAMP_HEAT_POLICY))
    assert result.evaluation_status == EvaluationStatus.REVIEW_REQUIRED
    assert result.compliance_outcome == ComplianceOutcome.UNDETERMINED
    assert result.issue_code == TODO
    assert DAMP_HEAT_POLICY in result.unresolved_rule_ids


def test_span_stability_exact_variation_boundary_is_compliant():
    result = evaluate_span()
    assert result.evaluation_status == EvaluationStatus.COMPLETE
    assert result.compliance_outcome == ComplianceOutcome.COMPLIANT
    variation = next(
        item for item in result.calculations if item.name == "span_stability_variation"
    )
    assert variation.value == Decimal("10")


def test_span_stability_over_variation_limit_is_noncompliant():
    result = evaluate_span(observations=span_observations(errors=(0, 3, 6, 11)))
    assert result.evaluation_status == EvaluationStatus.COMPLETE
    assert result.compliance_outcome == ComplianceOutcome.NONCOMPLIANT
    assert result.failed_conditions[0].code == ("SPAN_STABILITY_VARIATION_LIMIT_EXCEEDED")


@pytest.mark.parametrize(
    ("observations", "category"),
    [
        (
            lambda: span_observations(elapsed=(0, 80, 180, 300)),
            "TIMING",
        ),
        (
            lambda: span_observations(elapsed=(0, 120, 220, 320)),
            "TIMING",
        ),
        (
            lambda: span_observations(missing_power_event=True),
            "POWER",
        ),
        (
            lambda: span_observations(short_power_event=True),
            "POWER",
        ),
    ],
)
def test_span_timing_and_power_requirements_block_incomplete_runs(
    observations,
    category,
):
    result = evaluate_span(observations=observations())
    assert result.evaluation_status == EvaluationStatus.INCOMPLETE
    assert result.compliance_outcome == ComplianceOutcome.UNDETERMINED
    assert any(issue.category == category for issue in result.procedure_issues)


def test_span_planned_duration_must_meet_verified_policy():
    result = evaluate_span(procedure_context=span_context(planned_duration_s="299"))
    assert result.evaluation_status == EvaluationStatus.INCOMPLETE
    assert any(issue.category == "TIMING" for issue in result.procedure_issues)


def test_span_unverified_correction_is_rejected():
    result = evaluate_span(observations=span_observations(corrections=(0, 0, 0, 1)))
    assert result.evaluation_status == EvaluationStatus.INCOMPLETE
    assert any(issue.category == "ENVIRONMENT" for issue in result.procedure_issues)


def test_span_verified_additive_correction_changes_variation():
    observations = span_observations(
        errors=(0, 3, 6, 11),
        corrections=(0, 0, 0, -1),
    )
    result = evaluate_span(
        observations=observations,
        ruleset=span_rules(correction_mode="ADD"),
    )
    assert result.evaluation_status == EvaluationStatus.COMPLETE
    assert result.compliance_outcome == ComplianceOutcome.COMPLIANT
    variation = next(
        item for item in result.calculations if item.name == "span_stability_variation"
    )
    assert variation.value == Decimal("10")


def test_span_trend_requires_extension_when_verified_policy_triggers():
    observations = span_observations(errors=(0, 3, 6, 9))
    result = evaluate_span(
        observations=observations,
        ruleset=span_rules(trend=True),
    )
    assert result.evaluation_status == EvaluationStatus.INCOMPLETE
    assert result.compliance_outcome == ComplianceOutcome.UNDETERMINED
    assert any(
        issue.category == "TIMING" and "extension" in issue.reason.lower()
        for issue in result.procedure_issues
    )


def test_span_completed_extension_allows_determined_result():
    observations = span_observations(
        errors=(0, 3, 6, 9),
        extension_errors=(8, 7),
    )
    result = evaluate_span(
        observations=observations,
        procedure_context=span_context(extension_completed=True),
        ruleset=span_rules(trend=True),
    )
    assert result.evaluation_status == EvaluationStatus.COMPLETE
    assert result.compliance_outcome == ComplianceOutcome.COMPLIANT
    assert len(result.calculations) == 7


def test_span_unverified_procedure_is_review_required():
    result = evaluate_span(ruleset=span_rules(unverified=SPAN_STABILITY_POLICY))
    assert result.evaluation_status == EvaluationStatus.REVIEW_REQUIRED
    assert result.compliance_outcome == ComplianceOutcome.UNDETERMINED
    assert result.issue_code == TODO
    assert SPAN_STABILITY_POLICY in result.unresolved_rule_ids
