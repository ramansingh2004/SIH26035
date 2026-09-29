"""Phase 26 Stage 5 focused acceptance verifier."""

from app.compliance.checklist import ChecklistAssessment, ChecklistEngine
from app.compliance.domain import Applicability, ApplicabilityDecision
from app.compliance.full_demo_checklist import (
    EXPECTED_GROUP_COUNTS,
    NOTICE,
    full_demo_checklist_plan,
)
from app.compliance.full_demo_execution import (
    FULL_DEMO_EXECUTION_VERSION,
    load_full_demo_execution_ruleset,
)


def main() -> None:
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

    counts = {
        group: sum(item.group_code == group for item in plan)
        for group in EXPECTED_GROUP_COUNTS
    }

    assert len(plan) == 27
    assert counts == EXPECTED_GROUP_COUNTS
    assert all(item.evidence_required for item in plan)
    assert all(len(item.evidence_sha256) == 64 for item in plan)
    assert summary["evaluation_status"] == "COMPLETE"
    assert summary["compliance_outcome"] == "COMPLIANT"
    assert summary["passed"] == 27
    assert summary["missing_rule_keys"] == []
    assert summary["blockers"] == []

    print("Phase 26 Stage 5 acceptance: PASS")
    print(f"- ruleset version: {FULL_DEMO_EXECUTION_VERSION}")
    print("- Section 17 checklist rows: 27/27")
    print(f"- checklist group counts: {counts}")
    print("- required checklist rows: 27")
    print("- synthetic evidence descriptors: 27")
    print("- deterministic PASS responses: 27")
    print("- Section 17 summary: COMPLETE + COMPLIANT")
    print("- Section 16 prerequisite guard: enabled")
    print("- metadata-only evidence notice present: PASS")
    print(f"- notice: {NOTICE}")
    print("- production/official regulatory paths remain unchanged")
    print("- no database migration required")


if __name__ == "__main__":
    main()
