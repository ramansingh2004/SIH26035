import inspect
import json
from dataclasses import replace

import pytest
from pydantic import ValidationError

from app.compliance.domain import Applicability, ComplianceOutcome, EvaluationStatus
from app.compliance.engine import R76Engine
from app.compliance.evaluators import EvaluatorRegistry
from app.compliance.registries import (
    ContextRegistration,
    ObservationRegistration,
    ObservationSchemaRegistry,
    ProcedureContextRegistry,
)
from app.compliance.regulatory import dependencies
from app.compliance.ruleset import TODO, RuleSet, RuleSetRegistry, load_ruleset
from domain_tests.fixtures.synthetic import (
    CODE,
    FixtureContext,
    FixtureContextV2,
    FixtureObservation,
    FixtureObservationV2,
    context,
    engine,
    evaluate,
    instrument,
    observations,
    registration,
    ruleset,
)


def test_context_registry_versions_and_duplicate_rejection():
    registry = registration().contexts
    assert registry.validate(context()) == context()
    assert isinstance(
        registry.parse(context().model_dump() | {"procedure_schema_version": "v2"}),
        FixtureContextV2,
    )
    with pytest.raises(ValueError, match="Duplicate"):
        ProcedureContextRegistry((registry.registrations[0], registry.registrations[0]))
    for field, value in (
        ("procedure_schema_version", "unknown"),
        ("test_code", "OTHER"),
        ("procedure_variant", "OTHER"),
        ("unknown", "extra"),
    ):
        with pytest.raises(ValueError):
            registry.parse(context().model_dump() | {field: value})
    with pytest.raises(ValueError, match="Duplicate JSON"):
        registry.parse('{"test_code":"A","test_code":"B"}')


def test_observation_registry_versions_order_and_shapes():
    registry = registration().observations
    assert registry.validate(observations()) == observations()
    raw = [r.model_dump() for r in reversed(observations().rows)]
    batch = registry.parse(test_code=CODE, protocol="SYNTHETIC", version="v1", rows=raw)
    assert batch == observations()
    raw2 = [r | {"observation_schema_version": "v2"} for r in raw]
    assert isinstance(
        registry.parse(test_code=CODE, protocol="SYNTHETIC", version="v2", rows=raw2).rows[0],
        FixtureObservationV2,
    )
    for version in ("v3", "unknown"):
        with pytest.raises(ValueError, match="Unknown"):
            registry.parse(test_code=CODE, protocol="SYNTHETIC", version=version, rows=raw)
    for bad_rows in ([raw[0], raw[0]], [raw[0] | {"unknown": 1}], [raw[0], raw2[1]]):
        with pytest.raises(ValueError):
            registry.parse(test_code=CODE, protocol="SYNTHETIC", version="v1", rows=bad_rows)
    with pytest.raises(ValueError, match="Duplicate"):
        ObservationSchemaRegistry((registry.registrations[0], registry.registrations[0]))


def test_evaluator_registry_validation_and_keyword_only_contract():
    reg = registration()
    with pytest.raises(ValueError, match="Duplicate"):
        EvaluatorRegistry((reg, reg))
    with pytest.raises(ValueError, match="Unknown"):
        replace(reg, test_code="IMAGINARY")
    with pytest.raises(ValueError, match="mismatch"):
        replace(reg, test_code="ECCENTRICITY")
    with pytest.raises(ValueError, match="No evaluator"):
        EvaluatorRegistry().resolve(CODE)
    with pytest.raises(ValueError, match="Unknown"):
        EvaluatorRegistry().resolve("UNKNOWN")
    parameters = inspect.signature(R76Engine.evaluate).parameters
    assert tuple(parameters)[1:] == (
        "test_code",
        "instrument_snapshot",
        "procedure_context",
        "observations",
        "ruleset",
    )
    assert all(p.kind == p.KEYWORD_ONLY for name, p in parameters.items() if name != "self")
    with pytest.raises(TypeError):
        engine().evaluate(CODE, instrument(), context(), observations(), ruleset())


@pytest.mark.parametrize(
    "kwargs", [dict(unverified="MPE"), dict(unverified="BASE"), dict(missing_parameter=True)]
)
def test_unverified_transitive_and_null_dependency_gates(kwargs):
    result = evaluate(ruleset=ruleset(**kwargs))
    assert result.evaluation_status == EvaluationStatus.REVIEW_REQUIRED
    assert result.compliance_outcome == ComplianceOutcome.UNDETERMINED
    assert result.issue_code == TODO and result.unresolved_rule_ids
    assert not result.calculations and not result.acceptance_limits


def test_absent_rule_declared_by_evaluator():
    result = engine(extra_dependency="MISSING").evaluate(
        test_code=CODE,
        instrument_snapshot=instrument(),
        procedure_context=context(),
        observations=observations(),
        ruleset=ruleset(),
    )
    assert result.issue_code == TODO and "MISSING" in result.unresolved_rule_ids


