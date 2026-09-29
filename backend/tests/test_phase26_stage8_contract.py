from pathlib import Path

from scripts.phase26_demo import (
    EXPECTED_REPORT_COUNTS,
    INSTRUMENT_MODEL,
    LIVE_PREFIX,
    V3_ARTIFACT,
    V3_VERSION,
    canonical_snapshot,
)

ROOT = Path(__file__).resolve().parents[2]


def test_stage8_operator_is_public_api_only_and_history_preserving():
    source = (
        ROOT / "backend/scripts/phase26_demo.py"
    ).read_text(encoding="utf-8")

    assert "sqlalchemy" not in source.lower()
    assert "app.models" not in source
    assert "DELETE FROM" not in source.upper()
    assert ".delete(" not in source
    assert "retire_unfinished" in source
    assert 'workflow_status") not in MUTABLE_WORKFLOWS' in source
    assert "/cancel" in source


def test_stage8_operator_pins_the_final_v3_flow():
    source = (
        ROOT / "backend/scripts/phase26_demo.py"
    ).read_text(encoding="utf-8")

    assert V3_ARTIFACT == "sih26035_full_flow_demo_v3"
    assert V3_VERSION == "SYNTHETIC_TEST_SIH26035_FULL_FLOW_V3"
    assert LIVE_PREFIX == "SIH26035-FULL-DEMO-LIVE"
    assert "DEMO ONLY" in INSTRUMENT_MODEL
    assert canonical_snapshot()["maximum_tare_g"] == "5000"

    for endpoint in (
        "/configure",
        "/applicability",
        "/confirm-applicability",
        "/start-testing",
        "/demo-complete-evaluation",
        "/full-demo-report-previews",
    ):
        assert endpoint in source


def test_stage8_acceptance_verifies_non_official_boundaries():
    source = (
        ROOT / "backend/scripts/phase26_demo.py"
    ).read_text(encoding="utf-8")

    assert "/submit-for-review" in source
    assert "SYNTHETIC_DEMO_OFFICIAL_FORBIDDEN" in source
    assert "official report repository" in source
    assert EXPECTED_REPORT_COUNTS["sections"] == 17
    assert EXPECTED_REPORT_COUNTS["runs"] == 23
    assert EXPECTED_REPORT_COUNTS["evidence_links"] == 85
    assert EXPECTED_REPORT_COUNTS["unique_evidence_attachments"] == 60


def test_stage8_runbook_contains_reset_accept_and_judge_sequence():
    runbook = (ROOT / "PHASE26_STAGE8.md").read_text(encoding="utf-8")

    assert "uv run python -m scripts.phase26_demo reset" in runbook
    assert "uv run python -m scripts.phase26_demo accept" in runbook
    assert "Complete all 17 synthetic demo sections" in runbook
    assert "Generate complete 17-section demo report" in runbook
    assert "NOT AN OFFICIAL OIML CERTIFICATE" in runbook
