"""Pure Section 9 tests; determined outcomes use synthetic verified policies only."""

from decimal import Decimal

import pytest
from pydantic import ValidationError

from app.compliance.engine import R76Engine
from app.compliance.evaluators import EvaluatorRegistry
from app.compliance.ruleset import load_ruleset
from app.compliance.tare import CODE, TareContext, TareObservation, section9_registration
from domain_tests.fixtures.core_reusable import (
    _unverify,
    evaluate_tare,
    tare_context,
    tare_observations,
    tare_rules,
)
from domain_tests.fixtures.synthetic import instrument


def test_tare_complete_synthetic_trace_uses_net_load_for_error_and_mpe():
    result = evaluate_tare()
    assert result.evaluation_status == "COMPLETE"
    assert result.compliance_outcome == "COMPLIANT"
    first = result.calculations[0]
    assert first.net_load_g == Decimal("1000")
    assert first.gross_load_g == Decimal("2000")
    assert first.corrected_error_g == Decimal("0")
    assert first.mpe_g == Decimal("10")


def test_tare_required_point_failure_is_complete_noncompliant():
    result = evaluate_tare(observations=tare_observations(errors=("0", "11", "5", "0")))
    assert result.evaluation_status == "COMPLETE"
    assert result.compliance_outcome == "NONCOMPLIANT"
    assert any(f.code == "TARE_LIMIT_EXCEEDED" for f in result.failed_conditions)


@pytest.mark.parametrize(
    ("rules", "context", "maximum_tare_g"),
    [
        (tare_rules(), tare_context(stabilized=False), "5000"),
        (tare_rules(require_environment=True), tare_context(environment=[]), "5000"),
        (tare_rules(require_equipment=True), tare_context(equipment=[]), "5000"),
        (tare_rules(require_evidence=True), tare_context(evidence_hashes=[]), "5000"),
        (tare_rules(require_declared_tare_capacity=True), tare_context(), None),
    ],
)
def test_tare_verified_prerequisites_enforced(rules, context, maximum_tare_g):
    snapshot = instrument(
        indication_type="DIGITAL",
        tare_type="SUBTRACTIVE",
        maximum_tare_g=maximum_tare_g,
    )
    result = evaluate_tare(
        ruleset=rules, procedure_context=context, instrument_snapshot=snapshot
    )
    assert result.evaluation_status == "INCOMPLETE"
    assert result.compliance_outcome == "UNDETERMINED"


def test_tare_missing_required_load_is_incomplete():
    batch = tare_observations()
    rows = [row.model_dump(mode="python") for row in batch.rows[:-1]]
    parsed = section9_registration().observations.parse(
        test_code=CODE, protocol="TARE_V1", version="v1", rows=rows
    )
    result = evaluate_tare(observations=parsed)
    assert result.evaluation_status == "INCOMPLETE"
    assert any(issue.category in {"COUNT", "LOAD_COVERAGE"} for issue in result.procedure_issues)


def test_tare_inconsistent_gross_net_tare_relation_is_incomplete():
    batch = tare_observations()
    rows = [row.model_dump(mode="python") for row in batch.rows]
    rows[0]["gross_load_g"] = "9999"
    parsed = section9_registration().observations.parse(
        test_code=CODE, protocol="TARE_V1", version="v1", rows=rows
    )
    result = evaluate_tare(observations=parsed)
    assert result.evaluation_status == "INCOMPLETE"
    assert any("Gross load" in issue.reason for issue in result.procedure_issues)


def test_tare_context_and_policy_scenario_identity_must_match():
    context = tare_context(
        tare_scenarios=[dict(scenario_code="OTHER", tare_type="SUBTRACTIVE", tare_value_g="1000")]
    )
    result = evaluate_tare(procedure_context=context)
    assert result.evaluation_status == "INCOMPLETE"
    assert result.compliance_outcome == "UNDETERMINED"


def test_tare_candidate_rules_remain_review_required():
    result = R76Engine(EvaluatorRegistry((section9_registration(),))).evaluate(
        test_code=CODE,
        instrument_snapshot=instrument(
            indication_type="DIGITAL", tare_type="SUBTRACTIVE", maximum_tare_g="5000"
        ),
        procedure_context=tare_context(),
        observations=tare_observations(),
        ruleset=load_ruleset(),
    )
    assert result.evaluation_status == "REVIEW_REQUIRED"
    assert result.compliance_outcome == "UNDETERMINED"


@pytest.mark.parametrize("rule_id", ["SECTION9_PROCEDURE", "SECTION9_MPE", "SECTION9_TARE_MODE"])
def test_tare_unverified_dependency_blocks(rule_id):
    result = evaluate_tare(ruleset=_unverify(tare_rules(), rule_id))
    assert result.evaluation_status == "REVIEW_REQUIRED"
    assert rule_id in result.unresolved_rule_ids


@pytest.mark.parametrize("value", [1.5, "NaN", "Infinity", "-Infinity"])
def test_tare_float_and_nonfinite_rejected(value):
    row = tare_observations().rows[0].model_dump()
    row["tare_value_g"] = value
    with pytest.raises(ValueError):
        TareObservation.model_validate(row)


def test_tare_context_closed_frozen_and_hashes_are_deterministic():
    context = tare_context()
    with pytest.raises(ValidationError):
        context.stabilized = False
    with pytest.raises(ValidationError):
        TareContext.model_validate(context.model_dump() | {"invented": True})
    first = evaluate_tare()
    second = evaluate_tare()
    changed = evaluate_tare(observations=tare_observations(errors=("0", "9", "5", "0")))
    assert first.input_hash == second.input_hash
    assert first.result_hash == second.result_hash
    assert changed.input_hash != first.input_hash
    assert changed.result_hash != first.result_hash


def test_tare_supports_multiple_verified_scenarios_in_one_run():
    scenarios = [
        dict(
            scenario_code="T1",
            tare_type="SUBTRACTIVE",
            tare_value_g="1000",
            minimum_count=4,
            stages=["UP", "DOWN"],
            required_net_loads_g=["1000", "5000"],
        ),
        dict(
            scenario_code="T2",
            tare_type="PRESET",
            tare_value_g="2000",
            minimum_count=4,
            stages=["UP", "DOWN"],
            required_net_loads_g=["1000", "5000"],
        ),
    ]
    context = tare_context(
        tare_scenarios=[
            dict(scenario_code="T1", tare_type="SUBTRACTIVE", tare_value_g="1000"),
            dict(scenario_code="T2", tare_type="PRESET", tare_value_g="2000"),
        ]
    )
    base = [row.model_dump(mode="python") for row in tare_observations().rows]
    rows = list(base)
    for index, row in enumerate(base, 5):
        copy = row | {
            "sequence_no": index,
            "tare_scenario_code": "T2",
            "tare_type": "PRESET",
            "tare_value_g": "2000",
            "gross_load_g": str(int(row["net_load_g"]) + 2000),
            "measured_at": f"2000-01-01T00:00:{index:02d}Z",
        }
        rows.append(copy)
    observations = section9_registration().observations.parse(
        test_code=CODE,
        protocol="TARE_V1",
        version="v1",
        rows=rows,
    )
    result = evaluate_tare(
        ruleset=tare_rules(scenarios=scenarios),
        procedure_context=context,
        observations=observations,
    )
    assert result.evaluation_status == "COMPLETE"
    assert result.compliance_outcome == "COMPLIANT"
    assert {point.tare_scenario_code for point in result.calculations} == {"T1", "T2"}
