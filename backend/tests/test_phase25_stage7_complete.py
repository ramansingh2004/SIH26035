"""Phase 25 Stage 7 one-step engineering acceptance contracts."""

import json
from datetime import UTC, date, datetime
from pathlib import Path

import pytest

from app.compliance.phase8 import voltage_variation_registration
from app.compliance.ruleset import RuleSet, load_ruleset
from app.compliance.runtime_binding import runtime_binding_hash
from app.compliance.stage7_activation import (
    REQUIRED_REGISTERS,
    REQUIRED_SOURCE_IDS,
    VERIFIED_ARTIFACT,
    Stage7VerificationManifest,
    inspect_verified_artifact,
    verified_artifact_blockers,
)
from app.compliance.suite import implemented_registry
from app.schemas.foundations import RuleRegistration
from scripts.verify_phase25_stage7 import verify_stage7

REPO = Path(__file__).resolve().parents[2]


def synthetic_verified_fixture():
    verified_at = datetime(2026, 9, 27, 12, 0, tzinfo=UTC)
    source = {
        "part": "SYNTHETIC",
        "edition": "TEST",
        "identity": "SYNTHETIC STAGE7 FIXTURE",
        "clause": "TEST-1",
        "digest": "a" * 64,
    }
    verification = {
        "status": "VERIFIED",
        "verified_by": "independent-test-verifier",
        "verified_at": verified_at,
        "evidence": "synthetic-item-evidence",
    }
    ruleset = RuleSet.model_validate(
        {
            "metadata": {
                "schema_version": 1,
                "standard_code": "OIML_R76",
                "standard_name": "SYNTHETIC STAGE7 TEST FIXTURE",
                "edition": "R76-1:2006 / R76-2:2007",
                "version": "verified-v1",
                "standard_parts": [source],
                "supported_test_codes": ["WEIGHING_PERFORMANCE"],
                "source_reference": "SYNTHETIC STAGE7 TEST FIXTURE ONLY",
            },
            "rules": [
                {
                    "key": "SYNTHETIC_STAGE7_RULE",
                    "section": 1,
                    "kind": "dependency_v1",
                    "description": "synthetic Stage 7 fixture",
                    "source": source,
                    "verification": verification,
                    "dependencies": [],
                    "blockers": [],
                    "parameters": [],
                }
            ],
            "tests": [
                {
                    "code": "WEIGHING_PERFORMANCE",
                    "section": 1,
                    "name": "Synthetic weighing",
                    "source": source,
                    "dependencies": ["SYNTHETIC_STAGE7_RULE"],
                    "implemented": True,
                    "verification": verification,
                }
            ],
            "checklist": [],
        }
    )

    source_evidence = [
        {
            "source_id": "SYNTHETIC-1",
            "part": "SYNTHETIC",
            "edition": "TEST",
            "identity": "SYNTHETIC SOURCE FAMILY 1",
            "official_url": "https://example.invalid/synthetic-stage7",
            "current_through": date(2026, 9, 27),
            "amendment_set_complete": True,
            "verified_by": "independent-test-verifier",
            "verified_at": verified_at,
            "evidence_reference": "synthetic-source-evidence",
            "independent_of_implementation": True,
        },
        {
            "source_id": "SYNTHETIC-2",
            "part": "SYNTHETIC-EXTRA",
            "edition": "TEST",
            "identity": "SYNTHETIC SOURCE FAMILY 2",
            "official_url": "https://example.invalid/synthetic-stage7-extra",
            "current_through": date(2026, 9, 27),
            "amendment_set_complete": True,
            "verified_by": "independent-test-verifier",
            "verified_at": verified_at,
            "evidence_reference": "synthetic-source-evidence-2",
            "independent_of_implementation": True,
        },
        {
            "source_id": "SYNTHETIC-3",
            "part": "SYNTHETIC-EXTRA-3",
            "edition": "TEST",
            "identity": "SYNTHETIC SOURCE FAMILY 3",
            "official_url": "https://example.invalid/synthetic-stage7-extra-3",
            "current_through": date(2026, 9, 27),
            "amendment_set_complete": True,
            "verified_by": "independent-test-verifier",
            "verified_at": verified_at,
            "evidence_reference": "synthetic-source-evidence-3",
            "independent_of_implementation": True,
        },
        {
            "source_id": "SYNTHETIC-4",
            "part": "SYNTHETIC-EXTRA-4",
            "edition": "TEST",
            "identity": "SYNTHETIC SOURCE FAMILY 4",
            "official_url": "https://example.invalid/synthetic-stage7-extra-4",
            "current_through": date(2026, 9, 27),
            "amendment_set_complete": True,
            "verified_by": "independent-test-verifier",
            "verified_at": verified_at,
            "evidence_reference": "synthetic-source-evidence-4",
            "independent_of_implementation": True,
        },
        {
            "source_id": "SYNTHETIC-5",
            "part": "SYNTHETIC-EXTRA-5",
            "edition": "TEST",
            "identity": "SYNTHETIC SOURCE FAMILY 5",
            "official_url": "https://example.invalid/synthetic-stage7-extra-5",
            "current_through": date(2026, 9, 27),
            "amendment_set_complete": True,
            "verified_by": "independent-test-verifier",
            "verified_at": verified_at,
            "evidence_reference": "synthetic-source-evidence-5",
            "independent_of_implementation": True,
        },
    ]
    source_documents = [
        {
            "source_id": "SYNTHETIC-1",
            "document_id": "principal",
            "identity": "SYNTHETIC STAGE7 FIXTURE",
            "official_url": "https://example.invalid/synthetic-stage7.pdf",
            "sha256": "a" * 64,
            "acquired_at": verified_at,
            "acquisition_reference": "synthetic-source-1",
        },
        {
            "source_id": "SYNTHETIC-2",
            "document_id": "principal",
            "identity": "SYNTHETIC EXTRA STAGE7 FIXTURE",
            "official_url": "https://example.invalid/synthetic-stage7-extra.pdf",
            "sha256": "b" * 64,
            "acquired_at": verified_at,
            "acquisition_reference": "synthetic-source-2",
        },
        {
            "source_id": "SYNTHETIC-3",
            "document_id": "principal",
            "identity": "SYNTHETIC EXTRA 3 STAGE7 FIXTURE",
            "official_url": "https://example.invalid/synthetic-stage7-extra-3.pdf",
            "sha256": "c" * 64,
            "acquired_at": verified_at,
            "acquisition_reference": "synthetic-source-3",
        },
        {
            "source_id": "SYNTHETIC-4",
            "document_id": "principal",
            "identity": "SYNTHETIC EXTRA 4 STAGE7 FIXTURE",
            "official_url": "https://example.invalid/synthetic-stage7-extra-4.pdf",
            "sha256": "d" * 64,
            "acquired_at": verified_at,
            "acquisition_reference": "synthetic-source-4",
        },
        {
            "source_id": "SYNTHETIC-5",
            "document_id": "principal",
            "identity": "SYNTHETIC EXTRA 5 STAGE7 FIXTURE",
            "official_url": "https://example.invalid/synthetic-stage7-extra-5.pdf",
            "sha256": "e" * 64,
            "acquired_at": verified_at,
            "acquisition_reference": "synthetic-source-5",
        },
    ]
    register_signoffs = [
        {
            "register_id": register_id,
            "status": "VERIFIED",
            "verified_by": "independent-test-verifier",
            "verifier_role": "synthetic contract verifier",
            "verifier_organization": "synthetic test organization",
            "verified_at": verified_at,
            "evidence_reference": f"synthetic-{register_id}",
            "independent_of_implementation": True,
        }
        for register_id in REQUIRED_REGISTERS
    ]
    item_signoffs = [
        {
            "item_type": "RULE",
            "item_key": "SYNTHETIC_STAGE7_RULE",
            "source_part": "SYNTHETIC",
            "source_edition": "TEST",
            "source_identity": "SYNTHETIC STAGE7 FIXTURE",
            "source_clause": "TEST-1",
            "source_digest": "a" * 64,
            "verified_by": "independent-test-verifier",
            "verifier_role": "synthetic contract verifier",
            "verified_at": verified_at,
            "evidence_reference": "synthetic-item-evidence",
            "independent_of_implementation": True,
        },
        {
            "item_type": "TEST",
            "item_key": "WEIGHING_PERFORMANCE",
            "source_part": "SYNTHETIC",
            "source_edition": "TEST",
            "source_identity": "SYNTHETIC STAGE7 FIXTURE",
            "source_clause": "TEST-1",
            "source_digest": "a" * 64,
            "verified_by": "independent-test-verifier",
            "verifier_role": "synthetic contract verifier",
            "verified_at": verified_at,
            "evidence_reference": "synthetic-item-evidence",
            "independent_of_implementation": True,
        },
    ]
    manifest = Stage7VerificationManifest.model_validate(
        {
            "schema_version": 1,
            "artifact_id": VERIFIED_ARTIFACT,
            "target_standard_code": "OIML_R76",
            "target_edition": "R76-1:2006 / R76-2:2007",
            "target_version": "verified-v1",
            "candidate_configuration_hash": ruleset.configuration_hash,
            "verified_configuration_hash": ruleset.configuration_hash,
            "evidence_package_sha256": "c" * 64,
            "regulatory_signoff": True,
            "source_evidence": source_evidence,
            "source_documents": source_documents,
            "register_signoffs": register_signoffs,
            "item_signoffs": item_signoffs,
            "runtime_schemas": [
                {
                    "test_code": "WEIGHING_PERFORMANCE",
                    "procedure_schema_version": "v1",
                    "observation_schema_version": "v1",
                    "runtime_binding_sha256": runtime_binding_hash(
                        implemented_registry().resolve("WEIGHING_PERFORMANCE"),
                        "v1",
                        "v1",
                    ),
                    "status": "VERIFIED",
                    "reviewed_by": "independent-test-verifier",
                    "reviewer_role": "synthetic contract verifier",
                    "reviewer_organization": "synthetic test organization",
                    "reviewed_at": verified_at,
                    "evidence_reference": "synthetic-runtime-v1",
                    "independent_of_implementation": True,
                }
            ],
        }
    )
    return ruleset, manifest


