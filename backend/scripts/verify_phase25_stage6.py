"""Phase 25 Stage 6 final acceptance verifier."""

from __future__ import annotations

import csv
import json
from pathlib import Path

from app.compliance.candidate_stage6 import load_stage6_candidate

BACKEND = Path(__file__).resolve().parents[1]
REPO = BACKEND.parent
RULE_ROOT = BACKEND / "app" / "compliance" / "rules" / "oiml_r76_2006"
VECTOR_PATH = BACKEND / "tests" / "fixtures" / "phase25_stage6_boundary_vectors.json"


def verify_stage6() -> dict[str, object]:
    candidate = load_stage6_candidate()
    vectors = json.loads(VECTOR_PATH.read_text(encoding="utf-8"))

    assert candidate.verification_status == (
        "SOURCE_MAPPED_PENDING_INDEPENDENT_SIGNOFF"
    )
    assert candidate.activation_allowed is False
    assert candidate.independent_verifier == "PENDING"
    assert set(candidate.register_ids) == {"REG-16", "REG-17"}
    assert len(candidate.reg16) == 4
    assert len(candidate.reg17) == 5
    assert all(source.digest is None for source in candidate.sources)

    source_ids = {source.source_id for source in candidate.sources}
    assert source_ids == {
        "SRC-R76-1-2006-E",
        "SRC-R76-2-2007-E",
        "SRC-INDIA-APPROVAL-MODELS-2011",
        "SRC-INDIA-LM-GENERAL",
        "SRC-INDIA-GATC",
    }

    assert vectors["authority"] == "NON_AUTHORITATIVE_WORKFLOW_BOUNDARY_ONLY"
    assert vectors["review_status"] == "PENDING_INDEPENDENT_REVIEW"
    assert vectors["regulatory_signoff"] is False
    assert len(vectors["vectors"]) == 14
    assert {item["register_id"] for item in vectors["vectors"]} == {
        "REG-16",
        "REG-17",
    }
    assert all(item["authoritative_rule"] is False for item in vectors["vectors"])

    # REG-16 engineering boundaries.
    foundations = (
        BACKEND / "app" / "schemas" / "foundations.py"
    ).read_text(encoding="utf-8")
    testing = (
        BACKEND / "app" / "services" / "testing.py"
    ).read_text(encoding="utf-8")
    approval_snapshot = (
        BACKEND / "app" / "services" / "approval_snapshot.py"
    ).read_text(encoding="utf-8")

    assert 'regulatory_validation_status: Literal["TODO_REGULATORY_VALIDATION"]' in foundations
    assert "Environment row requires at least one measured quantity" in (
        BACKEND / "app" / "schemas" / "testing.py"
    ).read_text(encoding="utf-8")
    assert "retest_of_run_id=original.id" in testing
    assert "Retest selection requires verified REG-16 policy" in testing
    assert "TestRunSelectionEvent(" in testing
    assert "calibration_snapshot(" in testing
    assert "EVIDENCE_PROTECTED" in testing
    for key in (
        '"environment_readings"',
        '"equipment_links"',
        '"evidence"',
        '"selection_events"',
        '"result_events"',
    ):
        assert key in approval_snapshot

    # REG-17 engineering boundaries.
    report = (
        BACKEND / "app" / "services" / "report.py"
    ).read_text(encoding="utf-8")
    report_schema = (
        BACKEND / "app" / "schemas" / "report.py"
    ).read_text(encoding="utf-8")
    phase16_contracts = (
        BACKEND / "tests" / "test_phase16_contracts.py"
    ).read_text(encoding="utf-8")

    assert 'test_session.workflow_status != "APPROVED"' in report
    assert 'test_session.evaluation_status != "COMPLETE"' in report
    assert "snapshot.snapshot_hash != content_hash(snapshot.snapshot_json)" in report
    assert "async def generate(" in report
    assert "async def issue(" in report
    assert "_reg17_issue_gate(snapshot)" in report
    assert '"REG-17"' in report
    assert '"TODO_REGULATORY_VALIDATION"' in report
    assert "Authenticated issuer differs from the generated context" in report
    assert 'pattern=r"^R76-[0-9]{4}-[1-9][0-9]*$"' in report_schema
    assert "Report history is immutable" in phase16_contracts
    assert "Official report requires an approved session" in phase16_contracts

    # Candidate must not be runtime loaded or promoted.
    ruleset_source = (
        BACKEND / "app" / "compliance" / "ruleset.py"
    ).read_text(encoding="utf-8")
    assert "phase25_stage6_candidate.json" not in ruleset_source

    metadata = json.loads((RULE_ROOT / "metadata.yaml").read_text(encoding="utf-8"))
    assert metadata["version"] == "candidate-v1"
    assert metadata["supported_test_codes"] == []

    register = (
        REPO / "docs" / "regulatory" / "phase25_verification_register.csv"
    ).read_text(encoding="utf-8")
    assert "REG-16,Equipment calibration/environment/retest/evidence requirements" in register
    assert "REG-17,Authority report/issue/revision/signature/retention conventions" in register

    required_docs = (
        "PHASE25_STAGE6.md",
        "docs/regulatory/PHASE25_STAGE6_SOURCE_AND_GAP_ANALYSIS.md",
        "docs/regulatory/PHASE25_STAGE6_FINAL_ACCEPTANCE.md",
        "docs/regulatory/phase25_stage6_source_extraction.csv",
        "docs/regulatory/phase25_stage6_reg16_traceability_matrix.csv",
        "docs/regulatory/phase25_stage6_reg17_authority_matrix.csv",
        "docs/regulatory/phase25_stage6_external_signoff_checklist.csv",
    )
    for relative in required_docs:
        assert (REPO / relative).is_file(), relative

    checklist_path = (
        REPO / "docs" / "regulatory" / "phase25_stage6_external_signoff_checklist.csv"
    )
    with checklist_path.open(encoding="utf-8", newline="") as handle:
        gates = list(csv.DictReader(handle))
    assert len(gates) == 11
    assert all(gate["status"] == "PENDING" for gate in gates)

    return {
        "implementation_status": "COMPLETE",
        "regulatory_verification_status": "PENDING_INDEPENDENT_SIGNOFF",
        "activation_allowed": False,
        "reg16_authoritative": "BLOCKED",
        "reg17_authoritative": "BLOCKED",
        "reg16_fact_count": len(candidate.reg16),
        "reg17_fact_count": len(candidate.reg17),
        "boundary_vector_count": len(vectors["vectors"]),
        "candidate_hash": candidate.candidate_hash,
    }


def main():
    result = verify_stage6()

    print("Phase 25 Stage 6 verification passed.")
    print(f"Implementation status: {result['implementation_status']}")
    print(
        "Regulatory verification status: "
        f"{result['regulatory_verification_status']}"
    )
    print(f"Activation allowed: {result['activation_allowed']}")
    print(f"REG-16 authoritative use: {result['reg16_authoritative']}")
    print(f"REG-17 authoritative use: {result['reg17_authoritative']}")
    print(f"REG-16 mapped facts: {result['reg16_fact_count']}")
    print(f"REG-17 mapped facts: {result['reg17_fact_count']}")
    print(f"Boundary vectors: {result['boundary_vector_count']}")
    print(f"Stage 6 candidate hash: {result['candidate_hash']}")


if __name__ == "__main__":
    main()
