"""Phase 25 Fix 11 contracts — Stage 4 native-v2 verified runtime."""

from app.compliance.ruleset import load_ruleset
from app.compliance.runtime_binding import runtime_binding_options
from app.compliance.stage4_verified_runtime import (
    VerifiedDampHeatPolicyV2,
    VerifiedEnduranceContextV2,
    VerifiedEndurancePolicyV2,
    VerifiedSpanStabilityContextV2,
    VerifiedSpanStabilityPolicyV2,
    VerifiedVoltageVariationPolicyV2,
)
from app.compliance.suite import implemented_registry
from app.compliance.verified_blueprint import (
    V1_ONLY_PROCEDURE_RULES,
    executable_rule_blueprint,
)

FIX11 = {
    "VOLTAGE_VARIATION": (
        "SECTION11_VOLTAGE_PROCEDURE",
        "voltage_variation_procedure_v2",
        VerifiedVoltageVariationPolicyV2,
        "section11-fix11-v2",
    ),
    "DAMP_HEAT": (
        "SECTION13_DAMP_HEAT_PROCEDURE",
        "damp_heat_procedure_v2",
        VerifiedDampHeatPolicyV2,
        "section13-fix11-v2",
    ),
    "SPAN_STABILITY": (
        "SECTION14_SPAN_STABILITY_PROCEDURE",
        "span_stability_procedure_v2",
        VerifiedSpanStabilityPolicyV2,
        "section14-fix11-v2",
    ),
    "ENDURANCE": (
        "SECTION15_ENDURANCE_PROCEDURE",
        "endurance_procedure_v2",
        VerifiedEndurancePolicyV2,
        "section15-fix11-v2",
    ),
}


def test_fix11_removes_four_v1_only_blueprint_restrictions():
    assert V1_ONLY_PROCEDURE_RULES == frozenset()

    candidate = load_ruleset()
    blueprint = {
        item.rule_key: item
        for item in executable_rule_blueprint(candidate)
    }
    for _, (rule_key, v2_kind, _, _) in FIX11.items():
        assert v2_kind in blueprint[rule_key].allowed_kinds


def test_fix11_registry_uses_refined_v2_policy_schemas_and_new_versions():
    registry = implemented_registry()
    for test_code, (_, v2_kind, expected_schema, expected_version) in FIX11.items():
        registration = registry.resolve(test_code)
        policies = {item.kind: item.schema for item in registration.policy_schemas}
        assert policies[v2_kind] is expected_schema
        assert registration.implementation_version == expected_version


def test_fix11_all_four_registrations_publish_a_v2_v2_runtime_binding():
    registry = implemented_registry()
    for test_code in FIX11:
        options = runtime_binding_options(registry.resolve(test_code))
        assert any(
            item["procedure_schema_version"] == "v2"
            and item["observation_schema_version"] == "v2"
            for item in options
        )


def test_fix11_span_and_endurance_v2_contexts_capture_runtime_confirmation_facts():
    registry = implemented_registry()

    span_schema = registry.resolve("SPAN_STABILITY").contexts.resolve(
        "SPAN_STABILITY",
        "LONG_DURATION",
        "v2",
    )
    assert span_schema is VerifiedSpanStabilityContextV2
    assert {
        "test_load_near_max_confirmed",
        "builtin_span_adjustment_present",
        "damp_heat_applicable",
        "endurance_test_performed_during_span",
        "trend_detected",
    } <= set(span_schema.model_fields)

    endurance_schema = registry.resolve("ENDURANCE").contexts.resolve(
        "ENDURANCE",
        "MECHANICAL_CYCLING",
        "v2",
    )
    assert endurance_schema is VerifiedEnduranceContextV2
    assert {
        "cycling_load_approximation_confirmed",
        "pre_post_weighing_procedure_confirmed",
    } <= set(endurance_schema.model_fields)


def test_fix11_refined_voltage_policy_can_express_relative_source_native_targets():
    policy = VerifiedVoltageVariationPolicyV2.model_validate(
        {
            "schema_version": "v2",
            "evaluation_context": "TYPE_EXAMINATION",
            "profiles": [
                {
                    "power_supply_profile": "AC_MAINS",
                    "required_voltage_targets": [
                        {
                            "target_id": "LOW",
                            "source": "DECLARED_MIN_OR_NOMINAL_MULTIPLIER",
                            "value": "0.85",
                        },
                        {
                            "target_id": "HIGH",
                            "source": "DECLARED_MAX_OR_NOMINAL_MULTIPLIER",
                            "value": "1.10",
                        },
                    ],
                    "required_loads": [
                        {
                            "load_id": "TEN_E",
                            "source": "E_MULTIPLE",
                            "value": "10",
                            "required_distinct_loads": 1,
                        },
                        {
                            "load_id": "HALF_TO_MAX",
                            "source": "MAX_FRACTION_INTERVAL",
                            "minimum_fraction_of_max": "0.5",
                            "maximum_fraction_of_max": "1",
                            "required_distinct_loads": 1,
                        },
                    ],
                    "allow_switch_off": False,
                    "require_functions_operational_when_indicating": True,
                    "successive_phase_application_required": True,
                    "indication_limit_basis": "MPE",
                    "indication_limit_multiplier": "1",
                    "indication_operator": "<=",
                    "indication_semantics": "ABSOLUTE",
                }
            ],
            "require_environment": True,
            "require_equipment": True,
            "require_certificate": True,
            "require_evidence": True,
            "require_monotonic_timestamps": True,
        }
    )
    assert policy.profiles[0].required_loads[0].source == "E_MULTIPLE"


def test_fix11_candidate_ruleset_remains_non_authoritative():
    candidate = load_ruleset()
    assert candidate.metadata.version == "candidate-v1"
    assert not candidate.metadata.supported_test_codes
