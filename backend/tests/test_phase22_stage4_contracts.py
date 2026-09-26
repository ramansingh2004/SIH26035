"""Phase 22 Stage 4 Vercel deployment contracts."""

from pathlib import Path

import pytest

from scripts.check_vercel_frontend import frontend_origin

ROOT = Path(__file__).resolve().parents[2]


def test_vercel_frontend_origin_accepts_https(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv(
        "VERCEL_FRONTEND_URL",
        "https://sih26035.vercel.app/",
    )

    assert frontend_origin() == "https://sih26035.vercel.app"


@pytest.mark.parametrize(
    "value",
    [
        "http://sih26035.vercel.app",
        "https://sih26035.vercel.app/login",
    ],
)
def test_vercel_frontend_origin_rejects_invalid_origin(
    monkeypatch: pytest.MonkeyPatch,
    value: str,
) -> None:
    monkeypatch.setenv("VERCEL_FRONTEND_URL", value)

    with pytest.raises(RuntimeError, match="HTTPS origin"):
        frontend_origin()


def test_vercel_frontend_origin_requires_configuration(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("VERCEL_FRONTEND_URL", raising=False)

    with pytest.raises(RuntimeError, match="VERCEL_FRONTEND_URL"):
        frontend_origin()


def test_stage4_verifier_checks_login_and_same_origin_api() -> None:
    source = (
        ROOT / "backend/scripts/check_vercel_frontend.py"
    ).read_text(encoding="utf-8")

    assert 'request("/login")' in source
    assert 'request("/api/v1/auth/me")' in source
    assert "auth_status != 401" in source
    assert 'headers.get("cache-control") != "no-store"' in source


def test_stage4_frontend_uses_server_side_render_proxy() -> None:
    next_config = (
        ROOT / "frontend/next.config.ts"
    ).read_text(encoding="utf-8")

    frontend_config = (
        ROOT / "frontend/src/lib/config.ts"
    ).read_text(encoding="utf-8")

    assert "BACKEND_API_ORIGIN" in next_config
    assert "NEXT_PUBLIC_BACKEND_API_ORIGIN" not in next_config
    assert 'source: "/api/v1/:path*"' in next_config

    assert 'configured === "/"' in frontend_config
    assert 'return ""' in frontend_config
