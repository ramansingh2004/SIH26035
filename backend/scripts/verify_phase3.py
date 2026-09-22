"""Real PostgreSQL/Uvicorn/private-storage acceptance; never substitutes fake storage."""

import asyncio
import hashlib
import os
import secrets
import socket
import subprocess
import sys
import time
from urllib.parse import urlsplit, urlunsplit
from uuid import uuid4

import httpx
from sqlalchemy import text
from sqlalchemy.engine import make_url

from app.core.config import Settings
from app.db.session import create_database_engine, create_session_factory
from app.services.rulesets import seed_phase3
from app.storage.objects import create_storage
from scripts.verify_phase1 import prepare

PDF = b"%PDF-1.4\n1 0 obj << /Type /Catalog >> endobj\n%%EOF\n"


def expect(response, code=200):
    assert response.status_code == code, f"HTTP {response.status_code}; expected {code}"
    return response


async def preflight(settings):
    storage = create_storage(settings)
    await storage.ready()
    engine = create_database_engine(settings)
    try:
        async with engine.connect() as connection:
            assert (
                await connection.execute(text("SELECT version_num FROM alembic_version"))
            ).scalar() == "0004_phase5"
            assert (await connection.execute(text("SELECT count(*) FROM users"))).scalar() == 0, (
                "Use a fresh disposable database"
            )
            tables = set(
                (
                    await connection.execute(
                        text("SELECT tablename FROM pg_tables WHERE schemaname='public'")
                    )
                ).scalars()
            )
            assert {
                "rule_sets",
                "rule_definitions",
                "test_definitions",
                "checklist_rules",
                "test_equipment",
                "attachment_uploads",
                "attachments",
                "attachment_links",
            } <= tables
        async with create_session_factory(engine)() as session:
            await seed_phase3(session)
    finally:
        await engine.dispose()
    print("PostgreSQL 0004_phase5 schema, empty database and private versioned storage: PASS")


