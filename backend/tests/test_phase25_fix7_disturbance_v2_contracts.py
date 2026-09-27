"""Phase 25 Fix 7 structural contracts."""

from pathlib import Path

from app.compliance.parameterized_stage4 import (
    DisturbancePolicyV2,
    DisturbanceProfileV2,
)
from app.compliance.phase10 import disturbance_registrations

REPO = Path(__file__).resolve().parents[2]


def test_fix7_v2_policy_supports_multiple_variants_without_defaults():
    fields = DisturbanceProfileV2.model_fields
    assert fields["minimum_interval_seconds"].default is None
    assert fields["deviation_limit_multiplier_e"].is_required()
    assert fields["deviation_operator"].is_required()
    assert fields["require_evidence"].is_required()
    assert DisturbancePolicyV2.model_fields["profiles"].is_required()


def test_fix7_section12_implementation_identity_is_bumped():
    # Fix 7 established v2 runtime execution. Fix 8 extends the same runtime
    # with conditional RF profile selection, so the implementation identity
    # is intentionally advanced to section12-v3.
    assert {
        item.implementation_version for item in disturbance_registrations()
    } == {"section12-v3"}


def test_fix7_does_not_embed_iec_iso_severity_constants_in_runtime():
    source = (
        REPO / "backend" / "app" / "compliance" / "phase10.py"
    ).read_text(encoding="utf-8")
    for forbidden in (
        "61000-4-2",
        "61000-4-3",
        "61000-4-4",
        "61000-4-5",
        "61000-4-6",
        "61000-4-11",
        "7637-2",
        "7637-3",
        "6 kv",
        "8 kv",
        "10 v/m",
    ):
        assert forbidden not in source.lower()


def test_fix7_candidate_ruleset_remains_non_authoritative():
    metadata = (
        REPO
        / "backend"
        / "app"
        / "compliance"
        / "rules"
        / "oiml_r76_2006"
        / "metadata.yaml"
    ).read_text(encoding="utf-8")
    assert '"version": "candidate-v1"' in metadata
    assert '"supported_test_codes": []' in metadata
