"""Real PostgreSQL/API master lifecycle, isolation, concurrency and atomic audit."""

import asyncio
from decimal import Decimal
from uuid import UUID, uuid4

import httpx
import pytest
from sqlalchemy import func, select, text, update
from sqlalchemy.exc import IntegrityError

from app.models import AuditEvent, Instrument, Manufacturer, UserRoleAssignment
from app.services.audit import AuditService
from tests.conftest import login
from tests.test_master_validation import instrument_payload

pytestmark = pytest.mark.asyncio


async def masters(client, world):
    await login(client, world, "local")
    manufacturer = await client.post(
        "/api/v1/manufacturers",
        json={
            "laboratory_id": str(world.labs[0].id),
            "name": "Exact manufacturer",
            "registration_no": "REG-" + uuid4().hex,
            "address": {"address_line1": "Address"},
        },
    )
    assert manufacturer.status_code == 201, manufacturer.text
    instrument = await client.post(
        "/api/v1/instruments", json=instrument_payload(world.labs[0].id, manufacturer.json()["id"])
    )
    assert instrument.status_code == 201, instrument.text
    return manufacturer, instrument


async def test_manufacturer_crud_archive_filters_and_etags(client, world):
    manufacturer, _ = await masters(client, world)
    mid = manufacturer.json()["id"]
    path = f"/api/v1/manufacturers/{mid}"
    assert (await client.get(path)).headers["etag"] == '"1"'
    assert (await client.patch(path, json={"name": "Updated"})).status_code == 428
    assert (
        await client.patch(path, json={"name": "Updated"}, headers={"If-Match": '"9"'})
    ).status_code == 412
    updated = await client.patch(path, json={"name": "Updated"}, headers={"If-Match": '"1"'})
    assert updated.status_code == 200 and updated.headers["etag"] == '"2"'
    listing = await client.get(
        "/api/v1/manufacturers",
        params={"registration_no": manufacturer.json()["registration_no"], "search": "Updated"},
    )
    assert listing.json()["total"] == 1
    archived = await client.post(
        path + "/archive", json={"reason": "Retired"}, headers={"If-Match": '"2"'}
    )
    assert archived.status_code == 200 and archived.json()["is_active"] is False
    assert (
        await client.patch(path, json={"name": "No"}, headers={"If-Match": '"3"'})
    ).status_code == 409
    assert (await client.get(path)).json()["name"] == "Updated"


async def test_instrument_crud_exact_decimal_nulls_and_no_regulatory_claim(client, world):
    manufacturer, instrument = await masters(client, world)
    path = "/api/v1/instruments/" + instrument.json()["id"]
    assert instrument.json()["verification_intervals_n"] == "1000"
    patch = await client.patch(
        path,
        json={"max_capacity_g": "10000.000001", "min_capacity_g": None},
        headers={"If-Match": '"1"'},
    )
    assert patch.status_code == 200, patch.text
    assert patch.json()["max_capacity_g"] == "10000.000001"
    assert patch.json()["verification_intervals_n"] == "1000.0000001"
    assert patch.json()["metadata_json"]["is_direct_sales"] is None
    validation = await client.post(
        "/api/v1/instruments/validate-configuration",
        json=instrument_payload(world.labs[0].id, manufacturer.json()["id"]),
    )
    assert validation.status_code == 200, validation.text
    assert validation.json()["structural_valid"] is True
    assert validation.json()["regulatory_validation_status"] == "TODO_REGULATORY_VALIDATION"
    assert validation.json()["unresolved_rule_ids"] == ["REG-02"]
    history = await client.get(path + "/history")
    assert history.json()["availability"] == "NOT_IMPLEMENTED"
    assert history.json()["sessions"] is None
    archived = await client.post(
        path + "/archive", json={"reason": "Withdrawn"}, headers={"If-Match": '"2"'}
    )
    assert archived.status_code == 200
    assert archived.json()["instrument_status"] == "ARCHIVED"
    assert (
        await client.patch(path, json={"model_name": "No"}, headers={"If-Match": '"3"'})
    ).status_code == 409


