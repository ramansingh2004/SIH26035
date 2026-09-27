"""Phase 25 Stage 7 engineering acceptance verifier."""

from __future__ import annotations

import csv
import json
from pathlib import Path

from app.compliance.ruleset import load_ruleset
from app.compliance.stage7_activation import (
    REQUIRED_REGISTERS,
    REQUIRED_SOURCE_IDS,
    VERIFIED_ARTIFACT,
    inspect_verified_artifact,
)

BACKEND = Path(__file__).resolve().parents[1]
REPO = BACKEND.parent
RULE_ROOT = BACKEND / "app" / "compliance" / "rules" / "oiml_r76_2006"
VERIFIED_ROOT = (
    BACKEND / "app" / "compliance" / "rules" / "oiml_r76_2006_verified"
)


def verify_stage7() -> dict[str, object]:
    candidate = load_ruleset()
    readiness = inspect_verified_artifact()

    metadata = json.loads((RULE_ROOT / "metadata.yaml").read_text(encoding="utf-8"))
    assert metadata["version"] == "candidate-v1"
    assert metadata["supported_test_codes"] == []
    assert len(REQUIRED_SOURCE_IDS) == 5
    assert candidate.activation_blockers()

    foundations = (
        BACKEND / "app" / "schemas" / "foundations.py"
    ).read_text(encoding="utf-8")
    rulesets = (
        BACKEND / "app" / "services" / "rulesets.py"
    ).read_text(encoding="utf-8")
    evaluators = (
        BACKEND / "app" / "compliance" / "evaluators.py"
    ).read_text(encoding="utf-8")
    testing = (
        BACKEND / "app" / "services" / "testing.py"
    ).read_text(encoding="utf-8")

    assert VERIFIED_ARTIFACT in foundations
    assert "load_verified_ruleset" in rulesets
    assert "stage7_manifest_hash" in rulesets
    assert "RULESET_NOT_VALIDATED" in rulesets
    assert "default_procedure_schema_version" in testing
    assert "default_observation_schema_version" in testing
    assert "procedure_schema_version: str | None = None" in evaluators
    assert "observation_schema_version: str | None = None" in evaluators

    template = json.loads(
        (
            VERIFIED_ROOT
            / "stage7_verification_manifest.template.json"
        ).read_text(encoding="utf-8")
    )
    assert template["artifact_id"] == VERIFIED_ARTIFACT
    assert template["regulatory_signoff"] is False
    assert {
        row["register_id"]
        for row in template["register_signoffs"]
    } == set(REQUIRED_REGISTERS)
    assert all(
        row["status"] == "PENDING"
        for row in template["register_signoffs"]
    )

    register_path = (
        REPO / "docs" / "regulatory" / "phase25_verification_register.csv"
    )
    with register_path.open(encoding="utf-8", newline="") as handle:
        register_rows = list(csv.DictReader(handle))
    assert len(register_rows) == 17
    assert all(row["status"] != "VERIFIED" for row in register_rows)

    signoff_path = (
        REPO
        / "docs"
        / "regulatory"
        / "phase25_stage7_external_signoff_checklist.csv"
    )
    with signoff_path.open(encoding="utf-8", newline="") as handle:
        signoff_rows = list(csv.DictReader(handle))
    assert signoff_rows
    assert all(row["status"] == "PENDING" for row in signoff_rows)

    required_docs = (
        "PHASE25_STAGE7.md",
        "docs/regulatory/PHASE25_STAGE7_VERIFICATION_AND_ACTIVATION.md",
        "docs/regulatory/PHASE25_STAGE7_FINAL_ACCEPTANCE.md",
        "docs/regulatory/phase25_stage7_activation_matrix.csv",
        "docs/regulatory/phase25_stage7_external_signoff_checklist.csv",
    )
    for relative in required_docs:
        assert (REPO / relative).is_file(), relative

    regulatory_status = (
        "VERIFIED_EXTERNAL_PACKAGE_READY"
        if readiness.ready
        else "PENDING_EXTERNAL_SIGNOFF"
    )
    gate = "READY" if readiness.ready else "BLOCKED"

    return {
        "implementation_status": "COMPLETE",
        "regulatory_verification_status": regulatory_status,
        "verified_artifact_ready": readiness.ready,
        "registration_gate": gate,
        "activation_gate": gate,
        "stage8_authoritative_gate": gate,
        "candidate_hash": readiness.candidate_hash,
        "verified_hash": readiness.verified_hash,
        "manifest_hash": readiness.manifest_hash,
        "blockers": readiness.blockers,
        "required_registers": len(REQUIRED_REGISTERS),
        "pending_external_gates": len(signoff_rows),
    }


def main():
    result = verify_stage7()

    print("Phase 25 Stage 7 engineering verification passed.")
    print(f"Implementation status: {result['implementation_status']}")
    print(
        "Regulatory verification status: "
        f"{result['regulatory_verification_status']}"
    )
    print(f"Verified artifact ready: {result['verified_artifact_ready']}")
    print(f"Registration gate: {result['registration_gate']}")
    print(f"Activation gate: {result['activation_gate']}")
    print(
        "Stage 8 authoritative gate: "
        f"{result['stage8_authoritative_gate']}"
    )
    print(f"Required register signoffs: {result['required_registers']}")
    print(f"Pending external gates: {result['pending_external_gates']}")
    print(f"Candidate configuration hash: {result['candidate_hash']}")
    if result["verified_hash"]:
        print(f"Verified configuration hash: {result['verified_hash']}")
    if result["manifest_hash"]:
        print(f"Verification manifest hash: {result['manifest_hash']}")
    if result["blockers"]:
        print(f"Current blocker count: {len(result['blockers'])}")


if __name__ == "__main__":
    main()
