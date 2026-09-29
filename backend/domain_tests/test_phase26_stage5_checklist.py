from app.compliance.checklist import ChecklistAssessment, ChecklistEngine
from app.compliance.domain import Applicability, ApplicabilityDecision
from app.compliance.full_demo_checklist import (
    EXPECTED_GROUP_COUNTS,
    NOTICE,
    full_demo_checklist_plan,
)
from app.compliance.full_demo_execution import load_full_demo_execution_ruleset


def test_stage5_v3_checklist_plan_covers_all_27_rows():
    plan = full_demo_checklist_plan(load_full_demo_execution_ruleset())

    assert len(plan) == 27
    assert len({item.requirement_key for item in plan}) == 27
    assert all(item.response_result == "PASS" for item in plan)
    assert all(item.evidence_required for item in plan)
    assert all(len(item.evidence_sha256) == 64 for item in plan)
    assert all(item.evidence_size > 0 for item in plan)
    assert all(NOTICE in item.remarks for item in plan)

    counts = {
        group: sum(item.group_code == group for item in plan)
        for group in EXPECTED_GROUP_COUNTS
    }
    assert counts == EXPECTED_GROUP_COUNTS


def test_stage5_dataset_satisfies_existing_section17_completion_semantics():
    plan = full_demo_checklist_plan(load_full_demo_execution_ruleset())
    assessments = tuple(
        ChecklistAssessment(
            rule_key=item.requirement_key,
            decision=ApplicabilityDecision(
                applicability=Applicability.REQUIRED,
                reason="SYNTHETIC V3 SOFTWARE DEMONSTRATION ONLY",
            ),
            validation_status="VERIFIED",
            evidence_required=True,
            response_result="PASS",
            evidence_count=1,
        )
        for item in plan
    )

    summary = ChecklistEngine.summarize(
        assessments,
        completion_requested=True,
    )

    assert summary["catalog_total"] == 27
    assert summary["applicable"] == 27
    assert summary["passed"] == 27
    assert summary["failed"] == 0
    assert summary["not_examined"] == 0
    assert summary["not_applicable"] == 0
    assert summary["review_required"] == 0
    assert summary["evaluation_status"] == "COMPLETE"
    assert summary["compliance_outcome"] == "COMPLIANT"
    assert summary["missing_rule_keys"] == []
    assert summary["blockers"] == []
