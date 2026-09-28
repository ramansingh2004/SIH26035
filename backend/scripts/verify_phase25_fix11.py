"""Offline verifier for Phase 25 Fix 11 engineering wiring."""

from __future__ import annotations

import json

from app.compliance.ruleset import load_ruleset
from app.compliance.runtime_binding import runtime_binding_options
from app.compliance.suite import implemented_registry
from app.compliance.verified_blueprint import (
    V1_ONLY_PROCEDURE_RULES,
    executable_rule_blueprint,
)

EXPECTED = {
    "VOLTAGE_VARIATION": (
        "SECTION11_VOLTAGE_PROCEDURE",
        "voltage_variation_procedure_v2",
        "section11-fix11-v2",
    ),
    "DAMP_HEAT": (
        "SECTION13_DAMP_HEAT_PROCEDURE",
        "damp_heat_procedure_v2",
        "section13-fix11-v2",
    ),
    "SPAN_STABILITY": (
        "SECTION14_SPAN_STABILITY_PROCEDURE",
        "span_stability_procedure_v2",
        "section14-fix11-v2",
    ),
    "ENDURANCE": (
        "SECTION15_ENDURANCE_PROCEDURE",
        "endurance_procedure_v2",
        "section15-fix11-v2",
    ),
}


def verify_fix11():
    candidate = load_ruleset()
    registry = implemented_registry()
    blueprint = {
        item.rule_key: item
        for item in executable_rule_blueprint(candidate)
    }

    if V1_ONLY_PROCEDURE_RULES:
        raise RuntimeError(
            "Fix 11 expected the Stage-4 v1-only restriction set to be empty"
        )

    rows = {}
    for test_code, (rule_key, v2_kind, version) in EXPECTED.items():
        registration = registry.resolve(test_code)
        if registration.implementation_version != version:
            raise RuntimeError(
                f"{test_code}: implementation version mismatch"
            )
        if v2_kind not in blueprint[rule_key].allowed_kinds:
            raise RuntimeError(
                f"{rule_key}: v2 policy kind is not reviewable/executable"
            )
        options = runtime_binding_options(registration)
        v2 = [
            item
            for item in options
            if item["procedure_schema_version"] == "v2"
            and item["observation_schema_version"] == "v2"
        ]
        if len(v2) != 1:
            raise RuntimeError(
                f"{test_code}: expected exactly one v2/v2 runtime binding"
            )
        rows[test_code] = {
            "implementation_version": registration.implementation_version,
            "v2_policy_kind": v2_kind,
            "v2_runtime_binding_sha256": v2[0]["runtime_binding_sha256"],
        }

    if candidate.metadata.version != "candidate-v1":
        raise RuntimeError("Fix 11 must not promote candidate-v1")
    if candidate.metadata.supported_test_codes:
        raise RuntimeError("Fix 11 must not activate candidate supported tests")

    return {
        "fix": "PHASE25_FIX11_STAGE4_NATIVE_V2_RUNTIME",
        "engineering_status": "READY_FOR_TEST_AND_REVIEW_REEXPORT",
        "candidate_activation_changed": False,
        "database_migration_added": False,
        "registrations": rows,
    }


def main():
    print(json.dumps(verify_fix11(), indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