@pytest.mark.parametrize(
    "kind,payload,patch",
    [
        (
            "ranges",
            {
                "range_no": 1,
                "max_capacity_g": "10000",
                "min_capacity_g": "0",
                "scale_interval_d_g": "0.1",
                "verification_interval_e_g": "10",
            },
            {"min_capacity_g": "0.1"},
        ),
        (
            "components",
            {
                "component_type": "Load cell",
                "technical_specifications": {"rated_capacity_g": "10000"},
            },
            {"notes": "Updated identity"},
        ),
    ],
)
async def test_child_lifecycle_parent_versions_and_retention(client, world, kind, payload, patch):
    _, instrument = await masters(client, world)
    parent = "/api/v1/instruments/" + instrument.json()["id"]
    collection = parent + "/" + kind
    assert (await client.post(collection, json=payload)).status_code == 428
    created = await client.post(collection, json=payload, headers={"If-Match": '"1"'})
    assert created.status_code == 201, created.text
    assert created.headers["x-instrument-etag"] == '"2"'
    assert (
        await client.patch(parent, json={"model_name": "Stale"}, headers={"If-Match": '"1"'})
    ).status_code == 412
    path = collection + "/" + created.json()["id"]
    changed = await client.patch(path, json=patch, headers={"If-Match": '"1"'})
    assert changed.status_code == 200, changed.text
    assert changed.headers["x-instrument-etag"] == '"3"'
    deleted = await client.delete(
        path, params={"reason": "Superseded master entry"}, headers={"If-Match": '"2"'}
    )
    assert deleted.status_code == 204, deleted.text
    assert deleted.headers["x-instrument-etag"] == '"4"'
    assert (await client.get(collection)).json()["total"] == 0
    retained = await client.get(collection, params={"include_archived": True})
    assert retained.json()["items"][0]["is_active"] is False
    assert (await client.patch(path, json=patch, headers={"If-Match": '"3"'})).status_code == 409


async def test_range_change_cannot_leave_invalid_active_children(client, world):
    _, instrument = await masters(client, world)
    path = "/api/v1/instruments/" + instrument.json()["id"]
    payload = {
        "range_no": 1,
        "max_capacity_g": "10000",
        "scale_interval_d_g": "1",
        "verification_interval_e_g": "10",
    }
    created = await client.post(path + "/ranges", json=payload, headers={"If-Match": '"1"'})
    assert created.status_code == 201
    assert (
        await client.patch(path, json={"max_capacity_g": "9000"}, headers={"If-Match": '"2"'})
    ).status_code == 422
    assert (
        await client.post(path + "/ranges", json=payload, headers={"If-Match": '"2"'})
    ).status_code in (409, 422)
    child = path + "/ranges/" + created.json()["id"]
    assert (
        await client.patch(child, json={"max_capacity_g": "11000"}, headers={"If-Match": '"1"'})
    ).status_code == 422
    assert (await client.get(path)).json()["lock_version"] == 2


@pytest.mark.parametrize("who", ["admin", "viewer", "other", "officer"])
async def test_permission_denial_and_global_admin_has_no_master_wildcard(client, world, who):
    manufacturer, instrument = await masters(client, world)
    await login(client, world, who)
    assert (
        await client.post(
            "/api/v1/manufacturers",
            json={
                "laboratory_id": str(world.labs[0].id),
                "name": "Forbidden",
                "address": {"address_line1": "A"},
            },
        )
    ).status_code == 403
    assert (
        await client.patch(
            "/api/v1/instruments/" + instrument.json()["id"],
            json={"model_name": "Forbidden"},
            headers={"If-Match": '"1"'},
        )
    ).status_code == 403
    if who in {"admin", "other"}:
        assert (
            await client.get("/api/v1/manufacturers/" + manufacturer.json()["id"])
        ).status_code in (403, 404)


