"""Phase 23 Stage 1 demo-foundation source contracts."""

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def read(relative: str) -> str:
    return (ROOT / relative).read_text(encoding="utf-8")


def test_demo_seed_uses_application_api_not_database_shortcuts() -> None:
    source = read("backend/scripts/seed_phase23_demo_foundation.py")
    assert "import httpx" in source
    assert "import sqlalchemy" not in source.lower()
    assert "from sqlalchemy" not in source.lower()
    assert "app.models" not in source
    assert "app.repositories" not in source
    assert "app.services" not in source


def test_demo_seed_uses_stable_same_origin_production_path() -> None:
    source = read("backend/scripts/seed_phase23_demo_foundation.py")
    assert "https://sih26035.vercel.app" in source
    assert '"Origin": origin' in source
    assert '"/api/v1/auth/login"' in source


def test_demo_foundation_has_separate_operational_identities() -> None:
    source = read("backend/scripts/seed_phase23_demo_foundation.py")
    assert "LAB_ENGINEER" in source
    assert "REVIEWER" in source
    assert "APPROVING_OFFICER" in source
    assert "demo.engineer@example.com" in source
    assert "demo.reviewer@example.com" in source
    assert "demo.approver@example.com" in source


def test_demo_foundation_contains_required_master_data() -> None:
    source = read("backend/scripts/seed_phase23_demo_foundation.py")
    assert "SIH26035-DEMO" in source
    assert "Class III" in source
    assert '"accuracy_class": "III"' in source
    assert "/ranges" in source
    assert "/components" in source
    assert "/api/v1/test-equipment" in source


def test_stage1_scenarios_are_visibly_synthetic_and_undetermined() -> None:
    source = read("backend/scripts/seed_phase23_demo_foundation.py")
    assert "SYNTHETIC SIH DEMO ONLY" in source
    assert "SIH26035-DEMO-NOMINAL" in source
    assert "SIH26035-DEMO-ADVERSE" in source
    assert '"UNDETERMINED"' in source
    assert 'applicability.get("confirmable") is not False' in source


def test_stage1_does_not_activate_or_issue_anything() -> None:
    source = read("backend/scripts/seed_phase23_demo_foundation.py")
    assert "/activate" not in source
    assert "/issue" not in source
    assert "/approve" not in source
    assert "COMPLIANT" not in source
    assert "NONCOMPLIANT" not in source
    assert "official report issue performed" in source
