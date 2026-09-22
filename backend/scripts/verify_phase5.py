"""Real PostgreSQL/Uvicorn candidate-safety acceptance. No synthetic bypass."""

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
from app.services.rulesets import seed_phase3
from scripts.verify_phase1 import prepare


def expect(response, status=200):
    assert response.status_code == status, f"HTTP {response.status_code}, expected {status}"
    return response


async def preflight(settings):
    engine = create_database_engine(settings)
    try:
        async with engine.connect() as connection:
            assert (
                await connection.execute(text("SELECT version_num FROM alembic_version"))
            ).scalar() == "0004_phase5"
            assert (await connection.execute(text("SELECT count(*) FROM users"))).scalar() == 0, (
                "Use a fresh disposable database"
            )
        async with create_session_factory(engine)() as session:
            return await seed_phase3(session)
    finally:
        await engine.dispose()


def exercise(client, email, password, ruleset_id):
    def login(address):
        response = expect(
            client.post("/api/v1/auth/login", json={"email": address, "password": password})
        )
        client.headers["Authorization"] = "Bearer " + response.json()["access_token"]
        client.headers["X-CSRF-Token"] = client.cookies["sih_csrf"]
        expect(client.get("/api/v1/auth/me"))

    expect(client.get("/health"))
    for path in ("/docs", "/redoc", "/openapi.json"):
        expect(client.get(path))
    login(email)
    expect(client.get("/api/v1/test-sessions"), 403)
    labs = []
    for _ in range(2):
        result = expect(
            client.post(
                "/api/v1/laboratories",
                json=dict(
                    name="Phase 5 verification",
                    code=uuid4().hex,
                    address_line1="Address",
                    address_line2="",
                    city="City",
                    state="State",
                    postal_code="100001",
                    country="India",
                    phone="0000000000",
                    email="lab@example.com",
                    accreditation_no="TEST",
                ),
            ),
            201,
        )
        labs.append(result.json()["id"])
    users = {}
    for name, role, lab in (
        ("engineer", "LAB_ENGINEER", labs[0]),
        ("viewer", "VIEWER", labs[0]),
        ("other", "LAB_ENGINEER", labs[1]),
    ):
        address = f"{name}-{uuid4().hex}@example.com"
        expect(
            client.post(
                "/api/v1/users",
                json=dict(
                    email=address,
                    full_name=name,
                    password=password,
                    initial_assignment=dict(
                        role_code=role, scope_type="LABORATORY", laboratory_id=lab
                    ),
                ),
            ),
            201,
        )
        users[name] = address
    login(users["engineer"])
    manufacturer = expect(
        client.post(
            "/api/v1/manufacturers",
            json=dict(
                laboratory_id=labs[0],
                name="Candidate safety manufacturer",
                address={"address_line1": "Address"},
            ),
        ),
        201,
    ).json()
    capacity = dict(
        max_capacity_g="20000",
        min_capacity_g="0",
        verification_interval_e_g="10",
        scale_interval_d_g="10",
    )
    instrument = expect(
        client.post(
            "/api/v1/instruments",
            json=dict(
                laboratory_id=labs[0],
                manufacturer_id=manufacturer["id"],
                model_name="Candidate scale",
                accuracy_class="III",
                range_type="SINGLE",
                indication_type="DIGITAL",
                **capacity,
            ),
        ),
        201,
    )
    expect(
        client.post(
            "/api/v1/instruments/" + instrument.json()["id"] + "/ranges",
            headers={"If-Match": instrument.headers["etag"]},
            json=dict(range_no=1, **capacity),
        ),
        201,
    )
    key = uuid4().hex
    payload = dict(
        instrument_id=instrument.json()["id"],
        rule_set_id=ruleset_id,
        application_number="PHASE5-CANDIDATE",
        evaluation_context="INITIAL_VERIFICATION",
    )
    created = expect(
        client.post("/api/v1/test-sessions", headers={"Idempotency-Key": key}, json=payload), 201
    )
    replay = expect(
        client.post("/api/v1/test-sessions", headers={"Idempotency-Key": key}, json=payload), 201
    )
    assert replay.json() == created.json()
    path = "/api/v1/test-sessions/" + created.json()["id"]
    sections = expect(client.get(path + "/sections")).json()
    assert len(sections) == 17 and {r["section_number"] for r in sections} == set(range(1, 18))
    expect(client.patch(path, json={"notes": "missing ETag"}), 428)
    expect(client.patch(path, headers={"If-Match": '"99"'}, json={"notes": "stale ETag"}), 412)
    configured = expect(
        client.post(
            path + "/configure",
            headers={"If-Match": created.headers["etag"]},
            json={"instrument_snapshot": created.json()["instrument_snapshot"]},
        )
    )
    planning = expect(client.post(path + "/applicability")).json()
    assert not planning["confirmable"] and len(planning["plan"]["slots"]) == 28
    assert all(s["decision"]["unresolved_rule_ids"] for s in planning["plan"]["slots"])
    blocked = expect(
        client.post(
            path + "/confirm-applicability",
            headers={"If-Match": configured.headers["etag"]},
            json={"elections": {}},
        ),
        409,
    )
    assert blocked.json()["error"]["code"] == "TODO_REGULATORY_VALIDATION"
    assert expect(client.get(path + "/requirements")).json() == []
    expect(
        client.post(path + "/start-testing", headers={"If-Match": configured.headers["etag"]}), 409
    )
    revision = expect(
        client.post(
            path + "/revisions",
            headers={"If-Match": configured.headers["etag"], "Idempotency-Key": uuid4().hex},
            json={"reason": "Fresh configuration required"},
        ),
        201,
    )
    assert revision.json()["session_revision_no"] == 2
    assert expect(client.get(path)).json() == configured.json()
    login(users["viewer"])
    expect(client.get(path))
    expect(
        client.patch(
            path, headers={"If-Match": configured.headers["etag"]}, json={"notes": "forbidden"}
        ),
        403,
    )
    login(users["other"])
    expect(client.get(path), 404)
    expect(client.get(path + "/sections"), 404)
    expect(
        client.patch(
            path, headers={"If-Match": configured.headers["etag"]}, json={"notes": "cross-lab"}
        ),
        404,
    )
    refresh = client.cookies["sih_refresh"]
    response = expect(client.post("/api/v1/auth/refresh"))
    assert client.cookies["sih_refresh"] != refresh
    client.headers["Authorization"] = "Bearer " + response.json()["access_token"]
    client.headers["X-CSRF-Token"] = client.cookies["sih_csrf"]
    expect(client.post("/api/v1/auth/logout"), 204)
    expect(client.get("/api/v1/auth/me"), 401)
    print(
        "LIVE_CANDIDATE_SAFETY: PASS "
        "(health/auth/17 sections/gates/scoping/ETags/revisions/refresh/logout)"
    )


