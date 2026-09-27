"""Phase 25 Stage 5 final acceptance verifier."""

from __future__ import annotations

import csv
import json
from pathlib import Path

from app.compliance.candidate_stage5 import load_stage5_candidate
from app.compliance.catalog import CHECKLIST_DOMAINS
from app.compliance.ruleset import load_ruleset

BACKEND = Path(__file__).resolve().parents[1]
REPO = BACKEND.parent
RULE_ROOT = BACKEND / "app" / "compliance" / "rules" / "oiml_r76_2006"

EXPECTED_CONSTRUCTION_CATEGORIES = {
    "GENERAL",
    "RECEPTOR_LOAD_CELLS",
    "INDICATOR_DISPLAY",
    "PRINTER_PERIPHERALS",
    "POWER_INTERFACES",
    "TILT_ZERO_TARE",
    "SEALS_SECURITY_SOFTWARE",
    "DOCUMENTS_PHOTOS",
}


def _candidate_checklist_keys():
    return {
        f"{group}_{domain}"
        for group, domains in CHECKLIST_DOMAINS.items()
        for domain in domains
    }


def verify_stage5() -> dict[str, object]:
    candidate = load_stage5_candidate()
    ruleset = load_ruleset()

    assert candidate.verification_status == (
        "SOURCE_MAPPED_PENDING_INDEPENDENT_SIGNOFF"
    )
    assert candidate.activation_allowed is False
    assert candidate.independent_verifier == "PENDING"
    assert candidate.register_ids == ("REG-15",)
    assert all(source.digest is None for source in candidate.sources)
    assert all(
        source.acquisition_status == "PENDING_CONTROLLED_ACQUISITION"
        for source in candidate.sources
    )

    section16 = candidate.section16
    section17 = candidate.section17
    assert section16["activation_allowed"] is False
    assert section17["activation_allowed"] is False

    categories = {
        item["category"]
        for item in section16["internal_capture_categories"]
    }
    assert categories == EXPECTED_CONSTRUCTION_CATEGORIES

    mapped = {item["key"] for item in section17["domains"]}
    assert mapped == _candidate_checklist_keys()
    assert len(mapped) == 27
    assert {item["group"] for item in section17["domains"]} == {
        "GENERAL",
        "DIRECT_SALES",
        "ELECTRONIC",
        "SOFTWARE_CONTROLLED",
    }
    assert {
        item["r76_2_report_section"]
        for item in section17["domains"]
    } == {"17.1", "17.2", "17.3", "17.4"}

    assert "clause 6" in section17["principles"]["non_self_indicating_branch"]

    ruleset_source = (
        BACKEND / "app" / "compliance" / "ruleset.py"
    ).read_text(encoding="utf-8")
    assert "phase25_stage5_candidate.json" not in ruleset_source

    metadata = json.loads((RULE_ROOT / "metadata.yaml").read_text(encoding="utf-8"))
    assert metadata["version"] == "candidate-v1"
    assert metadata["supported_test_codes"] == []

    assert not any(rule.kind == "construction_item_v1" for rule in ruleset.rules)

    assert len(ruleset.checklist) == 27
    assert all(
        item.verification.status == "TODO_REGULATORY_VALIDATION"
        for item in ruleset.checklist
    )
    assert all(item.evidence_required is None for item in ruleset.checklist)
    assert all(item.source.clause is None for item in ruleset.checklist)
    assert all(item.source.digest is None for item in ruleset.checklist)

    construction_source = (
        BACKEND / "app" / "services" / "construction.py"
    ).read_text(encoding="utf-8")
    checklist_source = (
        BACKEND / "app" / "compliance" / "checklist.py"
    ).read_text(encoding="utf-8")
    assert 'rule.validation_status != "VERIFIED"' in construction_source
    assert 'rule.validation_status != "VERIFIED"' in checklist_source
    assert "REG-15:NO_SECTION16_CONSTRUCTION_CATALOG" in construction_source
    assert "REG-15:NO_SECTION17_CHECKLIST_CATALOG" in checklist_source

    required_docs = (
        "PHASE25_STAGE5.md",
        "docs/regulatory/PHASE25_STAGE5_SOURCE_AND_GAP_ANALYSIS.md",
        "docs/regulatory/PHASE25_STAGE5_FINAL_ACCEPTANCE.md",
        "docs/regulatory/phase25_stage5_source_extraction.csv",
        "docs/regulatory/phase25_stage5_construction_mapping.csv",
        "docs/regulatory/phase25_stage5_checklist_mapping.csv",
        "docs/regulatory/phase25_stage5_external_signoff_checklist.csv",
    )
    for relative in required_docs:
        assert (REPO / relative).is_file(), relative

    checklist_path = (
        REPO
        / "docs"
        / "regulatory"
        / "phase25_stage5_external_signoff_checklist.csv"
    )
    with checklist_path.open(encoding="utf-8", newline="") as handle:
        gates = list(csv.DictReader(handle))
    assert len(gates) == 9
    assert all(gate["status"] == "PENDING" for gate in gates)

    return {
        "implementation_status": "COMPLETE",
        "regulatory_verification_status": "PENDING_INDEPENDENT_SIGNOFF",
        "activation_allowed": False,
        "authoritative_section16": "BLOCKED",
        "authoritative_section17": "BLOCKED",
        "registers": ("REG-15",),
        "construction_categories": len(categories),
        "checklist_domains": len(mapped),
        "candidate_hash": candidate.candidate_hash,
    }


def main():
    result = verify_stage5()
    print("Phase 25 Stage 5 verification passed.")
    print(f"Implementation status: {result['implementation_status']}")
    print(
        "Regulatory verification status: "
        f"{result['regulatory_verification_status']}"
    )
    print(f"Activation allowed: {result['activation_allowed']}")
    print(
        "Authoritative Section 16 runtime: "
        f"{result['authoritative_section16']}"
    )
    print(
        "Authoritative Section 17 runtime: "
        f"{result['authoritative_section17']}"
    )
    print(
        "Section 16 internal capture categories: "
        f"{result['construction_categories']}"
    )
    print(f"Section 17 mapped domains: {result['checklist_domains']}")
    print(f"Stage 5 candidate hash: {result['candidate_hash']}")


if __name__ == "__main__":
    main()