def test_stage7_verified_artifact_is_a_closed_registration_literal():
    registration = RuleRegistration(artifact=VERIFIED_ARTIFACT)
    assert registration.artifact == VERIFIED_ARTIFACT


def test_stage7_current_production_intake_is_fail_closed():
    readiness = inspect_verified_artifact()

    assert readiness.ready is False
    assert readiness.blockers
    assert any(
        "independent_human_signoff.marker" in item
        for item in readiness.blockers
    )


def test_stage7_candidate_v1_remains_unpromoted():
    ruleset = load_ruleset()

    assert ruleset.metadata.version == "candidate-v1"
    assert ruleset.metadata.supported_test_codes == ()
    assert ruleset.activation_blockers()
    assert "NO_SUPPORTED_TESTS" in ruleset.activation_blockers()


def test_stage7_template_cannot_claim_signoff():
    path = (
        REPO
        / "backend"
        / "app"
        / "compliance"
        / "rules"
        / "oiml_r76_2006_verified"
        / "stage7_verification_manifest.template.json"
    )
    template = json.loads(path.read_text(encoding="utf-8"))

    assert template["regulatory_signoff"] is False
    assert template["candidate_configuration_hash"] is None
    assert template["verified_configuration_hash"] is None
    assert {
        row["register_id"] for row in template["register_signoffs"]
    } == set(REQUIRED_REGISTERS)
    assert all(
        row["status"] == "PENDING"
        for row in template["register_signoffs"]
    )


