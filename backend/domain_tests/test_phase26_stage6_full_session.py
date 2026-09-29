from app.compliance.aggregation import (
    AggregationChild,
    AggregationInput,
    SessionComplianceAggregator,
)
from app.compliance.full_demo_session import (
    full_demo_run_seeds,
    full_demo_traceability_counts,
)


def test_stage6_persisted_seed_plan_has_complete_v3_traceability():
    seeds = full_demo_run_seeds()

    assert len(seeds) == 23
    assert full_demo_traceability_counts(seeds) == {
        "runs": 23,
        "observations": 92,
        "environment": 23,
        "equipment": 24,
        "evidence": 23,
        "calibration_evidence": 2,
    }
    assert all(
        seed.client_procedure_context["equipment"] == []
        and seed.client_procedure_context["environment"] == []
        and seed.client_procedure_context["evidence_hashes"] == []
        for seed in seeds
    )
    assert all(
        seed.procedure_context["evaluation_context"] == "SYNTHETIC"
        for seed in seeds
    )


def test_stage6_seventeen_complete_compliant_sections_close_session():
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

    assert result.evaluation_status == "COMPLETE"
    assert result.compliance_outcome == "COMPLIANT"
