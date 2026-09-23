"""Phase 13 Stage 2 synthetic candidate-checklist integration fixture.

This fixture deliberately adds TODO_REGULATORY_VALIDATION checklist rows to
the accepted Phase 12 synthetic ruleset. It does not establish regulatory
authority and is imported only by tests.
"""

from app.compliance.ruleset import RuleSet
from app.services.rulesets import RulesetService
from domain_tests.fixtures.synthetic import SOURCE
from tests.phase12_fixtures import (
    phase12_fixture_rules,
    prepare_phase12_world,
)


def phase13_stage2_fixture_rules() -> RuleSet:
    payload = phase12_fixture_rules().model_dump(mode="json")
    payload["metadata"]["version"] = "SYNTHETIC_TEST_PHASE13_STAGE2"
    payload["metadata"]["edition"] = "TEST-PHASE13-STAGE2-v1"
    payload["checklist"] = [
        {
            "key": "GENERAL_SYNTHETIC_CANDIDATE",
            "group": "GENERAL",
            "text": (
                "SYNTHETIC TEST FIXTURE ONLY - candidate general checklist row; "
                "not regulatory wording."
            ),
            "source": SOURCE,
            "evidence_required": None,
        },
        {
            "key": "DIRECT_SALES_SYNTHETIC_CANDIDATE",
            "group": "DIRECT_SALES",
            "text": (
                "SYNTHETIC TEST FIXTURE ONLY - candidate direct-sales checklist "
                "row; not regulatory wording."
            ),
            "source": SOURCE,
            "evidence_required": None,
        },
        {
            "key": "ELECTRONIC_SYNTHETIC_CANDIDATE",
            "group": "ELECTRONIC",
            "text": (
                "SYNTHETIC TEST FIXTURE ONLY - candidate electronic checklist row; "
                "not regulatory wording."
            ),
            "source": SOURCE,
            "evidence_required": None,
        },
        {
            "key": "SOFTWARE_SYNTHETIC_CANDIDATE",
            "group": "SOFTWARE_CONTROLLED",
            "text": (
                "SYNTHETIC TEST FIXTURE ONLY - candidate software checklist row; "
                "not regulatory wording."
            ),
            "source": SOURCE,
            "evidence_required": None,
        },
    ]
    return RuleSet.model_validate(payload)


async def install_phase13_stage2_synthetic(world, monkeypatch):
    from app.services import rulesets as service_module
    from app.services.audit import RequestContext

    fixture = phase13_stage2_fixture_rules()
    with monkeypatch.context() as patch:
        patch.setattr(service_module, "load_ruleset", lambda: fixture)
        async with world.factory() as session, session.begin():
            row = await RulesetService(
                session,
                RequestContext(),
            ).insert_artifact()
            row.ruleset_status = "ACTIVE"
            row.validation_summary = {
                "authoritative": True,
                "SYNTHETIC_TEST_FIXTURE_ONLY": True,
                "checklist_regulatory_status": "TODO_REGULATORY_VALIDATION",
            }
            world.synthetic_ruleset_id = str(row.id)


async def prepare_phase13_stage2_world(world, monkeypatch):
    world = await prepare_phase12_world(world, monkeypatch)
    await install_phase13_stage2_synthetic(world, monkeypatch)
    return world
