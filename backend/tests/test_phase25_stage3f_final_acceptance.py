"""Phase 25 Stage 3F final acceptance contracts."""

import json
from pathlib import Path

from scripts.verify_phase25_stage3 import verify_stage3

REPO = Path(__file__).resolve().parents[2]


def test_stage3f_verifier_reports_complete_implementation_but_pending_signoff():
    result = verify_stage3()

    assert result["implementation_status"] == "COMPLETE"
    assert result["regulatory_verification_status"] == (
        "PENDING_INDEPENDENT_SIGNOFF"
    )
    assert result["activation_allowed"] is False
    assert result["runtime_v2_authoritative_execution"] == "BLOCKED"


def test_stage3f_verifier_covers_all_six_stage3_families():
    result = verify_stage3()

    assert set(result["families"]) == {
        "ZERO_RETURN",
        "CREEP",
        "STABILITY_EQUILIBRIUM",
        "TILTING",
        "TARE",
        "WARM_UP",
    }


def test_stage3f_verifier_covers_reg09_through_reg12():
    result = verify_stage3()

    assert set(result["registers"]) == {
        "REG-09",
        "REG-10",
        "REG-11",
        "REG-12",
    }


def test_stage3f_candidate_and_vector_artifacts_are_content_addressable():
    result = verify_stage3()

    assert len(result["candidate_hash"]) == 64
    assert len(result["vector_file_sha256"]) == 64
    assert result["vector_count"] == 12


def test_stage3f_final_stage_document_separates_implementation_from_verification():
    text = (REPO / "PHASE25_STAGE3.md").read_text(encoding="utf-8")

    assert "STAGE 3 IMPLEMENTATION WORK = COMPLETE" in text
    assert "REGULATORY VERIFICATION = COMPLETE" in text
    assert "does **not** mean" in text
    assert "supported_test_codes` remains empty" in text


def test_stage3f_external_signoff_checklist_has_no_completed_external_gate():
    path = (
        REPO
        / "docs"
        / "regulatory"
        / "phase25_stage3_external_signoff_checklist.csv"
    )
    rows = path.read_text(encoding="utf-8").splitlines()

    assert len(rows) == 9
    assert all(
        ",PENDING," in line or line.startswith("gate_id,")
        for line in rows
    )


def test_stage3f_runtime_candidate_is_still_unactivated():
    root = (
        REPO
        / "backend"
        / "app"
        / "compliance"
        / "rules"
        / "oiml_r76_2006"
    )
    metadata = json.loads((root / "metadata.yaml").read_text(encoding="utf-8"))

    assert metadata["version"] == "candidate-v1"
    assert metadata["supported_test_codes"] == []


def test_stage3f_is_final_acceptance_only_not_runtime_promotion():
    final_doc = (
        REPO
        / "docs"
        / "regulatory"
        / "PHASE25_STAGE3_FINAL_ACCEPTANCE.md"
    ).read_text(encoding="utf-8")

    assert "No rule is promoted to `VERIFIED`" in final_doc
    assert "authoritative runtime remains blocked" in final_doc
