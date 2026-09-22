"""Pure Phase 8 evaluator tests using synthetic-only regulatory fixtures."""

import pytest

from app.compliance.domain import ComplianceOutcome, EvaluationStatus
from app.compliance.phase8 import (
    TEMPERATURE_ZERO_POLICY,
    TILTING_POLICY,
    VOLTAGE_POLICY,
    WARM_UP_POLICY,
)
from app.compliance.ruleset import TODO
from domain_tests.fixtures.phase8_influence import (
    VOLTAGE_PROFILE_DATA,
    evaluate_temperature,
    evaluate_tilting,
    evaluate_voltage,
    evaluate_warm_up,
    temperature_observations,
    temperature_rules,
    tilting_observations,
    tilting_rules,
    voltage_observations,
    voltage_rules,
    warm_up_context,
    warm_up_observations,
    warm_up_rules,
)
from domain_tests.fixtures.synthetic import instrument


@pytest.mark.parametrize("accuracy_class", ["I", "III"])
def test_temperature_class_specific_normalization_passes_below_strict_limit(
    accuracy_class,
):
    result = evaluate_temperature(accuracy_class=accuracy_class)
    assert result.evaluation_status == EvaluationStatus.COMPLETE
    assert result.compliance_outcome == ComplianceOutcome.COMPLIANT
    assert result.synthetic_fixture is True


@pytest.mark.parametrize("accuracy_class", ["I", "III"])
def test_temperature_equality_fails_verified_strict_boundary(
    accuracy_class,
):
    result = evaluate_temperature(
        accuracy_class=accuracy_class,
        observations=temperature_observations(
            accuracy_class=accuracy_class,
            drift_g="10",
        ),
    )
    assert result.evaluation_status == EvaluationStatus.COMPLETE
    assert result.compliance_outcome == ComplianceOutcome.NONCOMPLIANT
    assert result.failed_conditions[0].code == ("TEMPERATURE_ZERO_DRIFT_LIMIT_EXCEEDED")


def test_temperature_order_and_stabilization_are_required():
    ordered = evaluate_temperature(observations=temperature_observations(reverse=True))
    assert ordered.evaluation_status == EvaluationStatus.INCOMPLETE
    assert any(issue.category == "ORDER" for issue in ordered.procedure_issues)

    unstable = evaluate_temperature(observations=temperature_observations(stabilized=False))
    assert unstable.evaluation_status == EvaluationStatus.INCOMPLETE
    assert any(issue.category == "STABILIZATION" for issue in unstable.procedure_issues)


def test_temperature_missing_point_is_incomplete():
    result = evaluate_temperature(observations=temperature_observations(omit_last=True))
    assert result.evaluation_status == EvaluationStatus.INCOMPLETE
    assert result.compliance_outcome == ComplianceOutcome.UNDETERMINED
    assert any(issue.code == "MISSING_REQUIRED_OBSERVATIONS" for issue in result.procedure_issues)


def test_temperature_unverified_procedure_is_regulatory_blocked():
    result = evaluate_temperature(ruleset=temperature_rules(unverified=TEMPERATURE_ZERO_POLICY))
    assert result.evaluation_status == EvaluationStatus.REVIEW_REQUIRED
    assert result.compliance_outcome == ComplianceOutcome.UNDETERMINED
    assert result.issue_code == TODO
    assert TEMPERATURE_ZERO_POLICY in result.unresolved_rule_ids


def test_temperature_declared_range_is_required_when_policy_demands_it():
    result = evaluate_temperature(
        instrument_snapshot=instrument(
            accuracy_class="III",
            zero_tracking_available=True,
        )
    )
    assert result.evaluation_status == EvaluationStatus.INCOMPLETE
    assert any(issue.category == "ENVIRONMENT" for issue in result.procedure_issues)


def test_tilting_no_level_mode_numeric_boundaries_pass():
    result = evaluate_tilting(mode="NO_LEVEL_DEVICE")
    assert result.evaluation_status == EvaluationStatus.COMPLETE
    assert result.compliance_outcome == ComplianceOutcome.COMPLIANT


def test_tilting_numeric_failure_is_noncompliant():
    result = evaluate_tilting(
        mode="NO_LEVEL_DEVICE",
        observations=tilting_observations(
            mode="NO_LEVEL_DEVICE",
            loaded_difference_g="11",
        ),
    )
    assert result.evaluation_status == EvaluationStatus.COMPLETE
    assert result.compliance_outcome == ComplianceOutcome.NONCOMPLIANT
    assert any(item.code == "TILT_MEASUREMENT_LIMIT_EXCEEDED" for item in result.failed_conditions)


@pytest.mark.parametrize(
    "mode",
    [
        "AUTOMATIC_TILT_SENSOR",
        "MOBILE_AUTOMATIC_TILT_SENSOR",
    ],
)
def test_tilting_sensor_modes_enforce_functional_behavior(mode):
    passing = evaluate_tilting(mode=mode)
    assert passing.evaluation_status == EvaluationStatus.COMPLETE
    assert passing.compliance_outcome == ComplianceOutcome.COMPLIANT

    failing = evaluate_tilting(
        mode=mode,
        observations=tilting_observations(
            mode=mode,
            bad_protection=True,
        ),
    )
    assert failing.evaluation_status == EvaluationStatus.COMPLETE
    assert failing.compliance_outcome == ComplianceOutcome.NONCOMPLIANT
    assert any(item.code == "TILT_PROTECTION_BEHAVIOR_FAILED" for item in failing.failed_conditions)