def test_stage7_manifest_requires_explicit_independent_signoff():
    _, manifest = synthetic_verified_fixture()
    value = manifest.model_dump(mode="json")
    value["register_signoffs"][0]["independent_of_implementation"] = False

    with pytest.raises(ValueError):
        Stage7VerificationManifest.model_validate(value)


def test_stage7_gate_logic_has_a_synthetic_contract_fixture():
    ruleset, manifest = synthetic_verified_fixture()

    assert ruleset.activation_blockers() == ()
    assert verified_artifact_blockers(
        ruleset,
        manifest,
        candidate_ruleset=ruleset,
        production=False,
    ) == ()


def test_stage7_synthetic_fixture_never_passes_production_intake():
    ruleset, manifest = synthetic_verified_fixture()

    blockers = verified_artifact_blockers(
        ruleset,
        manifest,
        candidate_ruleset=ruleset,
        production=True,
    )
    assert "STAGE7:SYNTHETIC_ARTIFACT_FORBIDDEN" in blockers


def test_stage7_runtime_schema_can_prefer_registered_v2():
    registration = voltage_variation_registration()
    v2_context = next(
        item
        for item in registration.contexts.registrations
        if item.procedure_schema_version == "v2"
    )
    assert any(
        item.observation_schema_version == "v2"
        for item in registration.observations.registrations
    )

    assert registration.runtime_schema_versions(
        v2_context.procedure_variant,
        procedure_schema_version="v2",
        observation_schema_version="v2",
    ) == ("v2", "v2")


