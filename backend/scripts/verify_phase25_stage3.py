"""Phase 25 Stage 3 final acceptance verification.

This verification proves implementation-groundwork completeness only.
It deliberately asserts that regulatory verification and activation remain
blocked.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

from app.compliance.candidate_stage3d import load_stage3d_candidate
from app.compliance.phase7 import (
    creep_registration,
    stability_registration,
    zero_return_registration,
)
from app.compliance.phase8 import tilting_registration, warm_up_registration
from app.compliance.tare import section9_registration

BACKEND = Path(__file__).resolve().parents[1]
REPO = BACKEND.parent
RULE_ROOT = BACKEND / "app" / "compliance" / "rules" / "oiml_r76_2006"
VECTOR_PATH = (
    BACKEND / "tests" / "fixtures" / "phase25_stage3e_independent_vectors.json"
)

FAMILIES = {
    "ZERO_RETURN",
    "CREEP",
    "STABILITY_EQUILIBRIUM",
    "TILTING",
    "TARE",
    "WARM_UP",
}
REGISTERS = {"REG-09", "REG-10", "REG-11", "REG-12"}


def _context_keys(registration):
    return {item.key for item in registration.contexts.registrations}


def _observation_keys(registration):
    return {item.key for item in registration.observations.registrations}


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def verify_stage3() -> dict[str, object]:
    candidate = load_stage3d_candidate()
    vectors = json.loads(VECTOR_PATH.read_text(encoding="utf-8"))
    metadata = json.loads(
        (RULE_ROOT / "metadata.yaml").read_text(encoding="utf-8")
    )

    # Source/candidate safety.
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
        register
        for fact in candidate.facts
        for register in fact.register_ids
    } == REGISTERS
    assert all(fact.activation_allowed is False for fact in candidate.facts)
    assert all(
        fact.verification_status
        == "SOURCE_MAPPED_PENDING_INDEPENDENT_SIGNOFF"
        for fact in candidate.facts
    )

    # Runtime candidate remains non-authoritative.
    assert metadata["version"] == "candidate-v1"
    assert metadata["supported_test_codes"] == []

    # Native v2 context/observation registrations exist.
    expected = {
        "ZERO_RETURN": (
            zero_return_registration(),
            {("ZERO_RETURN", "ZERO_RETURN", "v2")},
            {("ZERO_RETURN", "ZERO_RETURN_V2", "v2")},
        ),
        "CREEP": (
            creep_registration(),
            {
                ("CREEP", "SHORT", "v2"),
                ("CREEP", "EXTENDED", "v2"),
            },
            {("CREEP", "CREEP_V2", "v2")},
        ),
        "STABILITY_EQUILIBRIUM": (
            stability_registration(),
            {("STABILITY_EQUILIBRIUM", "FUNCTIONAL", "v2")},
            {
                (
                    "STABILITY_EQUILIBRIUM",
                    "STABILITY_EQUILIBRIUM_V2",
                    "v2",
                )
            },
        ),
        "TILTING": (
            tilting_registration(),
            {
                ("TILTING", "LEVEL_INDICATOR", "v2"),
                ("TILTING", "AUTOMATIC_TILT_SENSOR", "v2"),
                ("TILTING", "NO_LEVEL_DEVICE", "v2"),
                ("TILTING", "MOBILE_AUTOMATIC_TILT_SENSOR", "v2"),
                ("TILTING", "MOBILE_CARDANIC", "v2"),
            },
            {("TILTING", "TILTING_V2", "v2")},
        ),
        "TARE": (
            section9_registration(),
            {("TARE", "DIGITAL_PRE_ROUNDING", "v2")},
            {("TARE", "TARE_V2", "v2")},
        ),
        "WARM_UP": (
            warm_up_registration(),
            {("WARM_UP", "WARM_UP", "v2")},
            {("WARM_UP", "WARM_UP_V2", "v2")},
        ),
    }

    for registration, contexts, observations in expected.values():
        assert contexts <= _context_keys(registration)
        assert observations <= _observation_keys(registration)

    # Mechanics vector preparation is complete but explicitly non-authoritative.
    assert vectors["authority"] == "NON_AUTHORITATIVE_MECHANICS_ONLY"
    assert vectors["review_status"] == "PENDING_INDEPENDENT_REVIEW"
    assert vectors["regulatory_signoff"] is False
    assert len(vectors["vectors"]) == 12
    assert {item["family"] for item in vectors["vectors"]} == FAMILIES
    for family in FAMILIES:
        values = {
            item["expected_passed"]
            for item in vectors["vectors"]
            if item["family"] == family
        }
        assert values == {True, False}

    # The authoritative runtime must still fail closed for v2.
    dispatch_source = (
        BACKEND / "app" / "compliance" / "stage3_dispatch.py"
    ).read_text(encoding="utf-8")
    assert "raise _blocked(ruleset, key)" in dispatch_source

    # Pure mechanics are intentionally not connected to authoritative
    # evaluator modules before regulatory verification.
    for relative in (
        "app/compliance/phase7.py",
        "app/compliance/phase8.py",
        "app/compliance/tare.py",
        "app/compliance/stage3_dispatch.py",
    ):
        source = (BACKEND / relative).read_text(encoding="utf-8")
        assert "stage3_native_mechanics" not in source

    required_stage_docs = (
        "PHASE25_STAGE3.md",
        "docs/regulatory/PHASE25_STAGE3A_SOURCE_TRANSCRIPT.md",
        "docs/regulatory/PHASE25_STAGE3B_PARAMETERIZED_POLICIES.md",
        "docs/regulatory/PHASE25_STAGE3C_COMPLETE.md",
        "docs/regulatory/PHASE25_STAGE3D_NATIVE_SCHEMAS_AND_CANDIDATE.md",
        "docs/regulatory/PHASE25_STAGE3E_NATIVE_MECHANICS_AND_VECTORS.md",
        "docs/regulatory/PHASE25_STAGE3_FINAL_ACCEPTANCE.md",
        "docs/regulatory/phase25_stage3_external_signoff_checklist.csv",
    )
    for relative in required_stage_docs:
        assert (REPO / relative).is_file(), relative

    return {
        "implementation_status": "COMPLETE",
        "regulatory_verification_status": "PENDING_INDEPENDENT_SIGNOFF",
        "activation_allowed": False,
        "families": tuple(sorted(FAMILIES)),
        "registers": tuple(sorted(REGISTERS)),
        "candidate_hash": candidate.candidate_hash,
        "vector_file_sha256": _sha256(VECTOR_PATH),
        "vector_count": len(vectors["vectors"]),
        "runtime_v2_authoritative_execution": "BLOCKED",
    }


def main():
    result = verify_stage3()
    print("Phase 25 Stage 3 verification passed.")
    print(f"Implementation status: {result['implementation_status']}")
    print(
        "Regulatory verification status: "
        f"{result['regulatory_verification_status']}"
    )
    print(f"Activation allowed: {result['activation_allowed']}")
    print(
        "Native-v2 authoritative runtime: "
        f"{result['runtime_v2_authoritative_execution']}"
    )
    print(f"Stage 3 families: {len(result['families'])}")
    print(f"Stage 3 candidate hash: {result['candidate_hash']}")
    print(f"Stage 3 vector file SHA-256: {result['vector_file_sha256']}")
    print(f"Stage 3 vectors: {result['vector_count']}")


if __name__ == "__main__":
    main()
