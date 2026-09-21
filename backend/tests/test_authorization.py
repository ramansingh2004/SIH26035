import asyncio

import pytest

from app.core.errors import AppError
from app.models import UserRoleAssignment
from app.repositories.identity import IdentityRepository
from app.services.authorization import AuthorizationService
from tests.conftest import login

pytestmark = pytest.mark.asyncio


async def test_laboratory_isolation_and_permission_denial(client, world):
    await login(client, world, "viewer")
    response = await client.get("/api/v1/laboratories")
    assert response.status_code == 200
    assert [r["id"] for r in response.json()["items"]] == [str(world.labs[0].id)]
    assert (await client.get(f"/api/v1/laboratories/{world.labs[1].id}")).status_code == 403
    assert (await client.get("/api/v1/users")).status_code == 403
    assert (
        await client.patch(
            f"/api/v1/laboratories/{world.labs[0].id}",
            json={"name": "Changed"},
            headers={"If-Match": '"1"'},
        )
    ).status_code == 403
    await login(client, world, "local")
    assert (
        await client.get("/api/v1/users", params={"laboratory_id": str(world.labs[1].id)})
    ).status_code == 403
    users = (await client.get("/api/v1/users")).json()["items"]
    assert str(world.users["other"].id) not in {u["id"] for u in users}
    assert (
        await client.patch(
            f"/api/v1/users/{world.users['other'].id}",
            json={"full_name": "Blocked"},
            headers={"If-Match": '"1"'},
        )
    ).status_code == 403


async def test_admin_has_no_approval_wildcard_and_multi_role_scope(client, world):
    await login(client, world)
    before = (await client.get("/api/v1/auth/me")).json()
    assert "approval:finalize" not in before["global_permissions"]
    assert "observation:read" not in before["global_permissions"]
    assert before["laboratories"] == []
    async with world.factory() as session:
        grants = await AuthorizationService(IdentityRepository(session)).for_user(
            world.users["admin"].id
        )
        with pytest.raises(AppError):
            grants.require("approval:finalize", world.labs[0].id)
    result = await client.post(
        f"/api/v1/users/{world.users['admin'].id}/role-assignments",
        json={
            "role_code": "APPROVING_OFFICER",
            "scope_type": "LABORATORY",
            "laboratory_id": str(world.labs[0].id),
        },
        headers={"If-Match": f'"{before["lock_version"]}"'},
    )
    assert result.status_code == 201, result.text
    after = (await client.get("/api/v1/auth/me")).json()
    assert "approval:finalize" in after["laboratories"][0]["permissions"]
    assert "report:issue" in after["laboratories"][0]["permissions"]
    async with world.factory() as session:
        grants = await AuthorizationService(IdentityRepository(session)).for_user(
            world.users["admin"].id
        )
        with pytest.raises(AppError):
            grants.require("approval:finalize", world.labs[1].id)


async def test_revoked_grant_takes_effect_without_jwt_expiry(client, world):
    await login(client, world, "viewer")
    viewer_jwt = client.headers["Authorization"]
    await login(client, world)
    path = f"/api/v1/users/{world.users['viewer'].id}/role-assignments"
    row = (await client.get(path)).json()["items"][0]
    assert (
        await client.delete(
            path + "/" + row["id"],
            params={"reason": "Removed lab access"},
            headers={"If-Match": f'"{row["lock_version"]}"'},
        )
    ).status_code == 204
    assert (
        await client.get(
            f"/api/v1/laboratories/{world.labs[0].id}", headers={"Authorization": viewer_jwt}
        )
    ).status_code == 403
    me = await client.get("/api/v1/auth/me", headers={"Authorization": viewer_jwt})
    assert me.status_code == 200 and me.json()["laboratories"] == []


