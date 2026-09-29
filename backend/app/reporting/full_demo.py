"""Phase 26 Stage 7 full-demo report completeness contract."""

from __future__ import annotations

EXPECTED_FULL_DEMO_COUNTS = {
    "sections": 17,
    "runs": 23,
    "observations": 92,
    "environment_readings": 23,
    "equipment_links": 24,
    "results": 23,
    "construction_items": 8,
    "checklist": 27,
    "evidence_links": 85,
    "unique_evidence_attachments": 60,
}


def full_demo_record_counts(record: dict) -> dict[str, int]:
    construction = record.get("construction") or {}
    evidence = record.get("evidence", [])
    unique_evidence_attachments = {
        str(item.get("attachment", {}).get("id"))
        for item in evidence
        if item.get("attachment", {}).get("id") is not None
    }
    return {
        "sections": len(record.get("sections", [])),
        "runs": len(record.get("runs", [])),
        "observations": len(record.get("observations", [])),
        "environment_readings": len(record.get("environment_readings", [])),
        "equipment_links": len(record.get("equipment_links", [])),
        "results": len(record.get("results", [])),
        "construction_items": len(construction.get("items", [])),
        "checklist": len(record.get("checklist", [])),
        "evidence_links": len(evidence),
        "unique_evidence_attachments": len(unique_evidence_attachments),
    }


def validate_full_demo_record(record: dict) -> dict[str, int]:
    session = record.get("session") or {}
    if (
        session.get("workflow_status") != "EXAMINATION"
        or session.get("evaluation_status") != "COMPLETE"
        or session.get("compliance_outcome") != "COMPLIANT"
        or session.get("evaluation_context") != "SYNTHETIC"
    ):
        raise ValueError("Stage 7 requires the completed Stage 6 session state")

    counts = full_demo_record_counts(record)
    if counts != EXPECTED_FULL_DEMO_COUNTS:
        raise ValueError(
            f"Stage 7 full-demo source counts are incomplete: {counts}"
        )

    sections = record.get("sections", [])
    if (
        {row.get("section_number") for row in sections} != set(range(1, 18))
        or any(
            row.get("applicability_status") != "REQUIRED"
            or row.get("evaluation_status") != "COMPLETE"
            or row.get("compliance_outcome") != "COMPLIANT"
            for row in sections
        )
    ):
        raise ValueError("Stage 7 requires 17 REQUIRED COMPLETE COMPLIANT sections")

    runs = record.get("runs", [])
    if any(
        row.get("evaluation_status") != "COMPLETE"
        or row.get("compliance_outcome") != "COMPLIANT"
        or row.get("current_result_id") is None
        or row.get("completed_at") is None
        for row in runs
    ):
        raise ValueError("Stage 7 requires 23 completed compliant selected runs")

    construction = record.get("construction") or {}
    examination = construction.get("examination") or {}
    if (
        examination.get("evaluation_status") != "COMPLETE"
        or examination.get("compliance_outcome") != "COMPLIANT"
        or any(
            row.get("examination_state") != "EXAMINED"
            or row.get("conformance_result") != "PASS"
            for row in construction.get("items", [])
        )
    ):
        raise ValueError("Stage 7 requires completed Section 16 construction")

    if any(
        item.get("response", {}).get("applicability_status") != "REQUIRED"
        or item.get("response", {}).get("response_result") != "PASS"
        for item in record.get("checklist", [])
    ):
        raise ValueError("Stage 7 requires 27 required PASS checklist responses")

    return counts
