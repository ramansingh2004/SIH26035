"""Phase 25 Stage 6 one-step final acceptance contracts."""

import csv
import json
from pathlib import Path

from app.compliance.candidate_stage6 import load_stage6_candidate
from scripts.verify_phase25_stage6 import verify_stage6

REPO = Path(__file__).resolve().parents[2]
VECTOR_PATH = (
    Path(__file__).resolve().parent
    / "fixtures"
    / "phase25_stage6_boundary_vectors.json"
)


def test_stage6_candidate_is_non_authoritative():
    candidate = load_stage6_candidate()

    assert candidate.verification_status == (
        "SOURCE_MAPPED_PENDING_INDEPENDENT_SIGNOFF"
    )
    assert candidate.activation_allowed is False
    assert candidate.independent_verifier == "PENDING"
    assert set(candidate.register_ids) == {"REG-16", "REG-17"}
    assert all(source.digest is None for source in candidate.sources)


def test_stage6_reg16_has_four_traceability_topics():
    candidate = load_stage6_candidate()

    assert {item["topic"] for item in candidate.reg16} == {
        "test_standards_and_calibration",
        "environmental_conditions",
        "retest_and_authoritative_run_selection",
        "evidence_identity_and_immutability",
    }


def test_stage6_reg17_has_five_authority_topics():
    candidate = load_stage6_candidate()

    assert {item["topic"] for item in candidate.reg17} == {
        "oiml_report_format",
        "generation_vs_issue",
        "report_number_and_revision_lineage",
        "issuer_signature_and_authority",
        "retention_and_immutability",
    }


def test_stage6_sources_keep_oiml_and_india_authority_mapping_separate():
    candidate = load_stage6_candidate()
    by_id = {source.source_id: source for source in candidate.sources}

    assert by_id["SRC-R76-1-2006-E"].status == "PENDING_CONTROLLED_ACQUISITION"
    assert by_id["SRC-R76-2-2007-E"].status == "PENDING_CONTROLLED_ACQUISITION"
    assert by_id["SRC-INDIA-APPROVAL-MODELS-2011"].status == (
        "NATIONAL_MAPPING_PENDING_EXPERT_REVIEW"
    )
    assert by_id["SRC-INDIA-GATC"].status == "AUTHORITY_SCOPE_MAPPING_PENDING"


def test_stage6_boundary_vectors_are_non_authoritative():
    data = json.loads(VECTOR_PATH.read_text(encoding="utf-8"))

    assert data["authority"] == "NON_AUTHORITATIVE_WORKFLOW_BOUNDARY_ONLY"
    assert data["review_status"] == "PENDING_INDEPENDENT_REVIEW"
    assert data["regulatory_signoff"] is False
    assert len(data["vectors"]) == 14
    assert all(item["authoritative_rule"] is False for item in data["vectors"])


def test_stage6_runtime_candidate_remains_unpromoted():
    root = (
        REPO
        / "backend"
        / "app"
        / "compliance"
        / "rules"
        / "oiml_r76_2006"
    )
    metadata = json.loads((root / "metadata.yaml").read_text(encoding="utf-8"))
    ruleset_source = (
        REPO / "backend" / "app" / "compliance" / "ruleset.py"
    ).read_text(encoding="utf-8")

    assert metadata["version"] == "candidate-v1"
    assert metadata["supported_test_codes"] == []
    assert "phase25_stage6_candidate.json" not in ruleset_source


def test_stage6_document_separates_implementation_from_verification():
    text = (REPO / "PHASE25_STAGE6.md").read_text(encoding="utf-8")

    assert "STAGE 6 IMPLEMENTATION WORK = COMPLETE" in text
    assert "does **not** mean" in text
    assert "REG-16 / REG-17 REGULATORY VERIFICATION = COMPLETE" in text
    assert "No Stage 6 candidate fact is promoted to `VERIFIED`" in text


def test_stage6_final_acceptance_does_not_claim_legal_signature_or_retention():
    text = (
        REPO
        / "docs"
        / "regulatory"
        / "PHASE25_STAGE6_FINAL_ACCEPTANCE.md"
    ).read_text(encoding="utf-8")

    assert "No software identity/role is claimed to substitute" in text
    assert "No statutory retention period is asserted" in text
    assert "No project report-number format is claimed as an official Indian convention" in text


def test_stage6_external_signoff_gates_are_all_pending():
    path = (
        REPO
        / "docs"
        / "regulatory"
        / "phase25_stage6_external_signoff_checklist.csv"
    )
    with path.open(encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle))

    assert len(rows) == 11
    assert all(row["status"] == "PENDING" for row in rows)


def test_stage6_verifier_reports_safe_final_boundary():
    result = verify_stage6()

    assert result["implementation_status"] == "COMPLETE"
    assert result["regulatory_verification_status"] == (
        "PENDING_INDEPENDENT_SIGNOFF"
    )
    assert result["activation_allowed"] is False
    assert result["reg16_authoritative"] == "BLOCKED"
    assert result["reg17_authoritative"] == "BLOCKED"
    assert result["reg16_fact_count"] == 4
    assert result["reg17_fact_count"] == 5
    assert result["boundary_vector_count"] == 14
    assert len(result["candidate_hash"]) == 64
