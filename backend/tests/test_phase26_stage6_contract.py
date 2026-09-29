from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def test_stage6_route_and_orchestration_use_real_service_boundaries():
    testing_api = (
        ROOT / "backend/app/api/v1/testing.py"
    ).read_text(encoding="utf-8")
    service = (
        ROOT / "backend/app/services/testing.py"
    ).read_text(encoding="utf-8")

    assert "/demo-complete-evaluation" in testing_api
    assert "demo_complete_evaluation" in testing_api
    assert "full_demo_run_seeds" in service
    assert "self.evaluate(" in service
    assert '"complete"' in service
    assert "ConstructionService" in service
    assert "ChecklistService" in service
    assert "start_examination" in service
    assert "construction.demo_complete" in service
    assert "checklist.demo_complete" in service


def test_stage6_guards_remain_demo_only_and_do_not_enter_governance():
    service = (
        ROOT / "backend/app/services/testing.py"
    ).read_text(encoding="utf-8")

    assert "is_full_demo_execution_ruleset" in service
    assert "DEMO_LAB_CODE" in service
    assert 'row.evaluation_context != "SYNTHETIC"' in service
    assert "SYNTHETIC_DEMO_STAGE6_FORBIDDEN" in service
    assert "SYNTHETIC_DEMO_STAGE6_REQUIRES_FRESH_TESTING" in service
    assert "SYNTHETIC_DEMO_STAGE6_INSTRUMENT_REQUIRED" in service
    assert "full_demo_execution_instrument" in service
    assert "UNDER_REVIEW" not in service[
        service.index("async def demo_complete_evaluation"):
        service.index("async def revision")
    ]


def test_stage6_frontend_exposes_one_click_full17_demo_action():
    page = (
        ROOT
        / "frontend/src/app/(protected)/evaluations/[sessionId]/page.tsx"
    ).read_text(encoding="utf-8")
    api = (
        ROOT / "frontend/src/lib/evaluations/api.ts"
    ).read_text(encoding="utf-8")

    assert "completeFullDemoEvaluation" in api
    assert "/demo-complete-evaluation" in api
    assert "Complete all 17 synthetic demo sections" in page
    assert "SYNTHETIC_TEST_SIH26035_FULL_FLOW_V3" in page
