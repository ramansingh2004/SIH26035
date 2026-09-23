"""Pure Phase 10 evaluator tests using synthetic-only disturbance rules."""

import pytest

from app.compliance.domain import ComplianceOutcome, EvaluationStatus
from app.compliance.phase10 import (
    DISTURBANCE_BURST,
    DISTURBANCE_CODES,
    DISTURBANCE_POLICY_KEYS,
    DISTURBANCE_VEHICLE_SUPPLY,
)
from app.compliance.ruleset import TODO
from domain_tests.fixtures.phase10_disturbances import (
    disturbance_context,
    disturbance_observations,
    disturbance_rules,
    evaluate_disturbance,
)
from domain_tests.fixtures.synthetic import instrument


@pytest.mark.parametrize("code", DISTURBANCE_CODES)
def test_each_family_passes_exact_deviation_boundary(code):
    result = evaluate_disturbance(code)
    assert result.evaluation_status == EvaluationStatus.COMPLETE
    assert result.compliance_outcome == ComplianceOutcome.COMPLIANT
    assert result.synthetic_fixture is True
    assert len(result.calculations) == 4


@pytest.mark.parametrize("code", DISTURBANCE_CODES)
def test_each_family_excessive_unhandled_effect_fails(code):
    result = evaluate_disturbance(
        code,
        observations=disturbance_observations(code, deviation_g="11"),
    )
    assert result.evaluation_status == EvaluationStatus.COMPLETE
    assert result.compliance_outcome == ComplianceOutcome.NONCOMPLIANT
    assert all(
        item.code == "DISTURBANCE_EFFECT_NOT_ACCEPTABLY_HANDLED"
        for item in result.failed_conditions
    )


@pytest.mark.parametrize("code", DISTURBANCE_CODES)
def test_each_family_accepts_verified_handled_fault(code):
    result = evaluate_disturbance(
        code,
        observations=disturbance_observations(
            code,
            deviation_g="11",
            handled=True,
        ),
    )
    assert result.evaluation_status == EvaluationStatus.COMPLETE
    assert result.compliance_outcome == ComplianceOutcome.COMPLIANT


@pytest.mark.parametrize("code", DISTURBANCE_CODES)
def test_unaccepted_fault_response_does_not_rescue_excessive_effect(code):
    result = evaluate_disturbance(
        code,
        observations=disturbance_observations(
            code,
            deviation_g="11",
            handled=True,
            accepted_response=False,
        ),
    )
    assert result.evaluation_status == EvaluationStatus.COMPLETE
    assert result.compliance_outcome == ComplianceOutcome.NONCOMPLIANT


def test_missing_verified_severity_blocks_evaluation():
    code = DISTURBANCE_BURST
    result = evaluate_disturbance(
        code,
        procedure_context=disturbance_context(
            code,
            omit_severity=True,
        ),
    )
    assert result.evaluation_status == EvaluationStatus.INCOMPLETE
    assert result.compliance_outcome == ComplianceOutcome.UNDETERMINED
    assert any(issue.category == "SEVERITY" for issue in result.procedure_issues)


def test_missing_repetition_blocks_evaluation():
    code = DISTURBANCE_BURST
    result = evaluate_disturbance(
        code,
        observations=disturbance_observations(
            code,
            omit_last=True,
        ),
    )
    assert result.evaluation_status == EvaluationStatus.INCOMPLETE
    assert any(issue.category in {"COUNT", "ORDER"} for issue in result.procedure_issues)


def test_bad_repetition_order_blocks_evaluation():
    code = DISTURBANCE_BURST
    result = evaluate_disturbance(
        code,
        observations=disturbance_observations(
            code,
            bad_repetition_order=True,
        ),
    )
    assert result.evaluation_status == EvaluationStatus.INCOMPLETE
    assert any(issue.category == "ORDER" for issue in result.procedure_issues)


def test_missing_waveform_reference_blocks_evaluation():
    code = DISTURBANCE_BURST
    result = evaluate_disturbance(
        code,
        procedure_context=disturbance_context(
            code,
            missing_waveform=True,
        ),
    )
    assert result.evaluation_status == EvaluationStatus.INCOMPLETE
    assert any(issue.category == "EVIDENCE" for issue in result.procedure_issues)


