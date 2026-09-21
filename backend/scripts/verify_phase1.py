"""Live verification against an isolated *_dev PostgreSQL database; prints no secrets."""

import asyncio
import os
import secrets
import socket
import subprocess
import sys
import time
from uuid import uuid4

import httpx
from sqlalchemy import text
from sqlalchemy.engine import make_url

from app.core.config import Settings
from app.db.session import create_database_engine, create_session_factory
from app.services.provisioning import ProvisioningService


async def prepare(settings, email, password):
    engine = create_database_engine(settings)
    try:
        async with engine.connect() as connection:
            tables = set(
                (
                    await connection.execute(
                        text("SELECT tablename FROM pg_tables WHERE schemaname='public'")
                    )
                ).scalars()
            )
            assert tables == {
                "alembic_version",
                "users",
                "roles",
                "permissions",
                "role_permissions",
                "laboratories",
                "user_role_assignments",
                "auth_refresh_sessions",
                "audit_events",
                "idempotency_keys",
            }
            print("Development PostgreSQL schema: 9 Phase 1 tables + Alembic version; PASS")
        async with create_session_factory(engine)() as session:
            await ProvisioningService(session).bootstrap(
                email, "Verification administrator", password
            )
    finally:
        await engine.dispose()


def main():
    settings = Settings()
    if settings.database_url is None or not make_url(
        settings.database_url.get_secret_value()
    ).database.endswith("_dev"):
        raise RuntimeError("Use a disposable PostgreSQL database with a name ending in _dev")
    email = f"verify-{uuid4().hex}@example.com"
    password = secrets.token_urlsafe(32)
    asyncio.run(prepare(settings, email, password))
    with socket.socket() as probe:
        probe.bind(("127.0.0.1", 0))
        port = probe.getsockname()[1]
    env = dict(
        os.environ,
        JWT_SECRET=secrets.token_urlsafe(48),
        ENVIRONMENT="development",
        COOKIE_SECURE="false",
    )
    server = subprocess.Popen(
        [
            sys.executable,
            "-m",
            "uvicorn",
            "app.main:app",
            "--host",
            "127.0.0.1",
            "--port",
            str(port),
        ],
        env=env,
    )
    try:
        with httpx.Client(
            base_url=f"http://127.0.0.1:{port}",
            headers={"Origin": "http://127.0.0.1:3000"},
            timeout=10,
        ) as client:
            deadline = time.monotonic() + 20
            while True:
                try:
                    health = client.get("/health")
                    break
                except httpx.ConnectError:
                    if time.monotonic() >= deadline or server.poll() is not None:
                        raise
                    time.sleep(0.1)
            assert health.status_code == 200 and health.json() == {"status": "ok"}
            print("Live GET /health: HTTP 200; PASS")
            result = client.post("/api/v1/auth/login", json={"email": email, "password": password})
            assert result.status_code == 200
            client.headers["Authorization"] = "Bearer " + result.json()["access_token"]
            client.headers["X-CSRF-Token"] = client.cookies["sih_csrf"]
            assert client.get("/api/v1/auth/me").status_code == 200
            print("Live login and /auth/me: PASS")
            original = client.cookies["sih_refresh"]
            result = client.post("/api/v1/auth/refresh")
            assert result.status_code == 200 and client.cookies["sih_refresh"] != original
            client.headers["Authorization"] = "Bearer " + result.json()["access_token"]
            client.headers["X-CSRF-Token"] = client.cookies["sih_csrf"]
            print("Live persistent refresh rotation: PASS")
            labs = []
            for n in range(2):
                payload = dict(
                    name=f"Verify {n}",
                    code=uuid4().hex,
                    address_line1="Test address",
                    address_line2="",
                    city="City",
                    state="State",
                    postal_code="100001",
                    country="India",
                    phone="0000000000",
                    email="lab@example.com",
                    accreditation_no="TEST",
                )
                result = client.post("/api/v1/laboratories", json=payload)
                assert result.status_code == 201, result.text
                labs.append(result.json()["id"])
            viewer_email = f"viewer-{uuid4().hex}@example.com"
            result = client.post(
                "/api/v1/users",
                json={
                    "email": viewer_email,
                    "full_name": "Verification viewer",
                    "password": password,
                    "initial_assignment": {
                        "role_code": "VIEWER",
                        "scope_type": "LABORATORY",
                        "laboratory_id": labs[0],
                    },
                },
            )
            assert result.status_code == 201, result.text
            result = client.post(
                "/api/v1/auth/login", json={"email": viewer_email, "password": password}
            )
            assert result.status_code == 200
            client.headers["Authorization"] = "Bearer " + result.json()["access_token"]
            client.headers["X-CSRF-Token"] = client.cookies["sih_csrf"]
            assert client.get(f"/api/v1/laboratories/{labs[0]}").status_code == 200
            assert client.get(f"/api/v1/laboratories/{labs[1]}").status_code == 403
            assert client.get("/api/v1/users").status_code == 403
            print("Live permission denial and laboratory isolation: PASS")
            assert client.post("/api/v1/auth/logout").status_code == 204
            assert client.get("/api/v1/auth/me").status_code == 401
            assert client.post("/api/v1/auth/logout").status_code == 204
            print("Live logout/revocation: PASS")
    finally:
        if server.poll() is None:
            server.terminate()
            try:
                server.wait(timeout=10)
            except subprocess.TimeoutExpired:
                server.kill()
                server.wait()


if __name__ == "__main__":
    main()
