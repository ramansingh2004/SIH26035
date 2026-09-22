"""Production Section 1 mechanics tested only against labelled synthetic policy."""

from decimal import Decimal, localcontext

import pytest
from pydantic import ValidationError

from app.compliance.canonical import normalize
from app.compliance.engine import R76Engine
from app.compliance.ruleset import RuleSet, load_ruleset
from app.compliance.weighing import CODE, WeighingContext, WeighingObservation, section1_registry
from domain_tests.fixtures.synthetic import instrument
from domain_tests.fixtures.weighing import (
    evaluate,
    fixture_context,
    fixture_observations,
    fixture_rules,
)


def test_golden_section1_trace_and_candidate_isolation():
    result = evaluate()
    point = result.calculations[0]
    assert (point.prerounding_indication_g, point.error_g, point.corrected_error_g) == (
        Decimal("10020"),
        Decimal("20"),
        Decimal("20"),
    )
    assert result.evaluation_status == "COMPLETE"
    assert result.compliance_outcome == "NONCOMPLIANT"
    assert result.synthetic_fixture
    assert normalize(result)["calculations"][0]["sequence_no"] == 1
    assert result.model_dump(mode="json")["calculations"][0]["mpe_g"] == "10"


@pytest.mark.parametrize(
    "error,outcome",
    [
        ("10", "COMPLIANT"),
        ("10.000000000001", "NONCOMPLIANT"),
        ("-10", "COMPLIANT"),
        ("-10.00001", "NONCOMPLIANT"),
    ],
)
def test_exact_boundary(error, outcome):
    with localcontext() as context:
        context.prec = 2
        assert evaluate(observations=fixture_observations(error)).compliance_outcome == outcome


@pytest.mark.parametrize(
    "change",
    [
        dict(preloaded=False),
        dict(stabilized=None),
        dict(warmed_up_seconds="0"),
        dict(stages=["DOWN", "UP"]),
        dict(zero_condition="OTHER"),
        dict(environment=[]),
        dict(equipment=[]),
        dict(evidence_hashes=[]),
    ],
)
def test_procedure_incomplete_is_not_acceptance(change):
    result = evaluate(procedure_context=fixture_context(**change))
    assert result.evaluation_status == "INCOMPLETE"
    assert result.compliance_outcome == "UNDETERMINED"
    assert not result.calculations
    assert result.procedure_issues


@pytest.mark.parametrize(
    "policy",
    [
        dict(minimum_count=3),
        dict(require_max=True),
        dict(transition_loads=[dict(direction="UP", load_g="5000")]),
        dict(require_certificate=True),
        dict(temperature_min_c="21", temperature_max_c="25"),
        dict(range_type="MULTI"),
    ],
)
def test_complete_procedure_requirements_come_from_policy(policy):
    assert evaluate(ruleset=fixture_rules(**policy)).evaluation_status == "INCOMPLETE"


@pytest.mark.parametrize(
    "key",
    [
        "SECTION1_PROCEDURE",
        "SECTION1_MPE",
        "SECTION1_CLASSIFICATION",
        "SECTION1_CALIBRATION",
        "BASE",
    ],
)
def test_missing_or_unverified_dependency(key):
    data = fixture_rules().model_dump(mode="json")
    for rule in data["rules"]:
        if rule["key"] == key:
            rule["verification"] = {}
    result = evaluate(ruleset=RuleSet.model_validate(data))
    assert result.evaluation_status == "REVIEW_REQUIRED"
    assert result.compliance_outcome == "UNDETERMINED"
    assert result.issue_code == "TODO_REGULATORY_VALIDATION"
    assert key in result.unresolved_rule_ids


def test_candidate_and_production_registration_cannot_use_synthetic_authority():
    for rules in (load_ruleset(), fixture_rules()):
        result = R76Engine(section1_registry()).evaluate(
            test_code=CODE,
            instrument_snapshot=instrument(indication_type="DIGITAL"),
            procedure_context=fixture_context(),
            observations=fixture_observations(),
            ruleset=rules,
        )
        assert result.evaluation_status == "REVIEW_REQUIRED"
        assert result.compliance_outcome == "UNDETERMINED"