def test_tilting_missing_direction_load_stage_is_incomplete():
    result = evaluate_tilting(observations=tilting_observations(omit_last=True))
    assert result.evaluation_status == EvaluationStatus.INCOMPLETE
    assert any(issue.category in {"COUNT", "LOAD_COVERAGE"} for issue in result.procedure_issues)


def test_tilting_unverified_procedure_is_regulatory_blocked():
    result = evaluate_tilting(ruleset=tilting_rules(unverified=TILTING_POLICY))
    assert result.evaluation_status == EvaluationStatus.REVIEW_REQUIRED
    assert TILTING_POLICY in result.unresolved_rule_ids


def test_warm_up_inclusive_mpe_boundary_passes():
    result = evaluate_warm_up()
    assert result.evaluation_status == EvaluationStatus.COMPLETE
    assert result.compliance_outcome == ComplianceOutcome.COMPLIANT


def test_warm_up_over_mpe_boundary_fails():
    result = evaluate_warm_up(observations=warm_up_observations(error_g="11"))
    assert result.evaluation_status == EvaluationStatus.COMPLETE
    assert result.compliance_outcome == ComplianceOutcome.NONCOMPLIANT
    assert result.failed_conditions[0].code == ("WARM_UP_ERROR_LIMIT_EXCEEDED")


def test_warm_up_requires_power_off_prerequisite():
    result = evaluate_warm_up(procedure_context=warm_up_context(power_off_seconds="99"))
    assert result.evaluation_status == EvaluationStatus.INCOMPLETE
    assert any(issue.category == "TIMING" for issue in result.procedure_issues)


@pytest.mark.parametrize(
    "observations",
    [
        lambda: warm_up_observations(omit_checkpoint=900),
        lambda: warm_up_observations(shift_checkpoint=(900, 906)),
    ],
)
def test_warm_up_missing_or_outside_checkpoint_window_is_incomplete(
    observations,
):
    result = evaluate_warm_up(observations=observations())
    assert result.evaluation_status == EvaluationStatus.INCOMPLETE
    assert any(issue.category in {"COUNT", "TIMING"} for issue in result.procedure_issues)


def test_warm_up_unverified_procedure_is_regulatory_blocked():
    result = evaluate_warm_up(ruleset=warm_up_rules(unverified=WARM_UP_POLICY))
    assert result.evaluation_status == EvaluationStatus.REVIEW_REQUIRED
    assert WARM_UP_POLICY in result.unresolved_rule_ids


@pytest.mark.parametrize(
    "profile",
    tuple(VOLTAGE_PROFILE_DATA),
)
def test_all_voltage_profiles_pass_exact_required_boundaries(profile):
    result = evaluate_voltage(profile=profile)
    assert result.evaluation_status == EvaluationStatus.COMPLETE
    assert result.compliance_outcome == ComplianceOutcome.COMPLIANT


def test_voltage_measurement_over_mpe_is_noncompliant():
    result = evaluate_voltage(
        profile="AC_MAINS",
        observations=voltage_observations(
            profile="AC_MAINS",
            error_g="11",
        ),
    )
    assert result.evaluation_status == EvaluationStatus.COMPLETE
    assert result.compliance_outcome == ComplianceOutcome.NONCOMPLIANT
    assert any(item.code == "VOLTAGE_ERROR_LIMIT_EXCEEDED" for item in result.failed_conditions)


@pytest.mark.parametrize(
    "profile",
    ["BATTERY_NO_CHARGING", "VEHICLE_SUPPLY"],
)
def test_voltage_permitted_switch_off_is_compliant(profile):
    data = VOLTAGE_PROFILE_DATA[profile]
    first_voltage = data["voltages"][0]
    result = evaluate_voltage(
        profile=profile,
        observations=voltage_observations(
            profile=profile,
            switched_off=("100", first_voltage),
        ),
    )
    assert result.evaluation_status == EvaluationStatus.COMPLETE
    assert result.compliance_outcome == ComplianceOutcome.COMPLIANT


def test_voltage_unpermitted_switch_off_is_incomplete():
    result = evaluate_voltage(
        profile="AC_MAINS",
        observations=voltage_observations(
            profile="AC_MAINS",
            switched_off=("100", "200"),
        ),
    )
    assert result.evaluation_status == EvaluationStatus.INCOMPLETE
    assert any(issue.category == "FUNCTIONAL" for issue in result.procedure_issues)


def test_voltage_unexpected_boundary_is_incomplete():
    result = evaluate_voltage(
        profile="AC_MAINS",
        observations=voltage_observations(
            profile="AC_MAINS",
            unexpected_voltage="199",
        ),
    )
    assert result.evaluation_status == EvaluationStatus.INCOMPLETE
    assert any(issue.category == "POWER" for issue in result.procedure_issues)


def test_voltage_unverified_procedure_is_regulatory_blocked():
    result = evaluate_voltage(
        profile="AC_MAINS",
        ruleset=voltage_rules(
            profile="AC_MAINS",
            unverified=VOLTAGE_POLICY,
        ),
    )
    assert result.evaluation_status == EvaluationStatus.REVIEW_REQUIRED
    assert result.issue_code == TODO
    assert VOLTAGE_POLICY in result.unresolved_rule_ids
