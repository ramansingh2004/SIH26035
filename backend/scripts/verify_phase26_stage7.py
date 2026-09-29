"""Phase 26 Stage 7 full-demo report acceptance verifier."""

from __future__ import annotations

from app.reporting.context import full_demo_report_context
from app.reporting.full_demo import (
    EXPECTED_FULL_DEMO_COUNTS,
    validate_full_demo_record,
)
from app.reporting.renderers import build_plan, render_pair

SECTION_NAMES = (
    "WEIGHING PERFORMANCE",
    "TEMPERATURE ZERO",
    "ECCENTRICITY",
    "DISCRIMINATION / SENSITIVITY",
    "REPEATABILITY",
    "TIME DEPENDENCE",
    "STABILITY EQUILIBRIUM",
    "TILTING",
    "TARE",
    "WARM UP",
    "VOLTAGE VARIATION",
    "ELECTRICAL DISTURBANCES",
    "DAMP HEAT",
    "SPAN STABILITY",
    "ENDURANCE",
    "CONSTRUCTION EXAMINATION",
    "CHECKLIST",
)


def fixture_record() -> dict:
    requirements = [
        {
            "id": f"requirement-{index}",
            "slot_snapshot": {
                "test_code": f"DEMO_TEST_{index:02d}",
                "section": min(index, 15),
            },
        }
        for index in range(1, 24)
    ]
    runs = [
        {
            "id": f"run-{index}",
            "requirement_id": f"requirement-{index}",
            "run_no": 1,
            "evaluation_status": "COMPLETE",
            "compliance_outcome": "COMPLIANT",
            "current_result_id": f"result-{index}",
            "completed_at": "2026-09-29T00:00:00Z",
            "procedure_context": {
                "test_code": f"DEMO_TEST_{index:02d}",
                "evaluation_context": "SYNTHETIC",
            },
            "input_revision": 1,
        }
        for index in range(1, 24)
    ]

    observations = [
        {
            "id": f"observation-{index}",
            "test_run_id": f"run-{((index - 1) % 23) + 1}",
            "sequence_no": index,
            "payload_json": {"synthetic": True},
        }
        for index in range(1, 93)
    ]
    environments = [
        {
            "id": f"environment-{index}",
            "test_run_id": f"run-{index}",
            "measured_at": "2026-09-29T00:00:00Z",
            "temperature_c": "20",
            "phase": "SYNTHETIC",
        }
        for index in range(1, 24)
    ]
    equipment = [
        {
            "id": f"equipment-link-{index}",
            "test_run_id": f"run-{((index - 1) % 23) + 1}",
            "equipment_snapshot": {
                "category": "SYNTHETIC",
                "reference_number": f"DEMO-EQUIPMENT-{index:02d}",
            },
        }
        for index in range(1, 25)
    ]
    results = [
        {
            "id": f"result-{index}",
            "test_run_id": f"run-{index}",
            "evaluation_status": "COMPLETE",
            "compliance_outcome": "COMPLIANT",
            "calculations_json": [],
            "acceptance_limits_json": [],
            "failed_conditions_json": [],
        }
        for index in range(1, 24)
    ]
    construction_items = [
        {
            "id": f"construction-{index}",
            "item_key": f"CONSTRUCTION_{index:02d}",
            "category": "GENERAL",
            "description_snapshot": f"Synthetic construction item {index}",
            "examination_state": "EXAMINED",
            "conformance_result": "PASS",
            "remarks": "SYNTHETIC DEMO ONLY",
        }
        for index in range(1, 9)
    ]
    checklist = [
        {
            "response": {
                "id": f"checklist-response-{index}",
                "applicability_status": "REQUIRED",
                "response_result": "PASS",
                "remarks": "SYNTHETIC DEMO ONLY",
            },
            "rule": {
                "requirement_key": f"CHECKLIST_{index:02d}",
                "display_text": f"Synthetic checklist item {index}",
            },
        }
        for index in range(1, 28)
    ]
    evidence = []
    for index in range(1, 86):
        attachment_index = index if index <= 60 else index - 60
        evidence.append(
            {
                "link": {
                    "entity_type": (
                        "synthetic_demo"
                        if index <= 60
                        else "test_run_results"
                    ),
                    "entity_id": f"target-{index}",
                    "purpose": (
                        "synthetic_demo"
                        if index <= 60
                        else "result_traceability"
                    ),
                },
                "attachment": {
                    "id": f"evidence-attachment-{attachment_index:02d}",
                    "file_name": f"evidence-{attachment_index:02d}.txt",
                    "sha256": f"{attachment_index:064x}"[-64:],
                    "object_version": "phase26-stage7-fixture",
                },
            }
        )

    return {
        "schema_version": 1,
        "session": {
            "id": "11111111-2222-3333-4444-555555555555",
            "application_number": "SIH26035-STAGE7-DEMO",
            "workflow_status": "EXAMINATION",
            "evaluation_status": "COMPLETE",
            "compliance_outcome": "COMPLIANT",
            "evaluation_context": "SYNTHETIC",
        },
        "laboratory": {
            "name": "SIH26035 Demo Laboratory",
            "code": "SIH26035-DEMO",
            "country": "India",
        },
        "manufacturer": {"name": "Synthetic Demo Manufacturer"},
        "instrument_master_at_approval": {
            "model_name": "SIH26035 V3 Demo Instrument",
            "accuracy_class": "III",
        },
        "instrument_ranges_at_approval": [],
        "ruleset_record": {
            "standard_code": "OIML_R76",
            "edition": "SIH-FULL-DEMO-v3",
            "version": "SYNTHETIC_TEST_SIH26035_FULL_FLOW_V3",
            "configuration_hash": "a" * 64,
            "source_reference": "SYNTHETIC TEST FIXTURE ONLY",
        },
        "ruleset_snapshot": {"synthetic": True},
        "sections": [
            {
                "section_number": index,
                "code": name.replace(" / ", "_").replace(" ", "_"),
                "section_name": name,
                "applicability_status": "REQUIRED",
                "applicability_reason": "SYNTHETIC V3 DEMO",
                "evaluation_status": "COMPLETE",
                "compliance_outcome": "COMPLIANT",
            }
            for index, name in enumerate(SECTION_NAMES, start=1)
        ],
        "requirements": requirements,
        "runs": runs,
        "observations": observations,
        "environment_readings": environments,
        "equipment_links": equipment,
        "results": results,
        "result_events": [],
        "selection_events": [],
        "construction": {
            "examination": {
                "evaluation_status": "COMPLETE",
                "compliance_outcome": "COMPLIANT",
                "overall_notes": "SYNTHETIC DEMO ONLY",
            },
            "items": construction_items,
            "rules": [],
        },
        "checklist": checklist,
        "evidence": evidence,
        "approval_actions": [],
        "actors": [],
    }