@pytest.mark.parametrize("value", [1.2, "NaN", "Infinity", "-Infinity"])
def test_float_and_nonfinite_rejected(value):
    data = fixture_observations().rows[0].model_dump()
    data["load_g"] = value
    with pytest.raises(ValueError):
        WeighingObservation.model_validate(data)


def test_context_unknown_fields_and_immutability():
    context = fixture_context()
    with pytest.raises(ValidationError):
        context.preloaded = False
    with pytest.raises(ValidationError):
        WeighingContext.model_validate(context.model_dump() | {"invented": True})


def test_missing_selected_range_is_structural():
    with pytest.raises(ValueError, match="range"):
        evaluate(procedure_context=fixture_context(range_no=2))


def test_deterministic_results_and_evidence_hash_changes():
    first = evaluate()
    assert first.result_hash == evaluate().result_hash
    changed = evaluate(procedure_context=fixture_context(evidence_hashes=["c" * 64]))
    assert changed.input_hash != first.input_hash


def test_missing_observations_and_order():
    batch = fixture_observations()
    empty = type(batch).model_validate(batch.model_dump() | {"rows": []})
    assert evaluate(observations=empty).issue_code == "MISSING_REQUIRED_OBSERVATIONS"
    rows = [r.model_dump() for r in reversed(batch.rows)]
    for index, row in enumerate(rows, 1):
        row["sequence_no"] = index
    from app.compliance.weighing import section1_registration

    wrong = section1_registration().observations.parse(
        test_code=CODE, protocol="WEIGHING_V1", version="v1", rows=rows
    )
    assert evaluate(observations=wrong).evaluation_status == "INCOMPLETE"


def test_multi_range_uses_selected_interval_without_top_level_fallback():
    base = instrument(indication_type="DIGITAL").model_dump()
    first = base["ranges"][0]
    second = first | {"range_no": 2, "max_capacity_g": "40000", "verification_interval_e_g": "20"}
    from app.compliance.domain import InstrumentSnapshot

    snapshot = InstrumentSnapshot.model_validate(
        base
        | {
            "range_type": "MULTIPLE",
            "max_capacity_g": "40000",
            "verification_intervals_n": "4000",
            "ranges": [second, first],
        }
    )
    result = evaluate(
        instrument_snapshot=snapshot,
        procedure_context=fixture_context(range_no=2),
        ruleset=fixture_rules(range_type="MULTIPLE"),
    )
    assert result.evaluation_status == "COMPLETE"
    assert result.calculations[0].range_no == 2
    assert result.calculations[0].corrected_error_g == Decimal("25")
    assert result.calculations[0].mpe_g == Decimal("20")


def test_verified_mpe_profile_that_does_not_cover_class_is_review_required():
    result = evaluate(
        instrument_snapshot=instrument(indication_type="DIGITAL", accuracy_class="II")
    )
    assert result.evaluation_status == "REVIEW_REQUIRED"
    assert result.issue_code == "TODO_REGULATORY_VALIDATION"
    assert "SECTION1_MPE" in result.unresolved_rule_ids


def test_applicability_can_resolve_before_later_acceptance_dependency():
    from app.compliance.applicability import ApplicabilityEngine

    data = fixture_rules().model_dump(mode="json")
    for rule in data["rules"]:
        if rule["key"] == "SECTION1_MPE":
            rule["verification"] = {}
    rules = RuleSet.model_validate(data)
    decision = ApplicabilityEngine().determine(
        test_code=CODE,
        instrument_snapshot=instrument(),
        ruleset=rules,
        range_no=1,
        scenario="fixture",
        procedure_variant="DIGITAL_PRE_ROUNDING",
    )
    assert decision.applicability == "REQUIRED"
    assert evaluate(ruleset=rules).evaluation_status == "REVIEW_REQUIRED"


@pytest.mark.parametrize("value", [1.25, 10, "1000"])
def test_measurement_timestamp_cannot_originate_from_a_numeric_epoch(value):
    data = fixture_observations().rows[0].model_dump()
    with pytest.raises(ValidationError):
        WeighingObservation.model_validate(data | {"measured_at": value})