async def test_cross_lab_lists_references_and_child_paths(client, world):
    manufacturer, instrument = await masters(client, world)
    other_lab = world.labs[1].id
    async with world.factory() as session, session.begin():
        foreign = Manufacturer(
            id=uuid4(),
            laboratory_id=other_lab,
            name="Foreign",
            address={"schema_version": 1, "address_line1": "A"},
            created_by=world.users["admin"].id,
        )
        session.add(foreign)
    assert (
        await client.get("/api/v1/manufacturers", params={"laboratory_id": str(other_lab)})
    ).status_code == 403
    created = await client.post(
        "/api/v1/instruments", json=instrument_payload(world.labs[0].id, foreign.id)
    )
    assert created.status_code == 404
    changed = await client.patch(
        "/api/v1/instruments/" + instrument.json()["id"],
        json={"manufacturer_id": str(foreign.id)},
        headers={"If-Match": '"1"'},
    )
    assert changed.status_code == 404
    await login(client, world, "other")
    assert (await client.get("/api/v1/instruments")).json()["total"] == 0
    for suffix in ("", "/ranges", "/components", "/history"):
        assert (
            await client.get("/api/v1/instruments/" + instrument.json()["id"] + suffix)
        ).status_code == 404
    assert (
        await client.get("/api/v1/manufacturers/" + manufacturer.json()["id"])
    ).status_code == 404


async def test_database_rejects_cross_lab_fk_and_inconsistent_n(client, world):
    _, instrument = await masters(client, world)
    identifier = UUID(instrument.json()["id"])
    for values in (
        {"laboratory_id": world.labs[1].id},
        {"verification_intervals_n": Decimal("999")},
        {"accuracy_class": "IV"},
    ):
        with pytest.raises(IntegrityError):
            async with world.factory() as session, session.begin():
                await session.execute(
                    update(Instrument).where(Instrument.id == identifier).values(**values)
                )


async def test_same_etag_concurrent_updates_have_one_winner_and_one_audit(client, world):
    _, instrument = await masters(client, world)
    path = "/api/v1/instruments/" + instrument.json()["id"]

    async def change(name):
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=world.app),
            base_url="https://test.local",
            headers=dict(client.headers),
        ) as concurrent:
            return await concurrent.patch(
                path, json={"model_name": name}, headers={"If-Match": '"1"'}
            )

    results = await asyncio.gather(change("A"), change("B"))
    assert sorted(r.status_code for r in results) == [200, 412]
    async with world.factory() as session:
        events = (
            await session.scalars(
                select(AuditEvent).where(
                    AuditEvent.entity_id == UUID(instrument.json()["id"]),
                    AuditEvent.action == "instrument.updated",
                )
            )
        ).all()
    assert len(events) == 1
    assert events[0].source_revision == 1 and events[0].target_revision == 2
    assert events[0].laboratory_id == world.labs[0].id


async def test_audit_failure_rolls_back_master_mutation(client, world, monkeypatch):
    manufacturer, _ = await masters(client, world)

    def fail(*args, **kwargs):
        raise RuntimeError("Simulated audit failure")

    monkeypatch.setattr(AuditService, "record", fail)
    with pytest.raises(RuntimeError, match="Simulated audit"):
        await client.patch(
            "/api/v1/manufacturers/" + manufacturer.json()["id"],
            json={"name": "Rolled back"},
            headers={"If-Match": '"1"'},
        )
    async with world.factory() as session:
        row = await session.get(Manufacturer, UUID(manufacturer.json()["id"]))
        assert row.name == "Exact manufacturer" and row.lock_version == 1


async def test_unknown_fields_rounded_values_and_repeating_n_never_persist(client, world):
    manufacturer, _ = await masters(client, world)
    for changes in (
        {"max_capacity_g": "1.0000001"},
        {"max_capacity_g": 0.1},
        {"verification_intervals_n": "42"},
        {"max_capacity_g": "10", "verification_interval_e_g": "3"},
    ):
        response = await client.post(
            "/api/v1/instruments",
            json=instrument_payload(world.labs[0].id, manufacturer.json()["id"], **changes),
        )
        assert response.status_code == 422, response.text
    async with world.factory() as session:
        assert (
            await session.scalar(
                select(func.count())
                .select_from(Instrument)
                .where(Instrument.manufacturer_id == UUID(manufacturer.json()["id"]))
            )
            == 1
        )


