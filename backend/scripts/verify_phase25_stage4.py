"""Phase 25 Stage 4 final acceptance verifier.

This verifies implementation-groundwork completeness only. It deliberately
asserts that regulatory verification and authoritative activation remain
pending.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

from app.compliance.candidate_stage4b import load_stage4b_candidate
from app.compliance.phase8 import voltage_variation_registration
from app.compliance.phase9 import damp_heat_registration, span_stability_registration
from app.compliance.phase10 import disturbance_registrations
from app.compliance.phase11 import endurance_registration
from app.compliance.regulatory import SUPPORTED_KINDS

BACKEND = Path(__file__).resolve().parents[1]
REPO = BACKEND.parent
RULE_ROOT = BACKEND / "app" / "compliance" / "rules" / "oiml_r76_2006"
VECTOR_PATH = (
    BACKEND / "tests" / "fixtures" / "phase25_stage4b_mechanics_vectors.json"
)

FAMILIES = {
    "VOLTAGE_VARIATION",
    "ELECTRICAL_DISTURBANCES",
    "DAMP_HEAT",
    "SPAN_STABILITY",
    "ENDURANCE",
}
REGISTERS = {"REG-12", "REG-13", "REG-14"}
V2_KINDS = {
    "voltage_variation_procedure_v2",
    "disturbance_procedure_v2",
    "damp_heat_procedure_v2",
    "span_stability_procedure_v2",
    "endurance_procedure_v2",
}


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _context_keys(registration):
    return {item.key for item in registration.contexts.registrations}


def _observation_keys(registration):
    return {item.key for item in registration.observations.registrations}


def _policy_kinds(registration):
    return {item.kind for item in registration.policy_schemas}


def verify_stage4() -> dict[str, object]:
    candidate = load_stage4b_candidate()
    vectors = json.loads(VECTOR_PATH.read_text(encoding="utf-8"))
    metadata = json.loads(
        (RULE_ROOT / "metadata.yaml").read_text(encoding="utf-8")
    )

    assert candidate.verification_status == (
        "SOURCE_MAPPED_PENDING_INDEPENDENT_SIGNOFF"
    )
    assert candidate.activation_allowed is False
    assert candidate.independent_verifier == "PENDING"
    assert all(source.digest is None for source in candidate.sources)
    assert all(
        source.acquisition_status == "PENDING_CONTROLLED_ACQUISITION"
        for source in candidate.sources
    )
    assert {fact.family for fact in candidate.facts} == FAMILIES
    assert {
        register_id
        for fact in candidate.facts
        for register_id in fact.register_ids
    } == REGISTERS
    assert all(fact.activation_allowed is False for fact in candidate.facts)
    assert all(
        fact.verification_status
        == "SOURCE_MAPPED_PENDING_INDEPENDENT_SIGNOFF"
        for fact in candidate.facts
    )

    assert V2_KINDS <= set(SUPPORTED_KINDS)

    voltage = voltage_variation_registration()
    assert any(key[2] == "v2" for key in _context_keys(voltage))
    assert (
        "VOLTAGE_VARIATION",
        "VOLTAGE_VARIATION_V2",
        "v2",
    ) in _observation_keys(voltage)
    assert "voltage_variation_procedure_v2" in _policy_kinds(voltage)

    disturbances = disturbance_registrations()
    assert len(disturbances) == 7
    for registration in disturbances:
        assert any(key[2] == "v2" for key in _context_keys(registration))
        assert (
            registration.test_code,
            "DISTURBANCE_V2",
            "v2",
        ) in _observation_keys(registration)
        assert "disturbance_procedure_v2" in _policy_kinds(registration)

    damp = damp_heat_registration()
    span = span_stability_registration()
    endurance = endurance_registration()

    assert ("DAMP_HEAT", "STEADY_STATE", "v2") in _context_keys(damp)
    assert ("DAMP_HEAT", "DAMP_HEAT_V2", "v2") in _observation_keys(damp)
    assert "damp_heat_procedure_v2" in _policy_kinds(damp)

    assert ("SPAN_STABILITY", "LONG_DURATION", "v2") in _context_keys(span)
    assert (
        "SPAN_STABILITY",
        "SPAN_STABILITY_V2",
        "v2",
    ) in _observation_keys(span)
    assert "span_stability_procedure_v2" in _policy_kinds(span)

    assert (
        "ENDURANCE",
        "MECHANICAL_CYCLING",
        "v2",
    ) in _context_keys(endurance)
    assert ("ENDURANCE", "ENDURANCE_V2", "v2") in _observation_keys(endurance)
    assert "endurance_procedure_v2" in _policy_kinds(endurance)

    assert vectors["authority"] == "NON_AUTHORITATIVE_MECHANICS_ONLY"
    assert vectors["review_status"] == "PENDING_INDEPENDENT_REVIEW"
    assert vectors["regulatory_signoff"] is False
    assert len(vectors["vectors"]) == 10
    assert {item["family"] for item in vectors["vectors"]} == FAMILIES
    for family in FAMILIES:
        assert {
            item["expected_passed"]
            for item in vectors["vectors"]
            if item["family"] == family
        } == {True, False}

    dispatch_source = (
        BACKEND / "app" / "compliance" / "stage4_dispatch.py"
    ).read_text(encoding="utf-8")
    assert "raise _blocked(ruleset, key)" in dispatch_source

    for relative in (
        "app/compliance/phase8.py",
        "app/compliance/phase9.py",
        "app/compliance/phase10.py",
        "app/compliance/phase11.py",
    ):
        source = (BACKEND / relative).read_text(encoding="utf-8")
        assert "stage4_native_mechanics" not in source

    ruleset_source = (
        BACKEND / "app" / "compliance" / "ruleset.py"
    ).read_text(encoding="utf-8")
    assert "phase25_stage4b_candidate.json" not in ruleset_source

    assert metadata["version"] == "candidate-v1"
    assert metadata["supported_test_codes"] == []

    required_docs = (
        "PHASE25_STAGE4.md",
        "docs/regulatory/PHASE25_STAGE4A_SOURCE_TRANSCRIPT.md",
        "docs/regulatory/PHASE25_STAGE4B_CONTRACTS_MECHANICS_CANDIDATE.md",
        "docs/regulatory/PHASE25_STAGE4_FINAL_ACCEPTANCE.md",
        "docs/regulatory/phase25_stage4a_source_extraction.csv",
        "docs/regulatory/phase25_stage4a_engine_gap_matrix.csv",
        "docs/regulatory/phase25_stage4b_candidate_ledger.csv",
        "docs/regulatory/phase25_stage4_external_signoff_checklist.csv",
    )
    for relative in required_docs:
        assert (REPO / relative).is_file(), relative

    return {
        "implementation_status": "COMPLETE",
        "regulatory_verification_status": "PENDING_INDEPENDENT_SIGNOFF",
        "activation_allowed": False,
        "native_v2_authoritative_runtime": "BLOCKED",
        "families": tuple(sorted(FAMILIES)),
        "registers": tuple(sorted(REGISTERS)),
        "candidate_hash": candidate.candidate_hash,
        "vector_file_sha256": _sha256(VECTOR_PATH),
        "vector_count": len(vectors["vectors"]),
        "disturbance_family_count": len(disturbances),
    }


def main():
    result = verify_stage4()

    print("Phase 25 Stage 4 verification passed.")
    print(f"Implementation status: {result['implementation_status']}")
    print(
        "Regulatory verification status: "
        f"{result['regulatory_verification_status']}"
    )
    print(f"Activation allowed: {result['activation_allowed']}")
    print(
        "Native-v2 authoritative runtime: "
        f"{result['native_v2_authoritative_runtime']}"
    )
    print(f"Stage 4 top-level families: {len(result['families'])}")
    print(
        "Electrical-disturbance subfamilies: "
        f"{result['disturbance_family_count']}"
    )
    print(f"Stage 4 candidate hash: {result['candidate_hash']}")
    print(f"Stage 4 vector file SHA-256: {result['vector_file_sha256']}")
    print(f"Stage 4 vectors: {result['vector_count']}")


if __name__ == "__main__":
    main()
