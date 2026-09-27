"""Phase 25 Fix 6: policy-driven standard-weight substitution contracts."""

import json

from app.compliance.ruleset import RuleSet
from app.compliance.weighing import CODE, POLICY, WeighingContextV2, section1_registration
from domain_tests.fixtures.synthetic import instrument
from domain_tests.fixtures.weighing import fixture_engine, fixture_observations, fixture_rules


def rules(*, reductions=None):
    if reductions is None:
        reductions = [
            {
                "max_repeatability_error_multiplier_e": "0.3",
                "minimum_standard_weight_fraction": {"numerator": 1, "denominator": 3},
            },
            {
                "max_repeatability_error_multiplier_e": "0.2",
                "minimum_standard_weight_fraction": {"numerator": 1, "denominator": 5},
            },
        ]

    data = fixture_rules().model_dump(mode="json")
    policy = {
        "schema_version": "v2",
        "cases": [
            {
                "selector": {
                    "accuracy_classes": ["III"],
                    "evaluation_contexts": ["SYNTHETIC"],
                    "indication_types": ["DIGITAL"],
                    "range_types": ["SINGLE"],
                },
                "minimum_count": 2,
                "stages": ["UP", "DOWN"],
                "required_loads": [
                    {"direction": "UP", "load": {"basis": "ABSOLUTE_G", "value": "10000"}},
                    {"direction": "DOWN", "load": {"basis": "ABSOLUTE_G", "value": "0"}},
                ],
                "transition_loads": [],
                "require_min": False,
                "require_max": False,
                "require_preload": True,
                "require_stabilization": True,
                "minimum_warmup_seconds": "1",
                "zero_condition": "SYNTHETIC_ZERO",
                "require_environment": True,
                "temperature_min_c": "15",
                "temperature_max_c": "25",
                "humidity_min_percent": None,
                "humidity_max_percent": None,
                "require_equipment": True,
                "require_certificate": False,
                "require_evidence": True,
                "require_monotonic_timestamps": True,
                "standard_weight_substitution": {
                    "applicable_testing_location": "PLACE_OF_USE",
                    "capacity_basis": "INSTRUMENT_MAX",
                    "base_minimum_standard_weight_fraction": {"numerator": 1, "denominator": 2},
                    "repeatability_reductions": reductions,
                    "repeatability_placements": 3,
                    "standard_weight_categories": ["STANDARD_WEIGHT"],
                    "require_repeatability_load_approximation_confirmation": True,
                    "require_total_load_coverage": True,
                    "require_evidence": True,
                },
            }
        ],
    }
    target = next(item for item in data["rules"] if item["key"] == POLICY)
    target["kind"] = "weighing_procedure_v2"
    target["parameters"] = [{"name": "POLICY_JSON", "value": json.dumps(policy)}]
    return RuleSet.model_validate(data)


def observations_v2():
    rows = []
    for item in fixture_observations().rows:
        value = item.model_dump(mode="json")
        value["protocol"] = "WEIGHING_V2"
        value["observation_schema_version"] = "v2"
        rows.append(value)
    return section1_registration().observations.parse(
        test_code=CODE,
        protocol="WEIGHING_V2",
        version="v2",
        rows=rows,
    )


def context(
    *,
    standard_mass="10000",
    constant_mass="10000",
    indications=None,
    location="PLACE_OF_USE",
    substitution_used=True,
    include_record=True,
    approximation=True,
):
    equipment = [
        {
            "reference": "STD-1",
            "category": "STANDARD_WEIGHT",
            "nominal_mass_g": standard_mass,
        }
    ]
    record = None
    if include_record:
        repeatability = (
            None
            if indications is None
            else {
                "substitution_point_g": "10000",
                "repeatability_load_g": "10000",
                "approximately_at_substitution_point": approximation,
                "indications_g": indications,
            }
        )
        record = {
            "constant_load_substitution_used": substitution_used,
            "standard_weight_references": ["STD-1"],
            "constant_load_mass_g": constant_mass if substitution_used else None,
            "repeatability": repeatability if substitution_used else None,
        }

    return WeighingContextV2.model_validate(
        {
            "evaluation_context": "SYNTHETIC",
            "range_no": 1,
            "scenario": "fixture",
            "stages": ["UP", "DOWN"],
            "preloaded": True,
            "warmed_up_seconds": "2",
            "stabilized": True,
            "zero_condition": "SYNTHETIC_ZERO",
            "environment": [
                {"measured_at": "2000-01-01T00:00:00Z", "temperature_c": "20"}
            ],
            "equipment": equipment,
            "evidence_hashes": ["b" * 64],
            "testing_location": location,
            "standard_weight_substitution": record,
        }
    )


def evaluate(**changes):
    arguments = {
        "test_code": CODE,
        "instrument_snapshot": instrument(indication_type="DIGITAL"),
        "procedure_context": context(),
        "observations": observations_v2(),
        "ruleset": rules(),
    }
    arguments.update(changes)
    return fixture_engine().evaluate(**arguments)


def test_base_fraction_allows_substitution_without_repeatability_reduction():
    assert evaluate().evaluation_status == "COMPLETE"


def test_exact_one_third_comparison_uses_rational_cross_multiplication():
    result = evaluate(
        procedure_context=context(
            standard_mass="6667",
            constant_mass="13333",
            indications=["10000", "10003", "10001"],
        )
    )
    assert result.evaluation_status == "COMPLETE"

    too_little = evaluate(
        procedure_context=context(
            standard_mass="6666",
            constant_mass="13334",
            indications=["10000", "10003", "10001"],
        )
    )
    assert too_little.evaluation_status == "INCOMPLETE"
    assert any("minimum fraction" in item.reason for item in too_little.procedure_issues)


def test_stricter_repeatability_can_select_smaller_verified_fraction():
    result = evaluate(
        procedure_context=context(
            standard_mass="4000",
            constant_mass="16000",
            indications=["10000", "10002", "10001"],
        )
    )
    assert result.evaluation_status == "COMPLETE"


def test_repeatability_threshold_boundary_is_exact():
    result = evaluate(
        procedure_context=context(
            standard_mass="6667",
            constant_mass="13333",
            indications=["10000", "10003.0001", "10001"],
        )
    )
    assert result.evaluation_status == "INCOMPLETE"


def test_verified_placement_count_and_approximation_are_required_for_reduction():
    count = evaluate(
        procedure_context=context(
            standard_mass="6667",
            constant_mass="13333",
            indications=["10000", "10003"],
        )
    )
    assert count.evaluation_status == "INCOMPLETE"

    approximation = evaluate(
        procedure_context=context(
            standard_mass="6667",
            constant_mass="13333",
            indications=["10000", "10003", "10001"],
            approximation=False,
        )
    )
    assert approximation.evaluation_status == "INCOMPLETE"


def test_unknown_testing_location_fails_closed_but_other_location_skips_policy():
    missing = evaluate(procedure_context=context(location=None, include_record=False))
    assert missing.evaluation_status == "INCOMPLETE"

    other = evaluate(
        procedure_context=context(location="MANUFACTURE", include_record=False)
    )
    assert other.evaluation_status == "COMPLETE"


def test_no_substitution_requires_full_standard_weight_capacity():
    full = evaluate(
        procedure_context=context(
            standard_mass="20000",
            constant_mass=None,
            substitution_used=False,
        )
    )
    assert full.evaluation_status == "COMPLETE"

    short = evaluate(
        procedure_context=context(
            standard_mass="19999",
            constant_mass=None,
            substitution_used=False,
        )
    )
    assert short.evaluation_status == "INCOMPLETE"