def exercise(client, email, password):
    def login(address):
        result = expect(
            client.post("/api/v1/auth/login", json={"email": address, "password": password})
        )
        client.headers["Authorization"] = "Bearer " + result.json()["access_token"]
        client.headers["X-CSRF-Token"] = client.cookies["sih_csrf"]
        expect(client.get("/api/v1/auth/me"))

    login(email)
    for path in ("/docs", "/redoc", "/openapi.json"):
        expect(client.get(path))
    catalog = expect(client.get("/api/v1/rulesets")).json()["items"][0]
    rp = "/api/v1/rulesets/" + catalog["id"]
    assert expect(client.get(rp + "/tests")).json()["total"] == 28
    assert expect(client.get(rp + "/checklist")).json()["total"] == 27
    gated = expect(
        client.post(rp + "/activate", headers={"If-Match": f'"{catalog["lock_version"]}"'}), 409
    )
    assert gated.json()["error"]["code"] == "RULESET_NOT_VERIFIED"
    expect(client.get("/api/v1/test-equipment"), 403)
    labs = []
    for _ in range(2):
        result = expect(
            client.post(
                "/api/v1/laboratories",
                json={
                    "name": "Phase 3 laboratory",
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
        labs.append(result.json()["id"])
    accounts = {}
    for name, role, lab in (
        ("editor", "LAB_TECHNICIAN", labs[0]),
        ("viewer", "VIEWER", labs[0]),
        ("other", "LAB_TECHNICIAN", labs[1]),
    ):
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
    equipment = expect(
        client.post(
            "/api/v1/test-equipment",
            json={
                "laboratory_id": labs[0],
                "category": "Mass standard",
                "calibration_date": "2026-01-01",
                "calibration_due_date": "2027-01-01",
                "metadata_json": {"nominal_mass_g": "1000.000001"},
            },
        ),
        201,
    )
    eid = equipment.json()["id"]
    ep = "/api/v1/test-equipment/" + eid
    expect(client.get(ep))
    expect(client.patch(ep, json={"model": "A"}), 428)
    equipment = expect(
        client.patch(ep, json={"model": "A"}, headers={"If-Match": equipment.headers["etag"]})
    )
    expect(client.patch(ep, json={"model": "B"}, headers={"If-Match": '"1"'}), 412)
    version = equipment.headers["etag"]
    upload = expect(
        client.post(
            "/api/v1/attachments/presign",
            json={
                "laboratory_id": labs[0],
                "entity_type": "test_equipment",
                "entity_id": eid,
                "purpose": "calibration",
                "file_name": "certificate.pdf",
                "content_type": "application/pdf",
                "file_size": len(PDF),
                "sha256": hashlib.sha256(PDF).hexdigest(),
            },
            headers={"If-Match": version},
        ),
        201,
    ).json()
    with httpx.Client(timeout=30, trust_env=False) as storage_client:
        expect(storage_client.put(upload["upload_url"], content=PDF, headers=upload["headers"]))
        # Unsigned URL must not expose the staged object.
        parts = urlsplit(upload["upload_url"])
        unsigned = urlunsplit((parts.scheme, parts.netloc, parts.path, "", ""))
        assert storage_client.get(unsigned).status_code in (401, 403)
    finalized = expect(
        client.post(
            "/api/v1/attachments/complete",
            json={"upload_id": upload["upload_id"]},
            headers={"If-Match": version},
        ),
        201,
    ).json()
    version = finalized["target_etag"]
    ap = "/api/v1/attachments/" + finalized["id"]
    download = expect(client.get(ap + "/download")).json()
    with httpx.Client(timeout=30, trust_env=False) as storage_client:
        data = expect(storage_client.get(download["download_url"])).content
        assert data == PDF and hashlib.sha256(data).hexdigest() == download["sha256"]
        # Reusing the still-valid staging URL cannot overwrite published evidence.
        expect(
            storage_client.put(
                upload["upload_url"],
                content=PDF.replace(b"Catalog", b"catalog"),
                headers=upload["headers"],
            )
        )
        assert expect(storage_client.get(download["download_url"])).content == PDF
        parts = urlsplit(download["download_url"])
        assert storage_client.get(
            urlunsplit((parts.scheme, parts.netloc, parts.path, "", ""))
        ).status_code in (401, 403)
    second = expect(
        client.post(
            "/api/v1/test-equipment", json={"laboratory_id": labs[0], "category": "Second standard"}
        ),
        201,
    )
    expect(
        client.post(
            ap + "/link",
            json={
                "entity_type": "test_equipment",
                "entity_id": second.json()["id"],
                "purpose": "supporting",
            },
            headers={"If-Match": second.headers["etag"]},
        ),
        201,
    )
    expect(client.delete(ap, params={"reason": "Protected"}, headers={"If-Match": '"2"'}), 409)
    # Failed content finalization cannot publish a second attachment.
    bad = expect(
        client.post(
            "/api/v1/attachments/presign",
            json={
                "laboratory_id": labs[0],
                "entity_type": "test_equipment",
                "entity_id": eid,
                "purpose": "invalid",
                "file_name": "invalid.pdf",
                "content_type": "application/pdf",
                "file_size": len(PDF),
                "sha256": "0" * 64,
            },
            headers={"If-Match": version},
        ),
        201,
    ).json()
    with httpx.Client(timeout=30, trust_env=False) as storage_client:
        expect(storage_client.put(bad["upload_url"], content=PDF, headers=bad["headers"]))
    expect(
        client.post(
            "/api/v1/attachments/complete",
            json={"upload_id": bad["upload_id"]},
            headers={"If-Match": version},
        ),
        422,
    )
    login(accounts["viewer"])
    expect(client.get(ep))
    expect(client.patch(ep, json={"model": "Denied"}, headers={"If-Match": version}), 403)
    login(accounts["other"])
    expect(client.get(ep), 404)
    expect(client.get(ap + "/download"), 404)
    other = expect(
        client.post("/api/v1/test-equipment", json={"laboratory_id": labs[1], "category": "Other"}),
        201,
    )
    login(accounts["editor"])
    expect(
        client.post(
            ap + "/link",
            json={
                "entity_type": "test_equipment",
                "entity_id": other.json()["id"],
                "purpose": "cross",
            },
            headers={"If-Match": other.headers["etag"]},
        ),
        404,
    )
    archived = expect(
        client.post(
            ep + "/archive", json={"reason": "Acceptance fixture"}, headers={"If-Match": version}
        )
    )
    expect(
        client.patch(ep, json={"model": "Denied"}, headers={"If-Match": archived.headers["etag"]}),
        409,
    )
    expect(
        client.delete(
            ap + "/links/" + finalized["link_id"],
            params={"reason": "Protected"},
            headers={"If-Match": archived.headers["etag"]},
        ),
        409,
    )
    original = client.cookies["sih_refresh"]
    refreshed = expect(client.post("/api/v1/auth/refresh"))
    assert client.cookies["sih_refresh"] != original
    client.headers["Authorization"] = "Bearer " + refreshed.json()["access_token"]
    client.headers["X-CSRF-Token"] = client.cookies["sih_csrf"]
    expect(client.get("/api/v1/auth/me"))
    expect(client.post("/api/v1/auth/logout"), 204)
    expect(client.get("/api/v1/auth/me"), 401)
    print(
        "Live health/auth/catalog/gate, equipment, ETags, permissions/isolation, "
        "real private upload/download/hash, evidence lifecycle, refresh/logout: PASS"
    )


async def persistence_check(settings):
    engine = create_database_engine(settings)
    try:
        async with engine.connect() as connection:
            assert (
                await connection.execute(text("SELECT count(*) FROM attachments"))
            ).scalar() == 1
            assert (
                await connection.execute(
                    text(
                        "SELECT count(*) FROM attachment_uploads WHERE upload_status='FAILED' "
                        "AND completed_attachment_id IS NULL"
                    )
                )
            ).scalar() == 1
            actions = set(
                (await connection.execute(text("SELECT action FROM audit_events"))).scalars()
            )
            assert {
                "attachment.finalized",
                "attachment.linked",
                "attachment.finalization_failed",
                "equipment.created",
                "equipment.updated",
                "equipment.archived",
            } <= actions
            events = str(
                (
                    await connection.execute(
                        text("SELECT before_json, after_json FROM audit_events")
                    )
                ).all()
            )
            assert (
                "X-Amz-Signature" not in events
                and "upload_url" not in events
                and "download_url" not in events
            )
        print("PostgreSQL publication rollback, attachment identity, audit and URL redaction: PASS")
    finally:
        await engine.dispose()


def main():
    settings = Settings()
    if settings.database_url is None or not make_url(
        settings.database_url.get_secret_value()
    ).database.endswith("_dev"):
        raise RuntimeError("Use a fresh disposable PostgreSQL database ending in _dev")
    asyncio.run(preflight(settings))
    email, password = f"verify-{uuid4().hex}@example.com", secrets.token_urlsafe(32)
    asyncio.run(prepare(settings, email, password))
    with socket.socket() as probe:
        probe.bind(("127.0.0.1", 0))
        port = probe.getsockname()[1]
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
            base_url=f"http://127.0.0.1:{port}",
            headers={"Origin": "http://127.0.0.1:3000"},
            timeout=60,
            trust_env=False,
        ) as client:
            deadline = time.monotonic() + 20
            while True:
                try:
                    assert expect(client.get("/health")).json() == {"status": "ok"}
                    break
                except httpx.ConnectError:
                    if time.monotonic() >= deadline or server.poll() is not None:
                        raise
                    time.sleep(0.1)
            exercise(client, email, password)
        asyncio.run(persistence_check(settings))
    finally:
        if server.poll() is None:
            server.terminate()
            try:
                server.wait(timeout=10)
            except subprocess.TimeoutExpired:
                server.kill()
                server.wait(timeout=10)
        # Windows TerminateProcess and POSIX SIGTERM have different return codes.
        # Acceptance is determined by assertions above, not termination return code.


if __name__ == "__main__":
    main()