def test_unsupported_rule_kind_and_test_declaration():
    data = ruleset().model_dump()
    data["rules"] = list(data["rules"])
    data["rules"][0]["kind"] = "UNSUPPORTED_FUTURE_POLICY"
    assert not dependencies(RuleSet.model_validate(data), ("APP",)).verified
    data = ruleset().model_dump()
    data["metadata"]["supported_test_codes"] = ()
    result = evaluate(ruleset=RuleSet.model_validate(data))
    assert result.issue_code == TODO and CODE + ":UNSUPPORTED_TEST" in result.unresolved_rule_ids


def test_candidate_never_authoritative_and_all_regs_unresolved():
    candidate = load_ruleset()
    for domain_engine in (R76Engine(), engine()):
        result = domain_engine.evaluate(
            test_code=CODE,
            instrument_snapshot=instrument(),
            procedure_context=context(),
            observations=observations(),
            ruleset=candidate,
        )
        assert result.evaluation_status == EvaluationStatus.REVIEW_REQUIRED
        assert result.compliance_outcome == ComplianceOutcome.UNDETERMINED
        assert result.issue_code == TODO and not result.calculations
        assert {f"REG-{i:02}" for i in range(1, 18)} <= set(result.unresolved_rule_ids)
    assert (
        candidate.configuration_hash
        == "e795f71177ad2c0745417d92cd0010b6d895607a3768c3a21bf9bbe283c5a26b"
    )


def test_fixture_isolation_and_production_activation_stays_blocked():
    fixture = ruleset()
    result = evaluate()
    assert result.synthetic_fixture
    assert fixture.activation_blockers() == (CODE + ":NOT_IMPLEMENTED",)
    registry = RuleSetRegistry()
    registry.register(fixture)
    with pytest.raises(ValueError, match="RULESET_NOT_VERIFIED"):
        registry.get("OIML_R76", "TEST-v1", "SYNTHETIC_TEST_V1", authoritative=True)
    production_registration = replace(registration(), synthetic_fixture=False)
    result = R76Engine(EvaluatorRegistry((production_registration,))).evaluate(
        test_code=CODE,
        instrument_snapshot=instrument(),
        procedure_context=context(),
        observations=observations(),
        ruleset=fixture,
    )
    assert result.issue_code == TODO and not result.calculations


@pytest.mark.parametrize(
    "error,operator,outcome",
    [
        ("20", "<=", "NONCOMPLIANT"),
        ("10", "<=", "COMPLIANT"),
        ("10", "<", "NONCOMPLIANT"),
        ("9.9999999999999999999", "<", "COMPLIANT"),
        ("-20", "<=", "NONCOMPLIANT"),
    ],
)
def test_complete_synthetic_procedure_and_metrological_outcome(error, operator, outcome):
    result = evaluate(observations=observations(error=error), ruleset=ruleset(operator=operator))
    assert result.evaluation_status == EvaluationStatus.COMPLETE
    assert result.compliance_outcome == outcome
    assert result.acceptance_limits[0].operator == operator
    assert result.acceptance_limits[0].semantics == "ABSOLUTE"
    assert bool(result.failed_conditions) == (outcome == "NONCOMPLIANT")


@pytest.mark.parametrize(
    "changes,category",
    [
        ({"stages": ("LOAD", "ZERO")}, "STAGE"),
        ({"equipment": ()}, "EQUIPMENT"),
        ({"evidence_hashes": ()}, "EVIDENCE"),
    ],
)
def test_procedure_incomplete_not_a_current_acceptance(changes, category):
    result = evaluate(procedure_context=context(**changes))
    assert result.evaluation_status == EvaluationStatus.INCOMPLETE
    assert result.compliance_outcome == ComplianceOutcome.UNDETERMINED
    assert category in {i.category for i in result.procedure_issues}
    assert not result.calculations


def test_missing_observations_wrong_order_and_timing():
    rows = observations().rows
    empty = evaluate(observations=observations(rows=()))
    assert empty.issue_code == "MISSING_REQUIRED_OBSERVATIONS"
    assert empty.procedure_issues[0].category == "COUNT"
    wrong = (FixtureObservation(**(rows[0].model_dump() | {"stage": "LOAD"})), rows[1])
    assert (
        evaluate(observations=observations(rows=wrong)).evaluation_status
        == EvaluationStatus.INCOMPLETE
    )
    too_soon = (FixtureObservation(**(rows[0].model_dump() | {"elapsed_s": "0"})), rows[1])
    assert "TIMING" in {
        i.category for i in evaluate(observations=observations(rows=too_soon)).procedure_issues
    }
    with pytest.raises(ValidationError):
        FixtureObservation(**(rows[0].model_dump() | {"load_g": "invalid"}))


