"""Phase 25 Stage 2C1 contracts: v2 policy dispatch registration."""

import json
from pathlib import Path

from app.compliance.regulatory import SUPPORTED_KINDS
from app.compliance.suite import implemented_registry

EXPECTED = {
    "WEIGHING_PERFORMANCE": {
        "mpe_profile_v1",
        "mpe_profile_set_v2",
        "weighing_procedure_v1",
        "weighing_procedure_v2",
    },
    "TEMPERATURE_ZERO": {
        "temperature_zero_procedure_v1",
        "temperature_zero_procedure_v2",
    },
    "ECCENTRICITY": {
        "mpe_profile_v1",
        "mpe_profile_set_v2",
        "eccentricity_procedure_v1",
        "eccentricity_procedure_v2",
    },
    "REPEATABILITY": {
        "mpe_profile_v1",
        "mpe_profile_set_v2",
        "repeatability_procedure_v1",
        "repeatability_procedure_v2",
    },
    "DISCRIMINATION": {
        "discrimination_procedure_v1",
        "discrimination_procedure_v2",
    },
    "SENSITIVITY": {
        "sensitivity_procedure_v1",
        "sensitivity_procedure_v2",
    },
}

V2_KINDS = {
    "mpe_profile_set_v2",
    "weighing_procedure_v2",
    "temperature_zero_procedure_v2",
    "eccentricity_procedure_v2",
    "discrimination_procedure_v2",
    "sensitivity_procedure_v2",
    "repeatability_procedure_v2",
}


def test_stage2c1_regulatory_dependency_gate_recognizes_v2_kinds():
    assert V2_KINDS <= set(SUPPORTED_KINDS)


def test_stage2c1_sections_1_to_5_register_v1_and_v2_policy_schemas():
    registry = implemented_registry()
    for code, expected in EXPECTED.items():
        registration = registry.resolve(code)
        kinds = {item.kind for item in registration.policy_schemas}
        assert expected <= kinds


def test_stage2c1_v2_schema_registrations_are_unique():
    registry = implemented_registry()
    for code in EXPECTED:
        registration = registry.resolve(code)
        kinds = [item.kind for item in registration.policy_schemas]
        assert len(kinds) == len(set(kinds))


def test_stage2c1_existing_v1_dispatch_is_preserved():
    registry = implemented_registry()
    expected_v1 = {
        "WEIGHING_PERFORMANCE": "weighing_procedure_v1",
        "TEMPERATURE_ZERO": "temperature_zero_procedure_v1",
        "ECCENTRICITY": "eccentricity_procedure_v1",
        "REPEATABILITY": "repeatability_procedure_v1",
        "DISCRIMINATION": "discrimination_procedure_v1",
        "SENSITIVITY": "sensitivity_procedure_v1",
    }
    for code, kind in expected_v1.items():
        assert kind in {item.kind for item in registry.resolve(code).policy_schemas}


def test_stage2c1_candidate_ruleset_is_still_unpromoted():
    repo = Path(__file__).resolve().parents[2]
    root = repo / "backend" / "app" / "compliance" / "rules" / "oiml_r76_2006"
    metadata = json.loads((root / "metadata.yaml").read_text(encoding="utf-8"))
    mpe = json.loads((root / "mpe.yaml").read_text(encoding="utf-8"))

    assert metadata["version"] == "candidate-v1"
    assert metadata["supported_test_codes"] == []
    assert mpe["rules"][0]["key"] == "MPE_PENDING"
    assert mpe["rules"][0]["parameters"][0]["value"] is None
