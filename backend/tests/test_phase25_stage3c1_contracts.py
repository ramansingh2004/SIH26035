"""Phase 25 Stage 3C1 registration contracts."""

import inspect
import json
from pathlib import Path

from app.compliance.phase7 import (
    CreepEvaluator,
    StabilityEvaluator,
    ZeroReturnEvaluator,
    creep_registration,
    stability_registration,
    zero_return_registration,
)
from app.compliance.phase8 import (
    TiltingEvaluator,
    _tilting_policy,
    WarmUpEvaluator,
    tilting_registration,
    warm_up_registration,
)
from app.compliance.regulatory import SUPPORTED_KINDS
from app.compliance.tare import TareEvaluator, section9_registration

REPO = Path(__file__).resolve().parents[2]

EXPECTED_V2_KINDS = {
    "zero_return_procedure_v2",
    "creep_procedure_v2",
    "stability_equilibrium_procedure_v2",
    "tilting_procedure_v2",
    "tare_procedure_v2",
    "warm_up_procedure_v2",
}


def _kinds(registration):
    return {item.kind for item in registration.policy_schemas}


def test_stage3c1_dependency_gate_recognizes_sections_6_to_10_v2_kinds():
    assert EXPECTED_V2_KINDS <= set(SUPPORTED_KINDS)


def test_stage3c1_section6_and_7_registrations_advertise_v1_and_v2():
    assert {
        "zero_return_procedure_v1",
        "zero_return_procedure_v2",
    } <= _kinds(zero_return_registration())

    assert {
        "creep_procedure_v1",
        "creep_procedure_v2",
        "mpe_profile_set_v2",
    } <= _kinds(creep_registration())

    assert {
        "stability_equilibrium_procedure_v1",
        "stability_equilibrium_procedure_v2",
    } <= _kinds(stability_registration())


def test_stage3c1_sections_8_to_10_registrations_advertise_v1_and_v2():
    assert {
        "tilting_procedure_v1",
        "tilting_procedure_v2",
        "mpe_profile_v1",
        "mpe_profile_set_v2",
    } <= _kinds(tilting_registration())

    assert {
        "tare_procedure_v1",
        "tare_procedure_v2",
        "mpe_profile_v1",
        "mpe_profile_set_v2",
    } <= _kinds(section9_registration())

    assert {
        "warm_up_procedure_v1",
        "warm_up_procedure_v2",
        "mpe_profile_v1",
        "mpe_profile_set_v2",
    } <= _kinds(warm_up_registration())


def test_stage3c1_runtime_execution_keeps_legacy_paths_and_tilting_dispatch():
    checks = (
        (ZeroReturnEvaluator.validate_procedure, "zero_return_procedure_v1"),
        (CreepEvaluator.validate_procedure, "creep_procedure_v1"),
        (
            StabilityEvaluator.validate_procedure,
            "stability_equilibrium_procedure_v1",
        ),
        (TareEvaluator.validate_procedure, "tare_procedure_v1"),
        (WarmUpEvaluator.validate_procedure, "warm_up_procedure_v1"),
    )

    for method, expected_kind in checks:
        assert expected_kind in inspect.getsource(method)

    assert "_tilting_policy" in inspect.getsource(
        TiltingEvaluator.validate_procedure
    )
    assert "rule_policy_variant" in inspect.getsource(_tilting_policy)


def test_stage3c1_candidate_ruleset_remains_unpromoted():
    root = (
        REPO
        / "backend"
        / "app"
        / "compliance"
        / "rules"
        / "oiml_r76_2006"
    )
    metadata = json.loads((root / "metadata.yaml").read_text(encoding="utf-8"))
    mpe = json.loads((root / "mpe.yaml").read_text(encoding="utf-8"))

    assert metadata["version"] == "candidate-v1"
    assert metadata["supported_test_codes"] == []
    assert mpe["rules"][0]["key"] == "MPE_PENDING"
    assert mpe["rules"][0]["parameters"][0]["value"] is None
