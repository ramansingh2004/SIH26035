"""Phase 25 Stage 4C final acceptance contracts."""

import json
from pathlib import Path

from scripts.verify_phase25_stage4 import verify_stage4

REPO = Path(__file__).resolve().parents[2]


def test_stage4c_verifier_closes_implementation_not_regulatory_verification():
    result = verify_stage4()

    assert result["implementation_status"] == "COMPLETE"
    assert result["regulatory_verification_status"] == (
        "PENDING_INDEPENDENT_SIGNOFF"
    )
    assert result["activation_allowed"] is False
    assert result["native_v2_authoritative_runtime"] == "BLOCKED"


def test_stage4c_covers_sections_11_to_15_top_level_families():
    result = verify_stage4()

    assert set(result["families"]) == {
        "VOLTAGE_VARIATION",
        "ELECTRICAL_DISTURBANCES",
        "DAMP_HEAT",
        "SPAN_STABILITY",
        "ENDURANCE",
    }


def test_stage4c_covers_reg12_reg13_reg14():
    result = verify_stage4()

    assert set(result["registers"]) == {
        "REG-12",
        "REG-13",
        "REG-14",
    }


def test_stage4c_covers_all_seven_section12_disturbance_subfamilies():
    result = verify_stage4()

    assert result["disturbance_family_count"] == 7


def test_stage4c_candidate_and_vectors_are_content_addressable():
    result = verify_stage4()

    assert len(result["candidate_hash"]) == 64
    assert len(result["vector_file_sha256"]) == 64
    assert result["vector_count"] == 10


def test_stage4c_stage_document_separates_implementation_from_verification():
    text = (REPO / "PHASE25_STAGE4.md").read_text(encoding="utf-8")

    assert "STAGE 4 IMPLEMENTATION WORK = COMPLETE" in text
    assert "REGULATORY VERIFICATION = COMPLETE" in text
    assert "does **not** mean" in text
    assert "supported_test_codes` remains empty" in text


def test_stage4c_external_signoff_checklist_has_only_pending_gates():
    path = (
        REPO
        / "docs"
        / "regulatory"
        / "phase25_stage4_external_signoff_checklist.csv"
    )
    rows = path.read_text(encoding="utf-8").splitlines()

    assert len(rows) == 8
    assert all(
        ",PENDING," in line or line.startswith("gate_id,")
        for line in rows
    )


def test_stage4c_runtime_candidate_remains_unactivated():
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


def test_stage4c_final_acceptance_does_not_promote_candidate_rules():
    text = (
        REPO
        / "docs"
        / "regulatory"
        / "PHASE25_STAGE4_FINAL_ACCEPTANCE.md"
    ).read_text(encoding="utf-8")

    assert "No Stage 4 rule is promoted to `VERIFIED`" in text
    assert "authoritative native-v2 runtime remains blocked" in text
