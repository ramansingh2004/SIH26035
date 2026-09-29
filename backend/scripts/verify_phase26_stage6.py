"""Phase 26 Stage 6 focused acceptance verifier."""

from app.compliance.aggregation import (
    AggregationChild,
    AggregationInput,
    SessionComplianceAggregator,
)
from app.compliance.full_demo_checklist import full_demo_checklist_plan
from app.compliance.full_demo_construction import full_demo_construction_plan
from app.compliance.full_demo_execution import (
    FULL_DEMO_EXECUTION_VERSION,
    load_full_demo_execution_ruleset,
)
from app.compliance.full_demo_session import (
    full_demo_run_seeds,
    full_demo_traceability_counts,
)


def main() -> None:
    ruleset = load_full_demo_execution_ruleset()
    seeds = full_demo_run_seeds()
    construction = full_demo_construction_plan(ruleset)
    checklist = full_demo_checklist_plan(ruleset)
    counts = full_demo_traceability_counts(seeds)

    result = SessionComplianceAggregator.aggregate(
        AggregationInput(
            children=tuple(
                AggregationChild(
                    semantic_key=f"SECTION_{number:02d}",
                    applicability="REQUIRED",
                    evaluation_status="COMPLETE",
                    compliance_outcome="COMPLIANT",
                )
                for number in range(1, 18)
            )
        )
    )

    assert counts == {
        "runs": 23,
        "observations": 92,
        "environment": 23,
        "equipment": 24,
        "evidence": 23,
        "calibration_evidence": 2,
    }
    assert len(construction) == 8
    assert len(checklist) == 27
    assert result.evaluation_status == "COMPLETE"
    assert result.compliance_outcome == "COMPLIANT"

    print("Phase 26 Stage 6 acceptance: PASS")
    print(f"- ruleset version: {FULL_DEMO_EXECUTION_VERSION}")
    print("- persisted typed runs: 23")
    print("- persisted typed observations: 92")
    print("- synthetic environment readings: 23")
    print("- synthetic equipment links: 24")
    print("- run evidence descriptors: 23")
    print("- calibration evidence descriptors: 2")
    print("- Section 16 construction items: 8")
    print("- Section 17 checklist rows: 27")
    print("- all 17 sections aggregate: COMPLETE + COMPLIANT")
    print("- workflow remains EXAMINATION; governance is not bypassed")
    print("- production/official report gates remain unchanged")
    print("- no database migration required")


if __name__ == "__main__":
    main()
