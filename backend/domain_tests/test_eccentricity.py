"""Pure Section 3 tests; all determined outcomes use isolated synthetic rules only."""

from dataclasses import replace
from decimal import Decimal

import pytest
from pydantic import ValidationError

from app.compliance.eccentricity import (
    CODE,
    EccentricityContext,
    EccentricityObservation,
    section3_registration,
)
from app.compliance.engine import R76Engine
from app.compliance.evaluators import EvaluatorRegistry
from app.compliance.ruleset import load_ruleset
from domain_tests.fixtures.core_reusable import (
    _unverify,
    eccentricity_context,
    eccentricity_observations,
    eccentricity_rules,
    evaluate_eccentricity,
)
from domain_tests.fixtures.synthetic import instrument


def test_eccentricity_verified_synthetic_complete_and_exact_trace():
    result = evaluate_eccentricity()
    assert result.evaluation_status == "COMPLETE"
    assert result.compliance_outcome == "COMPLIANT"
    assert result.synthetic_fixture is True
    assert [point.position_code for point in result.calculations] == ["Q1", "Q2", "Q3", "Q4"]
    assert result.calculations[-1].corrected_error_g == Decimal("10")
    assert result.calculations[-1].mpe_g == Decimal("10")


def test_eccentricity_known_position_failure_is_noncompliant():
    result = evaluate_eccentricity(
        observations=eccentricity_observations(errors=("0", "5", "-5", "11"))
    )
    assert result.evaluation_status == "COMPLETE"
    assert result.compliance_outcome == "NONCOMPLIANT"
    assert result.failed_conditions[-1].code == "ECCENTRICITY_LIMIT_EXCEEDED"


@pytest.mark.parametrize(
    ("rules", "context"),
    [
        (eccentricity_rules(minimum_count=5), eccentricity_context()),
        (
            eccentricity_rules(
                required_positions=[
                    dict(position_code="Q1", rolling_direction=None),
                    dict(position_code="Q2", rolling_direction=None),
                    dict(position_code="Q3", rolling_direction=None),
                    dict(position_code="Q4", rolling_direction=None),
                    dict(position_code="Q5", rolling_direction=None),
                ]
            ),
            eccentricity_context(),
        ),
        (eccentricity_rules(required_support_count=6), eccentricity_context()),
        (
            eccentricity_rules(require_position_coordinates=True),
            eccentricity_context(
                positions=[
                    dict(position_code="Q1"),
                    dict(position_code="Q2", x_mm="1", y_mm="1"),
                    dict(position_code="Q3", x_mm="1", y_mm="-1"),
                    dict(position_code="Q4", x_mm="-1", y_mm="-1"),
                ]
            ),
        ),
        (eccentricity_rules(require_environment=True), eccentricity_context(environment=[])),
        (eccentricity_rules(require_equipment=True), eccentricity_context(equipment=[])),
        (eccentricity_rules(require_evidence=True), eccentricity_context(evidence_hashes=[])),
    ],
)
def test_eccentricity_verified_procedure_requirements_are_enforced(rules, context):
    result = evaluate_eccentricity(ruleset=rules, procedure_context=context)
    assert result.evaluation_status == "INCOMPLETE"
    assert result.compliance_outcome == "UNDETERMINED"
    assert result.procedure_issues


def test_eccentricity_observation_position_must_exist_in_geometry_snapshot():
    batch = eccentricity_observations()
    rows = [row.model_dump(mode="python") for row in batch.rows]
    rows[0]["position_code"] = "UNKNOWN"
    parsed = section3_registration().observations.parse(
        test_code=CODE, protocol="ECCENTRICITY_V1", version="v1", rows=rows
    )
    result = evaluate_eccentricity(observations=parsed)
    assert result.evaluation_status == "INCOMPLETE"
    assert any(issue.category == "GEOMETRY" for issue in result.procedure_issues)


