from app.compliance.full_demo import (
    FULL_DEMO_ARTIFACT,
    FULL_DEMO_VERSION,
    is_full_demo_ruleset,
)
from app.services.rulesets import (
    _trusted_artifact,
    _trusted_snapshot,
    _validation_summary,
)


def test_full_demo_is_a_trusted_server_artifact_but_never_authoritative():
    ruleset, manifest = _trusted_artifact(FULL_DEMO_ARTIFACT)

    assert manifest is None
    assert ruleset.metadata.version == FULL_DEMO_VERSION
    assert is_full_demo_ruleset(ruleset)

    trusted, trusted_manifest = _trusted_snapshot(ruleset)
    assert trusted_manifest is None
    assert trusted.configuration_hash == ruleset.configuration_hash

    summary = _validation_summary(ruleset)
    assert summary["structurally_valid"] is True
    assert summary["authoritative"] is False
    assert summary["synthetic_demo_only"] is True
    assert summary["blockers"] == ["SYNTHETIC_DEMO_ONLY"]