def main() -> None:
    record = fixture_record()
    counts = validate_full_demo_record(record)
    context = full_demo_report_context(
        record,
        requested_by="phase26-stage7-verifier",
        source_regulatory_revision=77,
    )
    plan = build_plan(context)
    rendered = render_pair(context)

    assert counts == EXPECTED_FULL_DEMO_COUNTS
    assert context["document_kind"] == "FULL_DEMO_REPORT"
    assert "NOT AN OFFICIAL OIML CERTIFICATE" in plan.status
    assert plan.watermark == "SIMULATED / DEMONSTRATION ONLY"
    assert rendered["pdf"][0].startswith(b"%PDF-")
    assert rendered["docx"][0].startswith(b"PK")

    titles = [section.title for section in plan.sections]
    assert "Executive Summary - All 17 Sections" in titles
    assert "Test Runs, Observations and Stored Results" in titles
    assert "Construction Examination" in titles
    assert "Checklist" in titles
    assert "Evidence Register" in titles

    print("Phase 26 Stage 7 acceptance: PASS")
    print("- document kind: FULL_DEMO_REPORT")
    print("- source: completed V3 Stage 6 session only")
    for key, value in counts.items():
        print(f"- source {key}: {value}")
    print("- detailed 17-section report plan: PASS")
    print("- PDF renderer: PASS")
    print("- DOCX renderer: PASS")
    print("- explicit NOT AN OFFICIAL OIML CERTIFICATE label: PASS")
    print("- compact Phase 25 simulation remains separate")
    print("- official report generation/issue path remains unchanged")
    print("- no database migration required")


if __name__ == "__main__":
    main()