async def test_archived_manufacturer_rejects_new_links_preserves_existing(client, world):
    manufacturer, instrument = await masters(client, world)
    result = await client.post(
        "/api/v1/manufacturers/" + manufacturer.json()["id"] + "/archive",
        json={"reason": "Retired"},
        headers={"If-Match": '"1"'},
    )
    assert result.status_code == 200
    assert (
        await client.post(
            "/api/v1/instruments",
            json=instrument_payload(world.labs[0].id, manufacturer.json()["id"]),
        )
    ).status_code == 409
    result = await client.patch(
        "/api/v1/instruments/" + instrument.json()["id"],
        json={"model_name": "Preserved instrument"},
        headers={"If-Match": '"1"'},
    )
    assert result.status_code == 200


async def test_master_mutations_do_not_create_idempotency_reservations(client, world):
    manufacturer, _ = await masters(client, world)
    async with world.factory() as session:
        assert (
            await session.execute(
                text("SELECT count(*) FROM idempotency_keys WHERE actor_id=:actor"),
                {"actor": world.users["local"].id},
            )
        ).scalar() == 0
    assert manufacturer.status_code == 201


async def test_revoked_grant_denies_unexpired_access_on_master_routes(client, world):
    _, instrument = await masters(client, world)
    async with world.factory() as session, session.begin():
        from datetime import UTC, datetime

        assignment = await session.scalar(
            select(UserRoleAssignment).where(UserRoleAssignment.user_id == world.users["local"].id)
        )
        assignment.revoked_at = datetime.now(UTC)
        assignment.revoked_by = world.users["admin"].id
        assignment.revocation_reason = "Revoked"
    assert (await client.get("/api/v1/instruments/" + instrument.json()["id"])).status_code == 403


async def test_child_parent_binding_and_single_transaction_audit(client, world):
    manufacturer, first = await masters(client, world)
    second = await client.post(
        "/api/v1/instruments", json=instrument_payload(world.labs[0].id, manufacturer.json()["id"])
    )
    assert second.status_code == 201
    collection = "/api/v1/instruments/" + first.json()["id"] + "/components"
    created = await client.post(
        collection, json={"component_type": "Indicator"}, headers={"If-Match": '"1"'}
    )
    assert created.status_code == 201
    child_id = created.json()["id"]
    wrong_path = "/api/v1/instruments/" + second.json()["id"] + "/components/" + child_id
    assert (
        await client.patch(wrong_path, json={"notes": "Wrong parent"}, headers={"If-Match": '"1"'})
    ).status_code == 404
    async with world.factory() as session:
        events = (
            await session.scalars(select(AuditEvent).where(AuditEvent.entity_id == UUID(child_id)))
        ).all()
        assert len(events) == 1
        event = events[0]
        assert event.action == "instrument.components.created"
        assert event.actor_id == world.users["local"].id
        assert event.laboratory_id == world.labs[0].id
        assert event.after_json["data"]["parent_lock_version"] == 2
        assert event.request_id and event.correlation_id == event.request_id


async def test_decimal_persistence_reads_exact_value_in_fresh_transaction(client, world):
    manufacturer, _ = await masters(client, world)
    response = await client.post(
        "/api/v1/instruments",
        json=instrument_payload(
            world.labs[0].id,
            manufacturer.json()["id"],
            max_capacity_g="10000.000001",
            verification_interval_e_g="0.000001",
        ),
    )
    assert response.status_code == 201, response.text
    async with world.factory() as session:
        row = await session.get(Instrument, UUID(response.json()["id"]))
        assert row.max_capacity_g == Decimal("10000.000001")
        assert row.verification_intervals_n == Decimal("10000000001")
    fetched = await client.get("/api/v1/instruments/" + response.json()["id"])
    assert fetched.json()["max_capacity_g"] == "10000.000001"
    assert fetched.json()["verification_intervals_n"] == "10000000001"


async def test_concurrent_child_creation_uses_parent_etag(client, world):
    _, instrument = await masters(client, world)
    path = "/api/v1/instruments/" + instrument.json()["id"] + "/components"

    async def create(name):
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=world.app),
            base_url="https://test.local",
            headers=dict(client.headers),
        ) as concurrent:
            return await concurrent.post(
                path, json={"component_type": name}, headers={"If-Match": '"1"'}
            )

    responses = await asyncio.gather(create("Indicator"), create("Load cell"))
    assert sorted(r.status_code for r in responses) == [201, 412]
    assert (await client.get(path)).json()["total"] == 1