async def persistence(settings):
    engine = create_database_engine(settings)
    try:
        async with engine.connect() as connection:
            assert (
                await connection.execute(text("SELECT count(*) FROM test_sessions"))
            ).scalar() == 2
            assert (
                await connection.execute(text("SELECT count(*) FROM test_session_sections"))
            ).scalar() == 34
            for table in ("test_runs", "test_run_results", "session_test_requirements"):
                assert (
                    await connection.execute(text(f"SELECT count(*) FROM {table}"))
                ).scalar() == 0
            actions = list(
                (await connection.execute(text("SELECT action FROM audit_events"))).scalars()
            )
            assert actions.count("session.created") == 1
            assert actions.count("session.configure") == 1
            assert actions.count("session.revision_created") == 1
            assert "session.applicability_confirmed" not in actions
        print("POSTGRESQL_PERSISTENCE_AND_AUDIT: PASS; no candidate regulatory outcome issued")
    finally:
        await engine.dispose()


def main():
    settings = Settings()
    if settings.database_url is None or not make_url(
        settings.database_url.get_secret_value()
    ).database.endswith("_dev"):
        raise RuntimeError("Use a fresh disposable PostgreSQL database ending in _dev")
    ruleset_id = asyncio.run(preflight(settings))
    email, password = f"verify-{uuid4().hex}@example.com", secrets.token_urlsafe(32)
    asyncio.run(prepare(settings, email, password))
    with socket.socket() as probe:
        probe.bind(("127.0.0.1", 0))
        port = probe.getsockname()[1]
    environment = dict(
        os.environ,
        JWT_SECRET=secrets.token_urlsafe(48),
        ENVIRONMENT="development",
        COOKIE_SECURE="false",
        LOGIN_LIMIT="1000",
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
        env=environment,
    )
    try:
        with httpx.Client(
            base_url=f"http://127.0.0.1:{port}",
            headers={"Origin": "http://127.0.0.1:3000"},
            timeout=30,
            trust_env=False,
        ) as client:
            deadline = time.monotonic() + 30
            while True:
                try:
                    expect(client.get("/health"))
                    break
                except httpx.ConnectError:
                    if time.monotonic() >= deadline or server.poll() is not None:
                        raise
                    time.sleep(0.1)
            exercise(client, email, password, ruleset_id)
        asyncio.run(persistence(settings))
    finally:
        server.terminate()
        try:
            server.wait(timeout=10)
        except subprocess.TimeoutExpired:
            server.kill()
            server.wait(timeout=10)


if __name__ == "__main__":
    main()