def test_eccentricity_candidate_rules_cannot_produce_authoritative_outcome():
    result = R76Engine(EvaluatorRegistry((section3_registration(),))).evaluate(
        test_code=CODE,
        instrument_snapshot=instrument(
            indication_type="DIGITAL", load_receptor_type="RECTANGULAR", support_point_count=4
        ),
        procedure_context=eccentricity_context(),
        observations=eccentricity_observations(),
        ruleset=load_ruleset(),
    )
    assert result.evaluation_status == "REVIEW_REQUIRED"
    assert result.compliance_outcome == "UNDETERMINED"
    assert result.issue_code == "TODO_REGULATORY_VALIDATION"


@pytest.mark.parametrize("rule_id", ["SECTION3_PROCEDURE", "SECTION3_MPE", "SECTION3_GEOMETRY"])
def test_eccentricity_unverified_dependency_blocks(rule_id):
    result = evaluate_eccentricity(ruleset=_unverify(eccentricity_rules(), rule_id))
    assert result.evaluation_status == "REVIEW_REQUIRED"
    assert rule_id in result.unresolved_rule_ids


@pytest.mark.parametrize("value", [1.2, "NaN", "Infinity", "-Infinity"])
def test_eccentricity_float_and_nonfinite_metrology_rejected(value):
    row = eccentricity_observations().rows[0].model_dump()
    row["load_g"] = value
    with pytest.raises(ValueError):
        EccentricityObservation.model_validate(row)


def test_eccentricity_context_is_closed_frozen_and_position_identity_unique():
    context = eccentricity_context()
    with pytest.raises(ValidationError):
        context.support_count = 9
    with pytest.raises(ValidationError):
        EccentricityContext.model_validate(context.model_dump() | {"invented": True})
    data = context.model_dump()
    data["positions"] = [data["positions"][0], data["positions"][0]]
    with pytest.raises(ValueError, match="Duplicate semantic identifier"):
        EccentricityContext.model_validate(data)


def test_eccentricity_input_and_result_hashes_are_deterministic_and_semantic():
    first = evaluate_eccentricity()
    second = evaluate_eccentricity()
    changed = evaluate_eccentricity(
        observations=eccentricity_observations(errors=("0", "5", "-5", "9"))
    )
    assert first.input_hash == second.input_hash
    assert first.result_hash == second.result_hash
    assert changed.input_hash != first.input_hash
    assert changed.result_hash != first.result_hash


def test_eccentricity_production_registration_is_not_marked_synthetic():
    assert section3_registration().synthetic_fixture is False
    assert replace(section3_registration(), synthetic_fixture=True).synthetic_fixture is True


def test_phase6_rule_model_allows_implemented_flag_without_changing_candidate():
    from app.compliance.ruleset import RuleSet
    from domain_tests.fixtures.core_reusable import repeatability_rules, tare_rules

    for fixture in (eccentricity_rules(), repeatability_rules(), tare_rules()):
        data = fixture.model_dump(mode="json")
        data["tests"][0]["implemented"] = True
        assert RuleSet.model_validate(data).tests[0].implemented is True
    candidate = load_ruleset()
    codes = {"ECCENTRICITY", "REPEATABILITY", "TARE"}
    assert all(not test.implemented for test in candidate.tests if test.code in codes)


def test_eccentricity_rolling_variant_is_typed_and_policy_driven():
    requirements = [
        dict(position_code=code, rolling_direction="FORWARD")
        for code in ("Q1", "Q2", "Q3", "Q4")
    ]
    rules = eccentricity_rules(
        procedure_variant="ROLLING_LOAD",
        required_positions=requirements,
    )
    result = evaluate_eccentricity(
        ruleset=rules,
        procedure_context=eccentricity_context(procedure_variant="ROLLING_LOAD"),
        observations=eccentricity_observations(rolling=True),
    )
    assert result.evaluation_status == "COMPLETE"
    assert result.compliance_outcome == "COMPLIANT"

    rules = eccentricity_rules(
        procedure_variant="ROLLING_LOAD",
        required_positions=requirements
        + [dict(position_code="Q1", rolling_direction="REVERSE")],
    )
    result = evaluate_eccentricity(
        ruleset=rules,
        procedure_context=eccentricity_context(procedure_variant="ROLLING_LOAD"),
        observations=eccentricity_observations(rolling=True),
    )
    assert result.evaluation_status == "INCOMPLETE"
    assert any(issue.category == "GEOMETRY" for issue in result.procedure_issues)
