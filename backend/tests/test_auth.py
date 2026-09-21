import asyncio
from datetime import UTC, datetime, timedelta
from uuid import uuid4

import httpx
import pytest
from sqlalchemy import select

from app.core.security import digest
from app.models import AuditEvent, RefreshSession
from tests.conftest import login

pytestmark = pytest.mark.asyncio


async def test_login_me_rotation_logout(client, world):
    response = await login(client, world, "viewer")
    assert "refresh_token" not in response.json()
    cookies = response.headers.get_list("set-cookie")
    assert any("HttpOnly" in c and "Secure" in c and "SameSite=strict" in c for c in cookies)
    assert response.headers["cache-control"] == "no-store"
    old = client.cookies["sih_refresh"]
    me = await client.get("/api/v1/auth/me")
    assert me.status_code == 200
    assert me.json()["global_permissions"] == []
    assert [x["laboratory_id"] for x in me.json()["laboratories"]] == [str(world.labs[0].id)]
    refresh = await client.post("/api/v1/auth/refresh")
    assert refresh.status_code == 200, refresh.text
    assert old != client.cookies["sih_refresh"]
    async with world.factory() as session:
        row = await session.scalar(
            select(RefreshSession).where(RefreshSession.token_digest == digest(old))
        )
        assert row.consumed_at and row.replaced_by_session_id
        assert row.token_digest != old
    client.headers["Authorization"] = "Bearer " + refresh.json()["access_token"]
    client.headers["X-CSRF-Token"] = client.cookies["sih_csrf"]
    assert (await client.post("/api/v1/auth/logout")).status_code == 204
    assert (await client.get("/api/v1/auth/me")).status_code == 401
    assert (await client.post("/api/v1/auth/logout")).status_code == 204


async def test_refresh_replay_commits_family_revocation(client, world):
    await login(client, world)
    old, csrf = client.cookies["sih_refresh"], client.cookies["sih_csrf"]
    assert (await client.post("/api/v1/auth/refresh")).status_code == 200
    new = client.cookies["sih_refresh"]
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=world.app),
        base_url="https://test.local",
        headers={"Origin": "https://test.local", "X-CSRF-Token": csrf},
        cookies={"sih_refresh": old, "sih_csrf": csrf},
    ) as replay:
        result = await replay.post("/api/v1/auth/refresh")
        assert result.status_code == 401 and result.json()["error"]["code"] == "REFRESH_REPLAY"
    client.headers["X-CSRF-Token"] = client.cookies["sih_csrf"]
    assert (await client.post("/api/v1/auth/refresh")).status_code == 401
    async with world.factory() as session:
        successor = await session.scalar(
            select(RefreshSession).where(RefreshSession.token_digest == digest(new))
        )
        assert successor.revoked_at is not None
        audits = (
            await session.scalars(
                select(AuditEvent).where(AuditEvent.actor_id == world.users["admin"].id)
            )
        ).all()
        assert any(a.action == "auth.refresh_replay" for a in audits)
        assert all(old not in str(a.after_json) and new not in str(a.after_json) for a in audits)


async def test_concurrent_refresh_has_one_successor_and_revokes_replay(client, world):
    await login(client, world)
    secret, csrf = client.cookies["sih_refresh"], client.cookies["sih_csrf"]

    async def rotate():
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=world.app),
            base_url="https://test.local",
            headers={"Origin": "https://test.local", "X-CSRF-Token": csrf},
            cookies={"sih_refresh": secret, "sih_csrf": csrf},
        ) as c:
            return await c.post("/api/v1/auth/refresh")

    responses = await asyncio.gather(rotate(), rotate())
    assert sorted(r.status_code for r in responses) == [200, 401]
    async with world.factory() as session:
        old = await session.scalar(
            select(RefreshSession).where(RefreshSession.token_digest == digest(secret))
        )
        children = (
            await session.scalars(
                select(RefreshSession).where(RefreshSession.parent_session_id == old.id)
            )
        ).all()
        assert len(children) == 1 and children[0].revoked_at is not None


async def test_invalid_login_rate_limit_and_durable_audit(client, world):
    world.settings.login_limit = 2
    for _ in range(2):
        response = await client.post(
            "/api/v1/auth/login",
            json={"email": world.users["admin"].email, "password": "incorrect"},
        )
        assert response.status_code == 401
        assert "incorrect" not in response.text
    assert (
        await client.post(
            "/api/v1/auth/login",
            json={"email": world.users["admin"].email, "password": "incorrect"},
        )
    ).status_code == 429
    async with world.factory() as session:
        events = (
            await session.scalars(
                select(AuditEvent).where(
                    AuditEvent.actor_id == world.users["admin"].id,
                    AuditEvent.action == "auth.login_failed",
                )
            )
        ).all()
        assert len(events) == 2