async def test_lab_admin_cannot_assign_outside_scope_or_reset_shared_user(client, world):
    await login(client, world, "local")
    target = world.users["viewer"]
    for data in [
        {"role_code": "ADMIN", "scope_type": "GLOBAL"},
        {"role_code": "VIEWER", "scope_type": "LABORATORY", "laboratory_id": str(world.labs[1].id)},
    ]:
        result = await client.post(
            f"/api/v1/users/{target.id}/role-assignments", json=data, headers={"If-Match": '"1"'}
        )
        assert result.status_code == 403
    async with world.factory() as session, session.begin():
        session.add(
            UserRoleAssignment(
                user_id=target.id,
                role_id=world.roles["VIEWER"],
                scope_type="LABORATORY",
                laboratory_id=world.labs[1].id,
                assigned_by=world.users["admin"].id,
            )
        )
    assert (
        await client.post(
            f"/api/v1/users/{target.id}/reset-password",
            json={"new_password": world.password},
            headers={"If-Match": '"1"'},
        )
    ).status_code == 403


async def test_etag_conflicts_and_concurrent_updates(client, world):
    await login(client, world)
    path = f"/api/v1/laboratories/{world.labs[0].id}"
    original = await client.get(path)
    assert (await client.patch(path, json={"name": "One"})).status_code == 428
    assert (
        await client.patch(path, json={"name": "One"}, headers={"If-Match": '"0"'})
    ).status_code == 412
    headers = {"If-Match": original.headers["etag"]}
    results = await asyncio.gather(
        client.patch(path, json={"name": "Winner A"}, headers=headers),
        client.patch(path, json={"name": "Winner B"}, headers=headers),
    )
    assert sorted(r.status_code for r in results) == [200, 412]
    events = await client.get("/api/v1/audit-events", params={"entity_id": str(world.labs[0].id)})
    assert len([e for e in events.json()["items"] if e["action"] == "laboratory.updated"]) == 1


async def test_user_create_assignment_is_atomic_and_secrets_hidden(client, world):
    await login(client, world, "local")
    payload = {
        "email": "new-" + str(world.labs[0].id) + "@example.com",
        "full_name": "New user",
        "password": world.password,
        "initial_assignment": {
            "role_code": "VIEWER",
            "scope_type": "LABORATORY",
            "laboratory_id": str(world.labs[0].id),
        },
    }
    result = await client.post("/api/v1/users", json=payload)
    assert result.status_code == 201, result.text
    assert world.password not in result.text and "password_hash" not in result.text
    duplicate = await client.post("/api/v1/users", json=payload)
    assert duplicate.status_code == 409 and world.password not in duplicate.text
    assignments = await client.get(f"/api/v1/users/{result.json()['id']}/role-assignments")
    assert len(assignments.json()["items"]) == 1
    payload["email"] = "blocked-" + str(world.labs[0].id) + "@example.com"
    payload["initial_assignment"]["laboratory_id"] = str(world.labs[1].id)
    assert (await client.post("/api/v1/users", json=payload)).status_code == 403
    assert not (await client.get("/api/v1/users", params={"search": payload["email"]})).json()[
        "items"
    ]


async def test_inactive_lab_removes_grants(client, world):
    await login(client, world, "viewer")
    token = client.headers["Authorization"]
    await login(client, world)
    path = f"/api/v1/laboratories/{world.labs[0].id}"
    tag = (await client.get(path)).headers["etag"]
    assert (
        await client.patch(path, json={"is_active": False}, headers={"If-Match": tag})
    ).status_code == 200
    result = await client.get("/api/v1/auth/me", headers={"Authorization": token})
    assert result.status_code == 200 and result.json()["laboratories"] == []


async def test_audit_scope_and_role_listing(client, world):
    await login(client, world)
    path = f"/api/v1/laboratories/{world.labs[1].id}"
    tag = (await client.get(path)).headers["etag"]
    assert (
        await client.patch(path, json={"name": "Other lab"}, headers={"If-Match": tag})
    ).status_code == 200
    await login(client, world, "local")
    result = await client.get(
        "/api/v1/audit-events", params={"laboratory_id": str(world.labs[1].id)}
    )
    assert result.status_code == 403
    roles = (await client.get("/api/v1/roles")).json()["items"]
    assert len(roles) == 6
    admin = next(r for r in roles if r["code"] == "ADMIN")
    assert "approval:finalize" not in admin["laboratory_permissions"]
    assert "laboratory:create" not in admin["laboratory_permissions"]
