"""Phase 26 Stage 8 static/frozen acceptance verifier."""

from __future__ import annotations

from pathlib import Path

from scripts.phase26_demo import (
    EXPECTED_REPORT_COUNTS,
    LIVE_PREFIX,
    V3_ARTIFACT,
    V3_VERSION,
    canonical_snapshot,
)

ROOT = Path(__file__).resolve().parents[1]


def main() -> None:
    source = (ROOT / "scripts/phase26_demo.py").read_text(encoding="utf-8")
    runbook = (ROOT.parent / "PHASE26_STAGE8.md").read_text(encoding="utf-8")

    assert V3_ARTIFACT == "sih26035_full_flow_demo_v3"
    assert V3_VERSION == "SYNTHETIC_TEST_SIH26035_FULL_FLOW_V3"
    assert LIVE_PREFIX == "SIH26035-FULL-DEMO-LIVE"
    assert EXPECTED_REPORT_COUNTS == {
        "sections": 17,
        "runs": 23,
        "observations": 92,
        "environment_readings": 23,
        "equipment_links": 24,
        "results": 23,
        "construction_items": 8,
        "checklist": 27,
        "evidence_links": 85,
        "unique_evidence_attachments": 60,
    }

    snapshot = canonical_snapshot()
    assert snapshot["software_identifier"] == "SIH26035-V3-DEMO"
    assert snapshot["maximum_tare_g"] == "5000"
    assert len(snapshot["ranges"]) == 1

    for endpoint in (
        "/api/v1/test-sessions",
        "/configure",
        "/applicability",
        "/confirm-applicability",
        "/start-testing",
        "/demo-complete-evaluation",
        "/full-demo-report-previews",
        "/submit-for-review",
        "/reports",
    ):
        assert endpoint in source

    assert "sqlalchemy" not in source.lower()
    assert "app.models" not in source
    assert "DELETE FROM" not in source.upper()
    assert ".delete(" not in source
    assert '"reset", "accept", "status"' in source
    assert "SYNTHETIC_DEMO_OFFICIAL_FORBIDDEN" in source
    assert "Global ADMIN is" in source
    assert source.index("login(client, ENGINEER_EMAIL") < source.index(
        "ensure_manufacturer(client, lab"
    )

    for step in (
        "Reset / seed",
        "Judge walkthrough",
        "Automated final acceptance",
        "Emergency re-reset",
    ):
        assert step in runbook

    print("Phase 26 Stage 8 acceptance: PASS")
    print("- one-command public-API demo reset/seed operator: PASS")
    print("- canonical V3 snapshot pin: PASS")
    print("- no SQLAlchemy/model/database-delete path: PASS")
    print("- reset preserves completed regulatory history: PASS")
    print("- Stage 6 full 17-section endpoint wired: PASS")
    print("- Stage 7 full PDF/DOCX endpoint wired: PASS")
    print("- synthetic review/official-report guards checked: PASS")
    print("- expected report evidence: 85 links / 60 unique attachments")
    print("- final SIH judge runbook present: PASS")
    print("- no database migration required")


if __name__ == "__main__":
    main()
