"""Live Phase 2 acceptance against a fresh disposable *_dev PostgreSQL database.

Uses generated credentials kept only in memory. Run migrations before this script.
"""

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
from app.db.session import create_database_engine
from scripts.verify_phase1 import prepare


async def check_schema(settings):
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
            assert {
                "manufacturers",
                "instruments",
                "instrument_ranges",
                "instrument_components",
            } <= tables
            assert (
                await connection.execute(text("SELECT version_num FROM alembic_version"))
            ).scalar() == "0002_phase2"
        print("Phase 2 PostgreSQL tables and migration revision: PASS")
    finally:
        await engine.dispose()


def expect(response, status=200):
    assert response.status_code == status, (response.status_code, response.text)
    return response


def main():
    settings = Settings()
    if settings.database_url is None or not make_url(
        settings.database_url.get_secret_value()
    ).database.endswith("_dev"):
        raise RuntimeError("Use a fresh disposable PostgreSQL database ending in _dev")
    email, password = f"verify-{uuid4().hex}@example.com", secrets.token_urlsafe(32)
    asyncio.run(check_schema(settings))
    asyncio.run(prepare(settings, email, password))
    with socket.socket() as probe:
        probe.bind(("127.0.0.1", 0))
        port = probe.getsockname()[1]
    origin = "http://127.0.0.1:3000"
    env = dict(
        os.environ,
        JWT_SECRET=secrets.token_urlsafe(48),
        ENVIRONMENT="development",
        COOKIE_SECURE="false",
        ALLOWED_ORIGINS='["http://127.0.0.1:3000"]',
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
            base_url=f"http://127.0.0.1:{port}", headers={"Origin": origin}, timeout=10
        ) as client:
            deadline = time.monotonic() + 15
            while True:
                try:
                    assert expect(client.get("/health")).json() == {"status": "ok"}
                    break
                except httpx.ConnectError:
                    if time.monotonic() >= deadline or server.poll() is not None:
                        raise
                    time.sleep(0.1)

            def login(address):
                response = expect(
                    client.post("/api/v1/auth/login", json={"email": address, "password": password})
                )
                client.headers["Authorization"] = "Bearer " + response.json()["access_token"]
                client.headers["X-CSRF-Token"] = client.cookies["sih_csrf"]
                expect(client.get("/api/v1/auth/me"))

            login(email)
            expect(client.get("/api/v1/manufacturers"), 403)
            labs = []
            for _ in range(2):
                response = expect(
                    client.post(
                        "/api/v1/laboratories",
                        json={
                            "name": "Verification laboratory",
                            "code": uuid4().hex,
                            "address_line1": "A",
                            "address_line2": "",
                            "city": "City",
                            "state": "State",
                            "postal_code": "100001",
                            "country": "India",
                            "phone": "0000000000",
                            "email": "lab@example.com",
                            "accreditation_no": "TEST",
                        },
                    ),
                    201,
                )
                labs.append(response.json()["id"])
            accounts = {}
            for name, role, lab in [
                ("editor", "ADMIN", labs[0]),
                ("viewer", "VIEWER", labs[0]),
                ("other", "VIEWER", labs[1]),
            ]:
                address = f"{name}-{uuid4().hex}@example.com"
                expect(
                    client.post(
                        "/api/v1/users",
                        json={
                            "email": address,
                            "full_name": name,
                            "password": password,
                            "initial_assignment": {
                                "role_code": role,
                                "scope_type": "LABORATORY",
                                "laboratory_id": lab,
                            },
                        },
                    ),
                    201,
                )
                accounts[name] = address
            login(accounts["editor"])
            manufacturer = expect(
                client.post(
                    "/api/v1/manufacturers",
                    json={
                        "laboratory_id": labs[0],
                        "name": "Live master",
                        "address": {"address_line1": "Address"},
                    },
                ),
                201,
            )
            mid = manufacturer.json()["id"]
            mpath = "/api/v1/manufacturers/" + mid
            expect(client.patch(mpath, json={"name": "Updated"}), 428)
            manufacturer = expect(
                client.patch(mpath, json={"name": "Updated"}, headers={"If-Match": '"1"'})
            )
            expect(client.patch(mpath, json={"name": "Stale"}, headers={"If-Match": '"1"'}), 412)
            payload = {
                "laboratory_id": labs[0],
                "manufacturer_id": mid,
                "model_name": "Live instrument",
                "accuracy_class": "III",
                "max_capacity_g": "10000.000001",
                "min_capacity_g": "0",
                "scale_interval_d_g": "0.1",
                "verification_interval_e_g": "10",
            }
            instrument = expect(client.post("/api/v1/instruments", json=payload), 201)
            assert instrument.json()["verification_intervals_n"] == "1000.0000001"
            ipath = "/api/v1/instruments/" + instrument.json()["id"]
            version = instrument.headers["etag"]
            for kind, child in [
                (
                    "ranges",
                    {
                        "range_no": 1,
                        "max_capacity_g": "10000",
                        "scale_interval_d_g": "0.1",
                        "verification_interval_e_g": "10",
                    },
                ),
                ("components", {"component_type": "Indicator", "notes": "Original"}),
            ]:
                created = expect(
                    client.post(ipath + "/" + kind, json=child, headers={"If-Match": version}), 201
                )
                version = created.headers["x-instrument-etag"]
                path = ipath + "/" + kind + "/" + created.json()["id"]
                patch = {"min_capacity_g": "1"} if kind == "ranges" else {"notes": "Updated"}
                changed = expect(
                    client.patch(path, json=patch, headers={"If-Match": created.headers["etag"]})
                )
                removed = expect(
                    client.delete(
                        path,
                        params={"reason": "Archive smoke fixture"},
                        headers={"If-Match": changed.headers["etag"]},
                    ),
                    204,
                )
                version = removed.headers["x-instrument-etag"]
                assert expect(client.get(ipath + "/" + kind)).json()["total"] == 0
            updated = expect(
                client.patch(
                    ipath, json={"model_name": "Updated master"}, headers={"If-Match": version}
                )
            )
            version = updated.headers["etag"]
            report = expect(
                client.post("/api/v1/instruments/validate-configuration", json=payload)
            ).json()
            assert report["regulatory_validation_status"] == "TODO_REGULATORY_VALIDATION"
            assert (
                expect(
                    client.get(
                        "/api/v1/audit-events", params={"entity_id": instrument.json()["id"]}
                    )
                ).json()["total"]
                == 2
            )
            expect(client.get("/api/v1/manufacturers", params={"laboratory_id": labs[1]}), 403)
            login(accounts["viewer"])
            expect(client.get(ipath))
            expect(
                client.patch(ipath, json={"model_name": "Denied"}, headers={"If-Match": version}),
                403,
            )
            login(accounts["other"])
            expect(client.get(ipath), 404)
            expect(client.get(mpath), 404)
            login(accounts["editor"])
            expect(
                client.post(
                    ipath + "/archive",
                    json={"reason": "Live fixture retired"},
                    headers={"If-Match": version},
                )
            )
            expect(
                client.post(
                    mpath + "/archive",
                    json={"reason": "Live fixture retired"},
                    headers={"If-Match": manufacturer.headers["etag"]},
                )
            )
            original = client.cookies["sih_refresh"]
            refreshed = expect(client.post("/api/v1/auth/refresh"))
            assert client.cookies["sih_refresh"] != original
            client.headers["Authorization"] = "Bearer " + refreshed.json()["access_token"]
            client.headers["X-CSRF-Token"] = client.cookies["sih_csrf"]
            expect(client.post("/api/v1/auth/logout"), 204)
            expect(client.get("/api/v1/auth/me"), 401)
            print(
                "Live health/auth, manufacturer/instrument CRUD, ranges/components, "
                "ETags, audit, permissions, lab isolation and revocation: PASS"
            )
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
