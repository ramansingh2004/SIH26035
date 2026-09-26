"""Phase 22 Stage 3 Render deployment contracts."""

from pathlib import Path

import pytest

from scripts.start_render import render_port

ROOT = Path(__file__).resolve().parents[2]


def test_render_entrypoint_binds_render_port(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("PORT", "12345")
    assert render_port() == 12345


@pytest.mark.parametrize("value", ["abc", "0", "65536", "-1"])
def test_render_entrypoint_rejects_invalid_ports(
    monkeypatch: pytest.MonkeyPatch, value: str
) -> None:
    monkeypatch.setenv("PORT", value)
    with pytest.raises(RuntimeError, match="PORT"):
        render_port()


def test_render_entrypoint_configures_database_before_importing_app() -> None:
    source = (ROOT / "backend/scripts/start_render.py").read_text(encoding="utf-8")
    assert source.index("configure_render_database_url()") < source.index("uvicorn.run(")
    assert '"app.main:app"' in source
    assert 'host="0.0.0.0"' in source


def test_render_python_runtime_is_pinned_to_supported_minor() -> None:
    assert (ROOT / "backend/.python-version").read_text(encoding="utf-8").strip() == "3.12"


def test_render_predeploy_gate_order() -> None:
    source = (ROOT / "backend/scripts/render_predeploy.py").read_text(encoding="utf-8")
    assert source.index("check_config()") < source.index("run_migrations()")
    assert source.index("run_migrations()") < source.index("check_dependencies()")


def test_public_verifier_covers_production_surface() -> None:
    source = (ROOT / "backend/scripts/check_render_service.py").read_text(encoding="utf-8")
    for marker in ('request("/health")', 'request("/docs")', 'request("/openapi.json")',
                   'request("/api/v1/auth/me")', "RENDER_SERVICE_URL"):
        assert marker in source
