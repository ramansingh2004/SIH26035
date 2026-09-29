"""Phase 25 Stage 7 verified-artifact intake and activation gates.

This module never promotes candidate regulatory content. It only validates a
separately supplied, independently signed-off immutable artifact before the
normal ruleset registration/activation lifecycle may see it.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.compliance.catalog import SECTIONS
from app.compliance.ruleset import ROOT as CANDIDATE_ROOT
from app.compliance.ruleset import RuleSet, load_ruleset
from app.compliance.runtime_binding import RuntimeBindingError, runtime_binding_hash
from app.compliance.suite import IMPLEMENTED_TEST_CODES, implemented_registry

VERIFIED_ARTIFACT = "oiml_r76_2006/verified-v1"
VERIFIED_VERSION = "verified-v1"
VERIFIED_ROOT = Path(__file__).parent / "rules" / "oiml_r76_2006_verified"
MANIFEST_NAME = "stage7_verification_manifest.json"
INDEPENDENT_HUMAN_SIGNOFF_MARKER = "independent_human_signoff.marker"
REQUIRED_RULESET_FILES = (
    "metadata.yaml",
    "classes.yaml",
    "mpe.yaml",
    "applicability.yaml",
    "voltage.yaml",
    "disturbances.yaml",
    "endurance.yaml",
    "checklist.yaml",
    "report_sections.yaml",
)
REQUIRED_REGISTERS = tuple(f"REG-{index:02d}" for index in range(1, 18))
REQUIRED_SOURCE_IDS = {
    "SRC-R76-1-2006-E",
    "SRC-R76-2-2007-E",
    "SRC-INDIA-APPROVAL-MODELS-2011",
    "SRC-INDIA-LM-GENERAL",
    "SRC-INDIA-GATC",
}
SINGLE_DOCUMENT_SOURCE_IDS = {
    "SRC-R76-1-2006-E",
    "SRC-R76-2-2007-E",
}


class Frozen(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class SourceFamilyEvidence(Frozen):
    source_id: str = Field(min_length=1)
    part: str = Field(min_length=1)
    edition: str = Field(min_length=1)
    identity: str = Field(min_length=1)
    # Landing/discovery URL for the logical source family. Exact document URLs
    # are carried by SourceDocumentEvidence.
    official_url: str = Field(min_length=1)
    current_through: date
    amendment_set_complete: Literal[True]
    verified_by: str = Field(min_length=1)
    verified_at: datetime
    evidence_reference: str = Field(min_length=1)
    independent_of_implementation: Literal[True] = True

    @model_validator(mode="after")
    def review_time_is_coherent(self):
        if self.verified_at.tzinfo is None:
            raise ValueError("Source-family verification time must include timezone")
        if self.current_through > self.verified_at.date():
            raise ValueError("Source-family current-through date cannot follow verification")
        return self


class SourceDocumentEvidence(Frozen):
    source_id: str = Field(min_length=1)
    document_id: str = Field(min_length=1)
    identity: str = Field(min_length=1)
    official_url: str = Field(min_length=1)
    sha256: str = Field(pattern=r"^[a-f0-9]{64}$")
    acquired_at: datetime
    acquisition_reference: str = Field(min_length=1)
    document_notes: str | None = None

    @model_validator(mode="after")
    def timezone_required(self):
        if self.acquired_at.tzinfo is None:
            raise ValueError("Source-document acquisition time must include timezone")
        return self


class RegisterSignoff(Frozen):
    register_id: str = Field(pattern=r"^REG-(0[1-9]|1[0-7])$")
    status: Literal["VERIFIED"]
    verified_by: str = Field(min_length=1)
    verifier_role: str = Field(min_length=1)
    verifier_organization: str = Field(min_length=1)
    verified_at: datetime
    evidence_reference: str = Field(min_length=1)
    independent_of_implementation: Literal[True] = True

    @model_validator(mode="after")
    def timezone_required(self):
        if self.verified_at.tzinfo is None:
            raise ValueError("Register verification timestamp must include timezone")
        return self


class ItemSignoff(Frozen):
    item_type: Literal["RULE", "TEST", "CHECKLIST"]
    item_key: str = Field(min_length=1)
    source_part: str = Field(min_length=1)
    source_edition: str = Field(min_length=1)
    source_identity: str = Field(min_length=1)
    source_clause: str = Field(min_length=1)
    source_digest: str = Field(pattern=r"^[a-f0-9]{64}$")
    verified_by: str = Field(min_length=1)
    verifier_role: str = Field(min_length=1)
    verified_at: datetime
    evidence_reference: str = Field(min_length=1)
    independent_of_implementation: Literal[True] = True

    @model_validator(mode="after")
    def timezone_required(self):
        if self.verified_at.tzinfo is None:
            raise ValueError("Item verification timestamp must include timezone")
        return self


class RuntimeSchemaSelection(Frozen):
    test_code: str = Field(min_length=1)
    procedure_schema_version: Literal["v1", "v2"]
    observation_schema_version: Literal["v1", "v2"]
    runtime_binding_sha256: str = Field(pattern=r"^[a-f0-9]{64}$")
    status: Literal["VERIFIED"]
    reviewed_by: str = Field(min_length=1)
    reviewer_role: str = Field(min_length=1)
    reviewer_organization: str = Field(min_length=1)
    reviewed_at: datetime
    evidence_reference: str = Field(min_length=1)
    independent_of_implementation: Literal[True] = True

    @model_validator(mode="after")
    def timezone_required(self):
        if self.reviewed_at.tzinfo is None:
            raise ValueError("Runtime-schema review timestamp must include timezone")
        return self


class Stage7VerificationManifest(Frozen):
    schema_version: Literal[1]
    artifact_id: Literal["oiml_r76_2006/verified-v1"]
    target_standard_code: Literal["OIML_R76"]
    target_edition: Literal["R76-1:2006 / R76-2:2007"]
    target_version: Literal["verified-v1"]
    candidate_configuration_hash: str = Field(pattern=r"^[a-f0-9]{64}$")
    verified_configuration_hash: str = Field(pattern=r"^[a-f0-9]{64}$")
    evidence_package_sha256: str = Field(pattern=r"^[a-f0-9]{64}$")
    regulatory_signoff: Literal[True]
    source_evidence: tuple[SourceFamilyEvidence, ...] = Field(min_length=5)
    source_documents: tuple[SourceDocumentEvidence, ...]
    register_signoffs: tuple[RegisterSignoff, ...] = Field(min_length=17)
    item_signoffs: tuple[ItemSignoff, ...] = Field(min_length=1)
    runtime_schemas: tuple[RuntimeSchemaSelection, ...] = Field(min_length=1)

    @model_validator(mode="after")
    def unique_identifiers(self):
        register_ids = [item.register_id for item in self.register_signoffs]
        if len(register_ids) != len(set(register_ids)):
            raise ValueError("Duplicate register signoff")

        item_ids = [(item.item_type, item.item_key) for item in self.item_signoffs]
        if len(item_ids) != len(set(item_ids)):
            raise ValueError("Duplicate item signoff")

        source_ids = [item.source_id for item in self.source_evidence]
        if len(source_ids) != len(set(source_ids)):
            raise ValueError("Duplicate source-family record")

        source_scopes = [(item.part, item.edition) for item in self.source_evidence]
        if len(source_scopes) != len(set(source_scopes)):
            raise ValueError("Duplicate source-family part/edition")

        document_keys = [
            (item.source_id, item.document_id)
            for item in self.source_documents
        ]
        if len(document_keys) != len(set(document_keys)):
            raise ValueError("Duplicate source-document record")

        family_by_id = {item.source_id: item for item in self.source_evidence}
        documented_source_ids = {item.source_id for item in self.source_documents}
        if not documented_source_ids <= family_by_id.keys():
            raise ValueError("Source document references unknown source family")
        if set(family_by_id) != documented_source_ids:
            raise ValueError("Every source family requires controlled source documents")
        for document in self.source_documents:
            if document.acquired_at > family_by_id[document.source_id].verified_at:
                raise ValueError("Source document acquired after source-family verification")

        runtime_codes = [item.test_code for item in self.runtime_schemas]
        if len(runtime_codes) != len(set(runtime_codes)):
            raise ValueError("Duplicate runtime schema selection")

        return self

    @property
    def manifest_hash(self) -> str:
        encoded = json.dumps(
            self.model_dump(mode="json"),
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
        ).encode("utf-8")
        return hashlib.sha256(encoded).hexdigest()

    def runtime_schema_map(self) -> dict[str, RuntimeSchemaSelection]:
        return {item.test_code: item for item in self.runtime_schemas}

    def source_document_map(self) -> dict[str, tuple[SourceDocumentEvidence, ...]]:
        return {
            source.source_id: tuple(
                document
                for document in self.source_documents
                if document.source_id == source.source_id
            )
            for source in self.source_evidence
        }


@dataclass(frozen=True)
class Stage7Readiness:
    ready: bool
    blockers: tuple[str, ...]
    candidate_hash: str
    verified_hash: str | None = None
    manifest_hash: str | None = None


class Stage7VerificationError(ValueError):
    def __init__(self, blockers):
        self.blockers = tuple(sorted(set(str(item) for item in blockers)))
        super().__init__("; ".join(self.blockers))


def _item_key(item_type: str, key: str) -> tuple[str, str]:
    return item_type, key


def _source_scope(source) -> tuple[str, str]:
    return source.part, source.edition


def _is_synthetic(ruleset: RuleSet) -> bool:
    values = (
        ruleset.metadata.version,
        ruleset.metadata.edition,
        ruleset.metadata.standard_name,
        ruleset.metadata.source_reference,
        *[source.identity for source in ruleset.metadata.standard_parts],
    )
    return any("SYNTHETIC" in str(value).upper() for value in values)


def _construction_policy_is_structural(rule) -> bool:
    parameters = [
        item.value
        for item in rule.parameters
        if item.name == "POLICY_JSON" and item.value is not None
    ]
    if len(parameters) != 1:
        return False
    try:
        policy = json.loads(parameters[0])
    except (TypeError, ValueError):
        return False
    return bool(
        isinstance(policy, dict)
        and policy.get("schema_version") == "v1"
        and policy.get("category")
        and policy.get("item_key")
        and isinstance(policy.get("required"), bool)
        and isinstance(policy.get("evidence_required"), bool)
        and isinstance(policy.get("allow_not_applicable"), bool)
    )


def verified_artifact_blockers(
    ruleset: RuleSet,
    manifest: Stage7VerificationManifest,
    *,
    candidate_ruleset: RuleSet,
    production: bool = True,
) -> tuple[str, ...]:
    blockers: set[str] = set()

    if manifest.candidate_configuration_hash != candidate_ruleset.configuration_hash:
        blockers.add("STAGE7:CANDIDATE_HASH_MISMATCH")
    if manifest.verified_configuration_hash != ruleset.configuration_hash:
        blockers.add("STAGE7:VERIFIED_HASH_MISMATCH")
    if manifest.target_standard_code != ruleset.metadata.standard_code:
        blockers.add("STAGE7:STANDARD_CODE_MISMATCH")
    if manifest.target_edition != ruleset.metadata.edition:
        blockers.add("STAGE7:EDITION_MISMATCH")
    if manifest.target_version != ruleset.metadata.version:
        blockers.add("STAGE7:VERSION_MISMATCH")
    if ruleset.metadata.version != VERIFIED_VERSION:
        blockers.add("STAGE7:VERIFIED_VERSION_REQUIRED")

    register_ids = {item.register_id for item in manifest.register_signoffs}
    if register_ids != set(REQUIRED_REGISTERS):
        blockers.add("STAGE7:REG01_REG17_SIGNOFF_REQUIRED")

    source_ids = {item.source_id for item in manifest.source_evidence}
    if production and not REQUIRED_SOURCE_IDS <= source_ids:
        blockers.add("STAGE7:REQUIRED_SOURCE_EVIDENCE_MISSING")

    documents_by_source = manifest.source_document_map()
    for source_id in source_ids:
        documents = documents_by_source.get(source_id, ())
        if not documents:
            blockers.add(f"STAGE7:SOURCE_DOCUMENTS_MISSING:{source_id}")
        if source_id in SINGLE_DOCUMENT_SOURCE_IDS and len(documents) != 1:
            blockers.add(f"STAGE7:SINGLE_DOCUMENT_SOURCE_REQUIRED:{source_id}")

    source_map = {
        (item.part, item.edition): item
        for item in manifest.source_evidence
    }
    for source in ruleset.metadata.standard_parts:
        evidence = source_map.get(_source_scope(source))
        if evidence is None:
            blockers.add(
                "STAGE7:SOURCE_EVIDENCE_MISSING:"
                + source.part
                + ":"
                + source.edition
            )
            continue
        matching_documents = [
            document
            for document in documents_by_source[evidence.source_id]
            if document.identity == source.identity
            and source.digest
            and document.sha256 == source.digest
        ]
        if not matching_documents:
            blockers.add(
                "STAGE7:SOURCE_DOCUMENT_MISMATCH:"
                + source.part
                + ":"
                + source.edition
            )

    signoffs = {
        _item_key(item.item_type, item.item_key): item
        for item in manifest.item_signoffs
    }

    def check_item(item_type, key, item):
        if item.verification.status != "VERIFIED":
            blockers.add(f"STAGE7:{item_type}:{key}:NOT_VERIFIED")
        if not item.source.clause:
            blockers.add(f"STAGE7:{item_type}:{key}:CLAUSE_REQUIRED")
        if not item.source.digest:
            blockers.add(f"STAGE7:{item_type}:{key}:DIGEST_REQUIRED")

        signoff = signoffs.get(_item_key(item_type, key))
        if signoff is None:
            blockers.add(f"STAGE7:{item_type}:{key}:SIGNOFF_REQUIRED")
            return

        expected = (
            item.source.part,
            item.source.edition,
            item.source.identity,
            item.source.clause,
            item.source.digest,
        )
        supplied = (
            signoff.source_part,
            signoff.source_edition,
            signoff.source_identity,
            signoff.source_clause,
            signoff.source_digest,
        )
        if supplied != expected:
            blockers.add(f"STAGE7:{item_type}:{key}:SIGNOFF_SOURCE_MISMATCH")
        if item.verification.verified_by != signoff.verified_by:
            blockers.add(f"STAGE7:{item_type}:{key}:VERIFIER_MISMATCH")
        if item.verification.verified_at != signoff.verified_at:
            blockers.add(f"STAGE7:{item_type}:{key}:VERIFIED_AT_MISMATCH")
        if item.verification.evidence != signoff.evidence_reference:
            blockers.add(f"STAGE7:{item_type}:{key}:EVIDENCE_REFERENCE_MISMATCH")

    for rule in ruleset.rules:
        check_item("RULE", rule.key, rule)
        if rule.blockers:
            blockers.add(f"STAGE7:RULE:{rule.key}:BLOCKERS_REMAIN")
        if any(parameter.value is None for parameter in rule.parameters):
            blockers.add(f"STAGE7:RULE:{rule.key}:UNRESOLVED_PARAMETER")
        if rule.kind == "construction_item_v1" and not _construction_policy_is_structural(rule):
            blockers.add(f"STAGE7:RULE:{rule.key}:INVALID_CONSTRUCTION_POLICY")

    for test in ruleset.tests:
        check_item("TEST", test.code, test)

    for item in ruleset.checklist:
        check_item("CHECKLIST", item.key, item)
        if isinstance(item.applicability, str):
            blockers.add(f"STAGE7:CHECKLIST:{item.key}:APPLICABILITY_UNRESOLVED")
        if item.evidence_required is None:
            blockers.add(f"STAGE7:CHECKLIST:{item.key}:EVIDENCE_REQUIREMENT_UNRESOLVED")

    expected_signoff_keys = {
        *[_item_key("RULE", item.key) for item in ruleset.rules],
        *[_item_key("TEST", item.code) for item in ruleset.tests],
        *[_item_key("CHECKLIST", item.key) for item in ruleset.checklist],
    }
    if set(signoffs) != expected_signoff_keys:
        blockers.add("STAGE7:ITEM_SIGNOFF_SET_MISMATCH")

    implemented = {item.code for item in ruleset.tests if item.implemented}
    supported = set(ruleset.metadata.supported_test_codes)
    required_implemented = set(IMPLEMENTED_TEST_CODES)

    if production:
        if _is_synthetic(ruleset):
            blockers.add("STAGE7:SYNTHETIC_ARTIFACT_FORBIDDEN")

        top_level = {item.code for item in ruleset.tests if item.parent is None}
        top_sections = {item.section for item in ruleset.tests if item.parent is None}
        if top_level != set(SECTIONS) or top_sections != set(range(1, 18)):
            blockers.add("STAGE7:COMPLETE_17_SECTION_CATALOG_REQUIRED")

        if implemented != required_implemented:
            blockers.add("STAGE7:IMPLEMENTED_TEST_SET_MISMATCH")
        if supported != required_implemented:
            blockers.add("STAGE7:SUPPORTED_TEST_SET_MISMATCH")

        if not any(item.kind == "construction_item_v1" for item in ruleset.rules):
            blockers.add("STAGE7:SECTION16_CONSTRUCTION_CATALOG_REQUIRED")
        if len(ruleset.checklist) != 27:
            blockers.add("STAGE7:SECTION17_CHECKLIST_CATALOG_REQUIRED")

    runtime_map = manifest.runtime_schema_map()
    if set(runtime_map) != supported:
        blockers.add("STAGE7:RUNTIME_SCHEMA_SET_MISMATCH")

    registry = implemented_registry()
    for code, selection in runtime_map.items():
        registration = registry.find(code)
        if registration is None:
            blockers.add(f"STAGE7:RUNTIME_SCHEMA:{code}:EVALUATOR_MISSING")
            continue

        procedure_versions = {
            item.procedure_schema_version
            for item in registration.contexts.registrations
        }
        observation_versions = {
            item.observation_schema_version
            for item in registration.observations.registrations
        }
        if selection.procedure_schema_version not in procedure_versions:
            blockers.add(f"STAGE7:RUNTIME_SCHEMA:{code}:PROCEDURE_UNAVAILABLE")
        if selection.observation_schema_version not in observation_versions:
            blockers.add(f"STAGE7:RUNTIME_SCHEMA:{code}:OBSERVATION_UNAVAILABLE")

        if (
            selection.procedure_schema_version in procedure_versions
            and selection.observation_schema_version in observation_versions
        ):
            try:
                expected_binding = runtime_binding_hash(
                    registration,
                    selection.procedure_schema_version,
                    selection.observation_schema_version,
                )
            except RuntimeBindingError:
                blockers.add(f"STAGE7:RUNTIME_SCHEMA:{code}:PAIR_UNAVAILABLE")
            else:
                if selection.runtime_binding_sha256 != expected_binding:
                    blockers.add(
                        f"STAGE7:RUNTIME_SCHEMA:{code}:RUNTIME_BINDING_MISMATCH"
                    )

        # v2 is not enabled by its label. It is authority-eligible only when
        # the exact runtime binding above is independently reviewed and still
        # matches the implementation at Stage 7 intake.

    blockers.update(ruleset.activation_blockers())
    return tuple(sorted(blockers))


def inspect_verified_artifact(
    directory: Path = VERIFIED_ROOT,
    *,
    candidate_directory: Path = CANDIDATE_ROOT,
) -> Stage7Readiness:
    candidate = load_ruleset(candidate_directory)
    missing = [
        name
        for name in (
            *REQUIRED_RULESET_FILES,
            MANIFEST_NAME,
            INDEPENDENT_HUMAN_SIGNOFF_MARKER,
        )
        if not (directory / name).is_file()
    ]
    if missing:
        return Stage7Readiness(
            ready=False,
            blockers=tuple(sorted(f"STAGE7:MISSING:{name}" for name in missing)),
            candidate_hash=candidate.configuration_hash,
        )

    try:
        ruleset = load_ruleset(directory)
    except Exception as exc:
        return Stage7Readiness(
            ready=False,
            blockers=(f"STAGE7:INVALID_VERIFIED_RULESET:{type(exc).__name__}",),
            candidate_hash=candidate.configuration_hash,
        )

    try:
        manifest = Stage7VerificationManifest.model_validate_json(
            (directory / MANIFEST_NAME).read_text(encoding="utf-8")
        )
    except Exception as exc:
        return Stage7Readiness(
            ready=False,
            blockers=(f"STAGE7:INVALID_MANIFEST:{type(exc).__name__}",),
            candidate_hash=candidate.configuration_hash,
            verified_hash=ruleset.configuration_hash,
        )

    blockers = verified_artifact_blockers(
        ruleset,
        manifest,
        candidate_ruleset=candidate,
        production=True,
    )
    return Stage7Readiness(
        ready=not blockers,
        blockers=blockers,
        candidate_hash=candidate.configuration_hash,
        verified_hash=ruleset.configuration_hash,
        manifest_hash=manifest.manifest_hash,
    )


def load_verified_ruleset(
    directory: Path = VERIFIED_ROOT,
    *,
    candidate_directory: Path = CANDIDATE_ROOT,
) -> tuple[RuleSet, Stage7VerificationManifest]:
    readiness = inspect_verified_artifact(
        directory,
        candidate_directory=candidate_directory,
    )
    if not readiness.ready:
        raise Stage7VerificationError(readiness.blockers)

    ruleset = load_ruleset(directory)
    manifest = Stage7VerificationManifest.model_validate_json(
        (directory / MANIFEST_NAME).read_text(encoding="utf-8")
    )
    return ruleset, manifest


__all__ = [
    "INDEPENDENT_HUMAN_SIGNOFF_MARKER",
    "MANIFEST_NAME",
    "REQUIRED_REGISTERS",
    "REQUIRED_SOURCE_IDS",
    "SINGLE_DOCUMENT_SOURCE_IDS",
    "SourceDocumentEvidence",
    "SourceFamilyEvidence",
    "Stage7Readiness",
    "Stage7VerificationError",
    "Stage7VerificationManifest",
    "VERIFIED_ARTIFACT",
    "VERIFIED_ROOT",
    "VERIFIED_VERSION",
    "inspect_verified_artifact",
    "load_verified_ruleset",
    "verified_artifact_blockers",
]
