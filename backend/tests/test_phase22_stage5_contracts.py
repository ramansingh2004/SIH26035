"""Phase 22 Stage 5 production acceptance contracts."""

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def read(relative: str) -> str:
    return (ROOT / relative).read_text(encoding="utf-8")


def test_production_bootstrap_uses_existing_authoritative_service() -> None:
    source = read("backend/scripts/bootstrap_production_admin.py")
    assert "ProvisioningService(session).bootstrap" in source
    assert "getpass.getpass" in source
    assert "password and database credentials were not printed" in source


def test_acceptance_runs_through_stable_vercel_origin() -> None:
    source = read("backend/scripts/check_production_acceptance.py")
    assert "VERCEL_FRONTEND_URL" in source
    assert 'headers={"Origin": origin' in source
    assert '"/api/v1/auth/login"' in source


def test_acceptance_verifies_strict_cookie_and_rotation_contracts() -> None:
    source = read("backend/scripts/check_production_acceptance.py")
    assert "samesite=strict" in source
    assert "httponly" in source
    assert "Refresh token did not rotate" in source
    assert '"/api/v1/auth/logout"' in source


def test_acceptance_verifies_real_s3_browser_cors_and_integrity() -> None:
    source = read("backend/scripts/check_production_acceptance.py")
    assert '"Access-Control-Request-Method": "PUT"' in source
    assert "access-control-allow-origin" in source
    assert '"/api/v1/attachments/presign"' in source
    assert '"/api/v1/attachments/complete"' in source
    assert "Production evidence download integrity verification failed" in source


def test_acceptance_preserves_candidate_regulatory_gate() -> None:
    source = read("backend/scripts/check_production_acceptance.py")
    assert "oiml_r76_2006/candidate-v1" in source
    assert "TODO_REGULATORY_VALIDATION" in source
    assert "/activate" not in source
    assert "no authoritative compliance outcome or official report was fabricated" in source


def test_acceptance_checks_phase21_history_and_report_surfaces() -> None:
    source = read("backend/scripts/check_production_acceptance.py")
    assert '/revisions"' in source
    assert '/reviews"' in source
    assert '/corrections"' in source
    assert "/history" in source
    assert "/api/v1/reports?laboratory_id=" in source
    assert "/report-previews" in source
