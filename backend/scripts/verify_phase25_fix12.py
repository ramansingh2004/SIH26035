"""Offline engineering verifier for Phase 25 Fix 12."""

from __future__ import annotations

import json

from app.compliance.ruleset import load_ruleset
from app.compliance.runtime_binding import runtime_binding_options
from app.compliance.suite import implemented_registry
from app.compliance.verified_blueprint import executable_rule_blueprint

EXPECTED = {
    "WEIGHING_PERFORMANCE": (
        "SECTION1_PROCEDURE",
        "weighing_procedure_v2",
        "section1-fix12-v2",
    ),
    "TEMPERATURE_ZERO": (
        "SECTION2_TEMPERATURE_ZERO_PROCEDURE",
        "temperature_zero_procedure_v2",
        "section2-fix12-v2",
    ),
    "ECCENTRICITY": (
        "SECTION3_PROCEDURE",
        "eccentricity_procedure_v2",
        "section3-fix12-v2",
    ),
    "DISCRIMINATION": (
        "SECTION4_DISCRIMINATION_PROCEDURE",
        "discrimination_procedure_v2",
        "section4-discrimination-fix12-v2",
    ),
    "SENSITIVITY": (
        "SECTION4_SENSITIVITY_PROCEDURE",
        "sensitivity_procedure_v2",
        "section4-sensitivity-fix12-v2",
    ),
    "REPEATABILITY": (
        "SECTION5_PROCEDURE",
        "repeatability_procedure_v2",
        "section5-fix12-v2",
    ),
    "TILTING": (
        "SECTION8_TILTING_PROCEDURE",
        "tilting_procedure_v2",
        "section8-fix12-v2",
    ),
}


def verify_fix12():
    candidate = load_ruleset()
    registry = implemented_registry()
    blueprint = {
        item.rule_key: item
        for item in executable_rule_blueprint(candidate)
    }

    output = {}
    for test_code, (rule_key, kind, version) in EXPECTED.items():
        registration = registry.resolve(test_code)
        if registration.implementation_version != version:
            raise RuntimeError(f"{test_code}: implementation-version mismatch")
        if kind not in blueprint[rule_key].allowed_kinds:
            raise RuntimeError(f"{rule_key}: v2 policy kind not exported")
        schemas = {
            item.kind: item.schema
            for item in registration.policy_schemas
        }
        if kind not in schemas:
            raise RuntimeError(f"{test_code}: v2 policy schema not registered")
        output[test_code] = {
            "implementation_version": version,
            "policy_kind": kind,
            "runtime_bindings": runtime_binding_options(registration),
        }

    weighing_schema = {
        item.kind: item.schema
        for item in registry.resolve("WEIGHING_PERFORMANCE").policy_schemas
    }["weighing_procedure_v2"].model_json_schema()
    schema_text = json.dumps(weighing_schema, sort_keys=True)
    for token in ("numeric_conditions", "MIN_CAPACITY_E", "MAX_CAPACITY_G"):
        if token not in schema_text:
            raise RuntimeError(f"Fix-12 selector token missing: {token}")

    eccentricity_schema = {
        item.kind: item.schema
        for item in registry.resolve("ECCENTRICITY").policy_schemas
    }["eccentricity_procedure_v2"].model_json_schema()
    if "required_rolling_directions" not in json.dumps(
        eccentricity_schema,
        sort_keys=True,
    ):
        raise RuntimeError("Rolling-load direction contract is not exported")

    tilting_schema = {
        item.kind: item.schema
        for item in registry.resolve("TILTING").policy_schemas
    }["tilting_procedure_v2"].model_json_schema()
    tilting_text = json.dumps(tilting_schema, sort_keys=True)
    for field in (
        "unloaded_operator",
        "unloaded_semantics",
        "is_portable",
        "load_receptor_types",
    ):
        if field not in tilting_text:
            raise RuntimeError(f"Tilting schema missing Fix-12 field: {field}")

    if candidate.metadata.version != "candidate-v1":
        raise RuntimeError("Fix 12 must not promote candidate-v1")
    if candidate.metadata.supported_test_codes:
        raise RuntimeError("Fix 12 must not activate candidate tests")

    return {
        "fix": "PHASE25_FIX12_POLICY_CLOSURE",
        "engineering_status": "READY_FOR_TEST_AND_REVIEW_REEXPORT",
        "candidate_activation_changed": False,
        "database_migration_added": False,
        "affected_evaluators": output,
        "review_note": (
            "Fix 12 closes representation/runtime gaps only; "
            "it does not independently verify regulatory values."
        ),
    }


def main():
    print(json.dumps(verify_fix12(), indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