def test_exact_operation_failure_is_structured():
    result = engine(repeating_division=True).evaluate(
        test_code=CODE,
        instrument_snapshot=instrument(),
        procedure_context=context(),
        observations=observations(),
        ruleset=ruleset(),
    )
    assert result.evaluation_status == EvaluationStatus.INCOMPLETE
    assert result.issue_code == "EVALUATION_NOT_POSSIBLE"
    assert result.compliance_outcome == ComplianceOutcome.UNDETERMINED


def test_unknown_feature_and_explicit_na():
    rs = ruleset(feature="is_electronic")
    result = evaluate(instrument_snapshot=instrument(is_electronic=None), ruleset=rs)
    assert result.evaluation_status == EvaluationStatus.REVIEW_REQUIRED
    assert result.issue_code == "INSTRUMENT_FACTS_REQUIRED"
    result = evaluate(instrument_snapshot=instrument(is_electronic=False), ruleset=rs)
    assert result.evaluation_status == EvaluationStatus.COMPLETE
    assert result.compliance_outcome == ComplianceOutcome.NOT_APPLICABLE
    assert result.applicability.applicability == Applicability.NOT_APPLICABLE


def test_structural_errors_precede_procedure_and_no_range_fallback():
    with pytest.raises(ValueError, match="Selected range"):
        evaluate(procedure_context=context(range_no=99))
    with pytest.raises(TypeError, match="typed immutable"):
        evaluate(instrument_snapshot=instrument().model_dump())
    with pytest.raises(ValueError, match="Unknown"):
        engine().evaluate(
            test_code="UNKNOWN",
            instrument_snapshot=instrument(),
            procedure_context=context(),
            observations=observations(),
            ruleset=ruleset(),
        )


def test_registration_wrong_schema_base_rejected():
    with pytest.raises(ValueError, match="Invalid context"):
        ProcedureContextRegistry(
            (ContextRegistration(CODE, "SYNTHETIC", "v1", FixtureObservation),)
        )
    with pytest.raises(ValueError, match="Invalid observation"):
        ObservationSchemaRegistry(
            (ObservationRegistration(CODE, "SYNTHETIC", "v1", FixtureContext),)
        )


@pytest.mark.parametrize("change", ["schema", "unknown", "overlap", "float", "gap"])
def test_invalid_mpe_policy_cannot_calculate(change, monkeypatch):
    data = ruleset().model_dump()
    parameter = data["rules"][1]["parameters"][0]
    policy = json.loads(parameter["value"])
    if change == "schema":
        policy["schema_version"] = "v999"
    elif change == "unknown":
        policy["hidden_tolerance"] = "0.01"
    elif change == "overlap":
        policy["bands"][1]["lower_operator"] = ">="
    elif change == "float":
        policy["bands"][0]["multiplier_e"] = 1.0
    else:
        policy["bands"][0]["lower_e"] = "1001"
        policy["bands"][0]["upper_e"] = "1002"
        policy["bands"] = policy["bands"][:1]
    parameter["value"] = json.dumps(policy)
    if change != "gap":
        from domain_tests.fixtures.synthetic import SyntheticEvaluator

        def forbidden(**kwargs):
            raise AssertionError("Calculation called before policy validation")

        monkeypatch.setattr(SyntheticEvaluator, "evaluate", staticmethod(forbidden))
    result = evaluate(ruleset=RuleSet.model_validate(data))
    assert result.issue_code == TODO
    assert result.evaluation_status == EvaluationStatus.REVIEW_REQUIRED
    assert result.compliance_outcome == ComplianceOutcome.UNDETERMINED
    assert "MPE" in result.unresolved_rule_ids


def test_missing_policy_schema_registration_is_blocked():
    reg = replace(registration(), policy_schemas=())
    result = R76Engine(EvaluatorRegistry((reg,))).evaluate(
        test_code=CODE,
        instrument_snapshot=instrument(),
        procedure_context=context(),
        observations=observations(),
        ruleset=ruleset(),
    )
    assert result.issue_code == TODO
    assert {"APP", "MPE", "PROCEDURE"} <= set(result.unresolved_rule_ids)


def test_evaluator_implementation_identity_participates_in_hashes():
    original = registration()
    updated = replace(original, implementation_version="synthetic-v2")
    args = dict(
        test_code=CODE,
        instrument_snapshot=instrument(),
        procedure_context=context(),
        observations=observations(),
        ruleset=ruleset(),
    )
    first = R76Engine(EvaluatorRegistry((original,))).evaluate(**args)
    second = R76Engine(EvaluatorRegistry((updated,))).evaluate(**args)
    assert first.engine_version != second.engine_version
    assert first.input_hash != second.input_hash and first.result_hash != second.result_hash
    assert first.calculations == second.calculations
    with pytest.raises(ValueError, match="implementation version"):
        replace(original, implementation_version="")
