"""Phase 25 Stage 5 one-step final acceptance contracts."""

import csv
import json
from pathlib import Path

from app.compliance.candidate_stage5 import load_stage5_candidate
from app.compliance.catalog import CHECKLIST_DOMAINS
from app.compliance.ruleset import load_ruleset
from scripts.verify_phase25_stage5 import verify_stage5

REPO = Path(__file__).resolve().parents[2]


def test_stage5_candidate_is_non_authoritative():
    candidate = load_stage5_candidate()

    assert candidate.verification_status == (
        "SOURCE_MAPPED_PENDING_INDEPENDENT_SIGNOFF"
    )
    assert candidate.activation_allowed is False
    assert candidate.independent_verifier == "PENDING"
    assert candidate.register_ids == ("REG-15",)
    assert all(source.digest is None for source in candidate.sources)


def test_stage5_section16_maps_all_existing_internal_capture_categories():
    candidate = load_stage5_candidate()

    assert {
        item["category"]
        for item in candidate.section16["internal_capture_categories"]
    } == {
        "GENERAL",
        "RECEPTOR_LOAD_CELLS",
        "INDICATOR_DISPLAY",
        "PRINTER_PERIPHERALS",
        "POWER_INTERFACES",
        "TILT_ZERO_TARE",
        "SEALS_SECURITY_SOFTWARE",
        "DOCUMENTS_PHOTOS",
    }


def test_stage5_section17_mapping_matches_project_checklist_domains():
    candidate = load_stage5_candidate()
    expected = {
        f"{group}_{domain}"
        for group, domains in CHECKLIST_DOMAINS.items()
        for domain in domains
    }

    mapped = {item["key"] for item in candidate.section17["domains"]}
    assert mapped == expected
    assert len(mapped) == 27


def test_stage5_section17_preserves_four_report_groups():
    candidate = load_stage5_candidate()

    assert candidate.section17["groups"] == {
        "GENERAL": "17.1",
        "DIRECT_SALES": "17.2",
        "ELECTRONIC": "17.3",
        "SOFTWARE_CONTROLLED": "17.4",
    }


def test_stage5_preserves_non_self_indicating_replacement_branch():
    candidate = load_stage5_candidate()

    branch = candidate.section17["principles"]["non_self_indicating_branch"]
    assert "R76-1 clause 6" in branch
    assert "in lieu of" in branch


def test_stage5_runtime_ruleset_remains_unpromoted():
    ruleset = load_ruleset()
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
    assert not any(rule.kind == "construction_item_v1" for rule in ruleset.rules)
    assert len(ruleset.checklist) == 27
    assert all(
        item.verification.status == "TODO_REGULATORY_VALIDATION"
        for item in ruleset.checklist
    )
    assert all(item.evidence_required is None for item in ruleset.checklist)


def test_stage5_candidate_file_is_not_in_runtime_loader():
    source = (
        REPO / "backend" / "app" / "compliance" / "ruleset.py"
    ).read_text(encoding="utf-8")
    assert "phase25_stage5_candidate.json" not in source


def test_stage5_external_signoff_gates_are_all_pending():
    path = (
        REPO
        / "docs"
        / "regulatory"
        / "phase25_stage5_external_signoff_checklist.csv"
    )
    with path.open(encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle))

    assert len(rows) == 9
    assert all(row["status"] == "PENDING" for row in rows)


def test_stage5_document_separates_implementation_from_verification():
    text = (REPO / "PHASE25_STAGE5.md").read_text(encoding="utf-8")

    assert "STAGE 5 IMPLEMENTATION WORK = COMPLETE" in text
    assert "does **not** mean" in text
    assert "REG-15 REGULATORY VERIFICATION = COMPLETE" in text
    assert "candidate-v1" in text


def test_stage5_verifier_reports_safe_final_boundary():
    result = verify_stage5()

    assert result["implementation_status"] == "COMPLETE"
    assert result["regulatory_verification_status"] == (
        "PENDING_INDEPENDENT_SIGNOFF"
    )
    assert result["activation_allowed"] is False
    assert result["authoritative_section16"] == "BLOCKED"
    assert result["authoritative_section17"] == "BLOCKED"
    assert result["construction_categories"] == 8
    assert result["checklist_domains"] == 27
    assert len(result["candidate_hash"]) == 64