def test_stage7_runtime_schema_rejects_partial_override():
    registration = voltage_variation_registration()
    variant = registration.contexts.registrations[0].procedure_variant

    with pytest.raises(ValueError):
        registration.runtime_schema_versions(
            variant,
            procedure_schema_version="v1",
            observation_schema_version=None,
        )


def test_stage7_service_binds_external_manifest_hash():
    source = (
        REPO / "backend" / "app" / "services" / "rulesets.py"
    ).read_text(encoding="utf-8")

    assert "load_verified_ruleset" in source
    assert "stage7_manifest_hash" in source
    assert "RULESET_NOT_VERIFIED" in source
    assert "RULESET_NOT_VALIDATED" in source


def test_stage7_docs_preserve_human_verification_boundary():
    text = (REPO / "PHASE25_STAGE7.md").read_text(encoding="utf-8")

    assert "STAGE 7 ACTIVATION-ACCEPTANCE INFRASTRUCTURE = COMPLETE" in text
    assert "REG-01..REG-17 = VERIFIED" in text
    assert "verified-v1 = ACTIVE" in text
    assert "independent human/domain-expert" in text


def test_stage7_verifier_reports_current_external_block():
    result = verify_stage7()

    assert result["implementation_status"] == "COMPLETE"
    assert result["regulatory_verification_status"] == "PENDING_EXTERNAL_SIGNOFF"
    assert result["verified_artifact_ready"] is False
    assert result["registration_gate"] == "BLOCKED"
    assert result["activation_gate"] == "BLOCKED"
    assert result["stage8_authoritative_gate"] == "BLOCKED"
    assert result["required_registers"] == 17
    assert len(result["candidate_hash"]) == 64


def test_stage7_requires_oiml_and_india_authority_source_evidence():
    assert REQUIRED_SOURCE_IDS == {
        "SRC-R76-1-2006-E",
        "SRC-R76-2-2007-E",
        "SRC-INDIA-APPROVAL-MODELS-2011",
        "SRC-INDIA-LM-GENERAL",
        "SRC-INDIA-GATC",
    }

    template_path = (
        REPO
        / "backend"
        / "app"
        / "compliance"
        / "rules"
        / "oiml_r76_2006_verified"
        / "stage7_verification_manifest.template.json"
    )
    template = json.loads(template_path.read_text(encoding="utf-8"))
    assert REQUIRED_SOURCE_IDS <= {
        row["source_id"] for row in template["source_evidence"]
    }


def test_stage7_runtime_authority_requires_exact_reviewed_binding():
    source = (
        REPO / "backend" / "app" / "compliance" / "stage7_activation.py"
    ).read_text(encoding="utf-8")
    assert "RUNTIME_BINDING_MISMATCH" in source
    assert "V2_NOT_AUTHORITY_ENABLED" not in source