def test_detected_fault_without_response_is_incomplete():
    code = DISTURBANCE_BURST
    result = evaluate_disturbance(
        code,
        observations=disturbance_observations(
            code,
            deviation_g="11",
            handled=True,
            missing_response=True,
        ),
    )
    assert result.evaluation_status == EvaluationStatus.INCOMPLETE
    assert any(issue.category == "FUNCTIONAL" for issue in result.procedure_issues)


def test_detected_fault_without_response_evidence_is_incomplete():
    code = DISTURBANCE_BURST
    result = evaluate_disturbance(
        code,
        observations=disturbance_observations(
            code,
            deviation_g="11",
            handled=True,
            missing_fault_evidence=True,
        ),
    )
    assert result.evaluation_status == EvaluationStatus.INCOMPLETE
    assert any(issue.category == "EVIDENCE" for issue in result.procedure_issues)


def test_missing_state_trace_is_incomplete():
    code = DISTURBANCE_BURST
    result = evaluate_disturbance(
        code,
        observations=disturbance_observations(
            code,
            missing_state=True,
        ),
    )
    assert result.evaluation_status == EvaluationStatus.INCOMPLETE
    assert any(issue.category == "EVIDENCE" for issue in result.procedure_issues)


@pytest.mark.parametrize(
    "field",
    [
        "warm_up_completed",
        "environment_stabilized",
        "peripherals_connected",
    ],
)
def test_shared_disturbance_prerequisites_are_enforced(field):
    code = DISTURBANCE_BURST
    result = evaluate_disturbance(
        code,
        procedure_context=disturbance_context(
            code,
            **{field: False},
        ),
    )
    assert result.evaluation_status == EvaluationStatus.INCOMPLETE


def test_missing_no_load_deviation_is_incomplete():
    code = DISTURBANCE_BURST
    result = evaluate_disturbance(
        code,
        procedure_context=disturbance_context(
            code,
            no_load_deviation_g=None,
        ),
    )
    assert result.evaluation_status == EvaluationStatus.INCOMPLETE
    assert any(issue.category == "LOAD_COVERAGE" for issue in result.procedure_issues)


@pytest.mark.parametrize(
    "variant",
    [
        "SUPPLY_LINE_CONDUCTION",
        "NON_SUPPLY_LINE_COUPLING",
    ],
)
def test_both_vehicle_subvariants_have_determined_results(variant):
    result = evaluate_disturbance(
        DISTURBANCE_VEHICLE_SUPPLY,
        variant=variant,
        vehicle_powered=True,
    )
    assert result.evaluation_status == EvaluationStatus.COMPLETE
    assert result.compliance_outcome == ComplianceOutcome.COMPLIANT


def test_vehicle_supply_not_applicable_when_explicitly_not_vehicle_powered():
    result = evaluate_disturbance(
        DISTURBANCE_VEHICLE_SUPPLY,
        vehicle_powered=False,
    )
    assert result.evaluation_status == EvaluationStatus.COMPLETE
    assert result.compliance_outcome == ComplianceOutcome.NOT_APPLICABLE


def test_vehicle_supply_unknown_power_fact_requires_review():
    code = DISTURBANCE_VEHICLE_SUPPLY
    result = evaluate_disturbance(
        code,
        instrument_snapshot=instrument(vehicle_powered=None),
    )
    assert result.evaluation_status == EvaluationStatus.REVIEW_REQUIRED
    assert result.compliance_outcome == ComplianceOutcome.UNDETERMINED
    assert result.issue_code == "INSTRUMENT_FACTS_REQUIRED"


def test_unverified_disturbance_policy_is_review_required():
    code = DISTURBANCE_BURST
    policy_key = DISTURBANCE_POLICY_KEYS[code]
    result = evaluate_disturbance(
        code,
        ruleset=disturbance_rules(
            code,
            unverified=policy_key,
        ),
    )
    assert result.evaluation_status == EvaluationStatus.REVIEW_REQUIRED
    assert result.compliance_outcome == ComplianceOutcome.UNDETERMINED
    assert result.issue_code == TODO
    assert policy_key in result.unresolved_rule_ids