@pytest.mark.parametrize("case", ["origin", "csrf", "missing"])
async def test_csrf_and_origin(client, world, case):
    await login(client, world)
    if case == "origin":
        client.headers["Origin"] = "https://evil.example"
    elif case == "csrf":
        client.headers["X-CSRF-Token"] = "bad"
    else:
        del client.headers["X-CSRF-Token"]
    assert (await client.post("/api/v1/auth/refresh")).status_code == 403


async def test_logout_all_and_owned_family_revocation(client, world):
    await login(client, world)
    first = (await client.get("/api/v1/auth/sessions")).json()["items"][0]
    await login(client, world)
    path = "/api/v1/auth/sessions/" + first["family_id"]
    assert (await client.delete(path)).status_code == 428
    assert (await client.delete(path, headers={"If-Match": '"wrong"'})).status_code == 412
    assert (await client.delete(path, headers={"If-Match": first["etag"]})).status_code == 204
    assert (
        await client.delete("/api/v1/auth/sessions/" + str(uuid4()), headers={"If-Match": '"1"'})
    ).status_code == 404
    assert (await client.post("/api/v1/auth/logout-all")).status_code == 204
    assert (await client.get("/api/v1/auth/me")).status_code == 401
    async with world.factory() as session:
        rows = (
            await session.scalars(
                select(RefreshSession).where(RefreshSession.user_id == world.users["admin"].id)
            )
        ).all()
        assert all(r.revoked_at for r in rows)


async def test_password_change_reset_disable_and_expiry(client, world):
    await login(client, world, "viewer")
    match = (await client.get("/api/v1/auth/me")).headers["etag"]
    replacement = "a different synthetic password"
    response = await client.post(
        "/api/v1/auth/password",
        json={"current_password": world.password, "new_password": replacement},
        headers={"If-Match": match},
    )
    assert response.status_code == 204
    assert (await client.get("/api/v1/auth/me")).status_code == 401
    assert (
        await client.post(
            "/api/v1/auth/login",
            json={"email": world.users["viewer"].email, "password": world.password},
        )
    ).status_code == 401
    logged = await client.post(
        "/api/v1/auth/login", json={"email": world.users["viewer"].email, "password": replacement}
    )
    assert logged.status_code == 200
    viewer_token = logged.json()["access_token"]
    await login(client, world)
    users = (
        await client.get("/api/v1/users", params={"search": world.users["viewer"].email})
    ).json()["items"]
    target = users[0]
    assert (
        await client.post(
            f"/api/v1/users/{target['id']}/reset-password",
            json={"new_password": world.password},
            headers={"If-Match": f'"{target["lock_version"]}"'},
        )
    ).status_code == 204
    assert (
        await client.get("/api/v1/auth/me", headers={"Authorization": "Bearer " + viewer_token})
    ).status_code == 401
    target = (
        await client.get("/api/v1/users", params={"search": world.users["viewer"].email})
    ).json()["items"][0]
    assert (
        await client.patch(
            f"/api/v1/users/{target['id']}",
            json={"is_active": False},
            headers={"If-Match": f'"{target["lock_version"]}"'},
        )
    ).status_code == 200
    assert (
        await client.post(
            "/api/v1/auth/login",
            json={"email": world.users["viewer"].email, "password": world.password},
        )
    ).status_code == 401


async def test_expired_refresh_and_family_cap(client, world):
    await login(client, world)
    secret = client.cookies["sih_refresh"]
    async with world.factory() as session, session.begin():
        row = await session.scalar(
            select(RefreshSession).where(RefreshSession.token_digest == digest(secret))
        )
        row.created_at = datetime.now(UTC) - timedelta(days=8)
        row.expires_at = datetime.now(UTC) - timedelta(seconds=1)
    assert (await client.post("/api/v1/auth/refresh")).status_code == 401
    await login(client, world)
    secret = client.cookies["sih_refresh"]
    cap = datetime.now(UTC) + timedelta(hours=1)
    async with world.factory() as session, session.begin():
        row = await session.scalar(
            select(RefreshSession).where(RefreshSession.token_digest == digest(secret))
        )
        row.expires_at = cap
        row.family_expires_at = cap
    assert (await client.post("/api/v1/auth/refresh")).status_code == 200
    new = client.cookies["sih_refresh"]
    async with world.factory() as session:
        row = await session.scalar(
            select(RefreshSession).where(RefreshSession.token_digest == digest(new))
        )
        assert row.expires_at == cap and row.family_expires_at == cap


async def test_no_input_secret_leak_and_duplicate_json(client, world):
    response = await client.post(
        "/api/v1/auth/login",
        json={"email": "invalid", "password": "sensitive-secret", "extra": "secret"},
    )
    assert response.status_code == 422 and "sensitive-secret" not in response.text
    response = await client.post(
        "/api/v1/auth/login",
        content='{"email":"x","email":"y","password":"sensitive-secret"}',
        headers={"Content-Type": "application/json"},
    )
    assert response.status_code == 422 and "sensitive-secret" not in response.text
