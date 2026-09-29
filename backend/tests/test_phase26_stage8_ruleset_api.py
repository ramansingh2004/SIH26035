import pytest

from tests.conftest import login

pytestmark = pytest.mark.asyncio


async def test_stage8_v3_ruleset_is_registerable_through_public_api(
    client,
    world,
):
    await login(client, world, "admin")

    response = await client.post(
        "/api/v1/rulesets",
        json={"artifact": "sih26035_full_flow_demo_v3"},
    )

    assert response.status_code == 201, response.text
    ruleset = response.json()

    assert ruleset["version"] == "SYNTHETIC_TEST_SIH26035_FULL_FLOW_V3"
    assert ruleset["edition"] == "SIH-FULL-DEMO-v3"
    assert ruleset["ruleset_status"] == "DRAFT"
    assert ruleset["validation_summary"]["synthetic_demo_only"] is True
    assert ruleset["validation_summary"]["authoritative"] is False


async def test_ruleset_registration_schema_rejects_unknown_artifacts(
    client,
    world,
):
    await login(client, world, "admin")

    response = await client.post(
        "/api/v1/rulesets",
        json={"artifact": "not-a-trusted-artifact"},
    )

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "INVALID_INPUT"
