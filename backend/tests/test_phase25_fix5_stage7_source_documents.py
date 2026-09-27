"""Phase 25 Fix 5: Stage 7 document-level controlled-source intake contracts."""

import json
from datetime import timedelta
from pathlib import Path

import pytest
from pydantic import ValidationError

from app.compliance.stage7_activation import (
    Stage7VerificationManifest,
    verified_artifact_blockers,
)
from tests.test_phase25_stage7_complete import synthetic_verified_fixture

REPO = Path(__file__).resolve().parents[2]


def _manifest_value():
    _, manifest = synthetic_verified_fixture()
    value = manifest.model_dump(mode="python")
    value["source_documents"] = list(value["source_documents"])
    return value


def test_stage7_source_families_no_longer_carry_a_single_document_digest():
    _, manifest = synthetic_verified_fixture()

    family = manifest.source_evidence[0]
    assert not hasattr(family, "sha256")
    assert not hasattr(family, "acquired_at")
    assert family.amendment_set_complete is True
    assert manifest.source_documents[0].sha256 == "a" * 64


def test_stage7_manifest_rejects_document_for_unknown_source_family():
    value = _manifest_value()
    value["source_documents"][0]["source_id"] = "UNKNOWN"

    with pytest.raises(ValidationError, match="unknown source family"):
        Stage7VerificationManifest.model_validate(value)


def test_stage7_manifest_rejects_duplicate_document_key():
    value = _manifest_value()
    value["source_documents"].append(dict(value["source_documents"][0]))

    with pytest.raises(ValidationError, match="Duplicate source-document"):
        Stage7VerificationManifest.model_validate(value)


def test_stage7_manifest_requires_at_least_one_document_for_every_family():
    value = _manifest_value()
    value["source_documents"] = value["source_documents"][:-1]

    with pytest.raises(ValidationError, match="Every source family"):
        Stage7VerificationManifest.model_validate(value)


def test_stage7_family_cannot_claim_current_through_after_review_date():
    value = _manifest_value()
    verified_at = value["source_evidence"][0]["verified_at"]
    value["source_evidence"][0]["current_through"] = (
        verified_at.date() + timedelta(days=1)
    )

    with pytest.raises(ValidationError, match="current-through"):
        Stage7VerificationManifest.model_validate(value)


def test_stage7_source_document_must_have_been_acquired_before_family_signoff():
    value = _manifest_value()
    value["source_documents"][0]["acquired_at"] = (
        value["source_evidence"][0]["verified_at"] + timedelta(seconds=1)
    )

    with pytest.raises(ValidationError, match="acquired after"):
        Stage7VerificationManifest.model_validate(value)


def test_stage7_gate_binds_verified_standard_digest_to_exact_document():
    ruleset, manifest = synthetic_verified_fixture()
    value = manifest.model_dump(mode="python")
    value["source_documents"][0]["sha256"] = "f" * 64
    tampered = Stage7VerificationManifest.model_validate(value)

    blockers = verified_artifact_blockers(
        ruleset,
        tampered,
        candidate_ruleset=ruleset,
        production=False,
    )
    assert "STAGE7:SOURCE_DOCUMENT_MISMATCH:SYNTHETIC:TEST" in blockers


def test_stage7_template_separates_source_families_and_source_documents():
    path = (
        REPO
        / "backend"
        / "app"
        / "compliance"
        / "rules"
        / "oiml_r76_2006_verified"
        / "stage7_verification_manifest.template.json"
    )
    value = json.loads(path.read_text(encoding="utf-8"))

    assert len(value["source_evidence"]) == 5
    assert len(value["source_documents"]) == 5
    assert all("sha256" not in item for item in value["source_evidence"])
    assert all("current_through" in item for item in value["source_evidence"])
    assert all("amendment_set_complete" in item for item in value["source_evidence"])
    assert {item["source_id"] for item in value["source_documents"]} == {
        item["source_id"] for item in value["source_evidence"]
    }


def test_stage7_synthetic_contract_still_passes_nonproduction_gate():
    ruleset, manifest = synthetic_verified_fixture()

    assert verified_artifact_blockers(
        ruleset,
        manifest,
        candidate_ruleset=ruleset,
        production=False,
    ) == ()
