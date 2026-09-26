"""Phase 23 Stage 3 source-contract tests."""

from pathlib import Path

BACKEND = Path(__file__).resolve().parents[1]
SCRIPT = BACKEND / "scripts" / "verify_phase23_demo_walkthrough.py"
DOC = BACKEND.parent / "PHASE23_STAGE3.md"


def source() -> str:
    return SCRIPT.read_text(encoding="utf-8")


def documentation() -> str:
    return DOC.read_text(encoding="utf-8")


def test_stage3_verifier_is_api_only() -> None:
    text = source()
    forbidden = (
        "from app.models",
        "import app.models",
        "from app.db",
        "import sqlalchemy",
        "from app.repositories",
    )
    assert not any(item in text for item in forbidden)
    assert "httpx" in text


def test_stage3_checks_all_four_canonical_scenarios() -> None:
    text = source()
    assert "SIH26035-DEMO-NOMINAL" in text
    assert "SIH26035-DEMO-ADVERSE" in text
    assert "SIH26035-DEMO-POSITIVE" in text
    assert "SIH26035-DEMO-NEGATIVE" in text


def test_stage3_checks_role_separation_and_synthetic_ruleset() -> None:
    text = source()
    assert "LAB_ENGINEER" in text
    assert "REVIEWER" in text
    assert "APPROVING_OFFICER" in text
    assert "SYNTHETIC_TEST_SIH26035_DEMO_V1" in text
    assert 'ruleset_status") != "DRAFT"' in text


def test_stage3_checks_history_dashboard_and_repository() -> None:
    text = source()
    assert "/history" in text
    assert "/dashboard/summary" in text
    assert '"/api/v1/reports"' in text
    assert "all 17 sections" in text


def test_stage3_checks_unofficial_preview_download_integrity() -> None:
    text = source()
    assert "UNOFFICIAL_PREVIEW" in text
    assert "hashlib.sha256(body).hexdigest()" in text
    assert '("pdf", b"%PDF-")' in text
    assert '("docx", b"PK")' in text


def test_stage3_keeps_official_synthetic_path_blocked() -> None:
    text = source()
    assert "SYNTHETIC_DEMO_OFFICIAL_FORBIDDEN" in text
    assert "/submit-for-review" in text
    assert "/reports" in text


def test_stage3_documentation_defines_safe_non_destructive_reset() -> None:
    text = documentation()
    assert "Do **not** delete production rows" in text
    assert "seed_phase23_demo_foundation" in text
    assert "seed_phase23_demo_scenarios" in text
    assert "verify_phase23_demo_walkthrough" in text
    assert "Append-only history is deliberately preserved" in text
