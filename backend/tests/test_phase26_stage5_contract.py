from pathlib import Path

from app.compliance.full_demo_checklist import (
    NOTICE,
    full_demo_checklist_plan,
)
from app.compliance.full_demo_execution import load_full_demo_execution_ruleset

ROOT = Path(__file__).resolve().parents[2]


def test_stage5_backend_route_and_scope_guards_are_explicit():
    route = (
        ROOT / "backend/app/api/v1/checklist.py"
    ).read_text(encoding="utf-8")
    service = (
        ROOT / "backend/app/services/checklist.py"
    ).read_text(encoding="utf-8")

    assert "/checklist/demo-complete" in route
    assert "demo_complete" in route
    assert "is_full_demo_execution_ruleset" in service
    assert "DEMO_LAB_CODE" in service
    assert 'session.evaluation_context != "SYNTHETIC"' in service
    assert "SYNTHETIC_DEMO_STAGE5_FORBIDDEN" in service
    assert "SYNTHETIC_DEMO_STAGE5_SECTION16_REQUIRED" in service
    assert "synthetic-demo" in service
    assert "metadata_only" in service


def test_stage5_synthetic_evidence_is_unambiguously_non_regulatory():
    plan = full_demo_checklist_plan(load_full_demo_execution_ruleset())

    assert "not regulatory evidence" in NOTICE
    assert len(plan) == 27
    assert all("SYNTHETIC" in item.remarks for item in plan)
    assert all(item.evidence_file_name.endswith(".txt") for item in plan)
