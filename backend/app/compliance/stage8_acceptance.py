"""Phase 25 Stage 8 authoritative end-to-end acceptance contract.

The module defines the production walkthrough contract and fail-closed preflight.
It does not manufacture regulatory evidence and it does not bypass Stage 7.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.compliance.stage7_activation import VERIFIED_ROOT, inspect_verified_artifact

HASH64 = r"^[a-f0-9]{64}$"
RUN_RECORD_NAME = "stage8_authoritative_run.json"


class Frozen(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class HttpStep(Frozen):
    step_id: str
    method: Literal["GET", "POST", "PATCH", "DELETE"]
    path: str
    purpose: str
    actor_boundary: str


REQUIRED_HTTP_STEPS = (
    HttpStep(
        step_id="RULESET_REGISTER",
        method="POST",
        path="/api/v1/rulesets",
        purpose="Register independently verified trusted artifact",
        actor_boundary="ruleset:create",
    ),
    HttpStep(
        step_id="RULESET_VALIDATE",
        method="POST",
        path="/api/v1/rulesets/{identifier}/validate",
        purpose="Re-evaluate frozen artifact and Stage 7 manifest",
        actor_boundary="ruleset:validate",
    ),
    HttpStep(
        step_id="RULESET_ACTIVATE",
        method="POST",
        path="/api/v1/rulesets/{identifier}/activate",
        purpose="Activate only a validated blocker-free production artifact",
        actor_boundary="ruleset:activate",
    ),
    HttpStep(
        step_id="SESSION_CREATE",
        method="POST",
        path="/api/v1/test-sessions",
        purpose="Pin immutable ACTIVE verified ruleset into a new evaluation",
        actor_boundary="LAB_ENGINEER",
    ),
    HttpStep(
        step_id="SESSION_CONFIGURE",
        method="POST",
        path="/api/v1/test-sessions/{identifier}/configure",
        purpose="Freeze instrument configuration snapshot",
        actor_boundary="LAB_ENGINEER",
    ),
    HttpStep(
        step_id="APPLICABILITY_PREVIEW",
        method="POST",
        path="/api/v1/test-sessions/{identifier}/applicability",
        purpose="Resolve rules-driven applicability before confirmation",
        actor_boundary="LAB_ENGINEER",
    ),
    HttpStep(
        step_id="APPLICABILITY_CONFIRM",
        method="POST",
        path="/api/v1/test-sessions/{identifier}/confirm-applicability",
        purpose="Create authoritative requirements and runs",
        actor_boundary="LAB_ENGINEER",
    ),
    HttpStep(
        step_id="START_TESTING",
        method="POST",
        path="/api/v1/test-sessions/{identifier}/start-testing",
        purpose="Enter testing workflow",
        actor_boundary="LAB_ENGINEER",
    ),
    HttpStep(
        step_id="RUN_START",
        method="POST",
        path="/api/v1/test-runs/{identifier}/start",
        purpose="Start each required/elected run",
        actor_boundary="LAB_TECHNICIAN_OR_ENGINEER",
    ),
    HttpStep(
        step_id="PROCEDURE_CONTEXT",
        method="PATCH",
        path="/api/v1/test-runs/{identifier}/procedure-context",
        purpose="Capture verified procedure context",
        actor_boundary="LAB_TECHNICIAN_OR_ENGINEER",
    ),
    HttpStep(
        step_id="OBSERVATIONS",
        method="POST",
        path="/api/v1/test-runs/{identifier}/observations",
        purpose="Capture typed observations",
        actor_boundary="LAB_TECHNICIAN_OR_ENGINEER",
    ),
    HttpStep(
        step_id="ENVIRONMENT",
        method="POST",
        path="/api/v1/test-runs/{identifier}/environment",
        purpose="Capture measured environmental facts",
        actor_boundary="LAB_TECHNICIAN_OR_ENGINEER",
    ),
    HttpStep(
        step_id="EQUIPMENT",
        method="POST",
        path="/api/v1/test-runs/{identifier}/equipment/{equipment_id}",
        purpose="Freeze test-equipment/calibration identity",
        actor_boundary="LAB_TECHNICIAN_OR_ENGINEER",
    ),
    HttpStep(
        step_id="EVIDENCE_PRESIGN",
        method="POST",
        path="/api/v1/attachments/presign",
        purpose="Stage bounded evidence upload",
        actor_boundary="LAB_TECHNICIAN_OR_ENGINEER",
    ),
    HttpStep(
        step_id="EVIDENCE_COMPLETE",
        method="POST",
        path="/api/v1/attachments/complete",
        purpose="Publish content-addressed evidence",
        actor_boundary="LAB_TECHNICIAN_OR_ENGINEER",
    ),
    HttpStep(
        step_id="RUN_EVALUATE",
        method="POST",
        path="/api/v1/test-runs/{identifier}/evaluate",
        purpose="Produce deterministic ruleset-pinned result",
        actor_boundary="LAB_ENGINEER",
    ),
    HttpStep(
        step_id="RUN_COMPLETE",
        method="POST",
        path="/api/v1/test-runs/{identifier}/complete",
        purpose="Lock completed run and its source observations",
        actor_boundary="LAB_ENGINEER",
    ),
    HttpStep(
        step_id="RETEST",
        method="POST",
        path="/api/v1/test-runs/{identifier}/retests",
        purpose="Create immutable retest lineage when required",
        actor_boundary="LAB_ENGINEER",
    ),
    HttpStep(
        step_id="SELECT_RUN",
        method="POST",
        path="/api/v1/test-requirements/{identifier}/select-run",
        purpose="Explicitly select authoritative retest result",
        actor_boundary="LAB_ENGINEER",
    ),
    HttpStep(
        step_id="START_EXAMINATION",
        method="POST",
        path="/api/v1/test-sessions/{identifier}/start-examination",
        purpose="Enter Sections 16–17 examination workflow",
        actor_boundary="LAB_ENGINEER",
    ),
    HttpStep(
        step_id="CONSTRUCTION_ITEM",
        method="PATCH",
        path="/api/v1/test-sessions/{identifier}/construction/items/{item_id}",
        purpose="Capture Section 16 verified construction examination",
        actor_boundary="LAB_ENGINEER",
    ),
    HttpStep(
        step_id="CONSTRUCTION_COMPLETE",
        method="POST",
        path="/api/v1/test-sessions/{identifier}/construction/complete",
        purpose="Complete Section 16",
        actor_boundary="LAB_ENGINEER",
    ),
    HttpStep(
        step_id="CHECKLIST_ITEM",
        method="PATCH",
        path="/api/v1/test-sessions/{identifier}/checklist/{rule_id}",
        purpose="Capture Section 17 response/evidence",
        actor_boundary="LAB_ENGINEER",
    ),
    HttpStep(
        step_id="CHECKLIST_COMPLETE",
        method="POST",
        path="/api/v1/test-sessions/{identifier}/checklist/complete",
        purpose="Complete Section 17",
        actor_boundary="LAB_ENGINEER",
    ),
    HttpStep(
        step_id="SUBMIT_REVIEW",
        method="POST",
        path="/api/v1/test-sessions/{identifier}/submit-for-review",
        purpose="Submit immutable current regulatory revision",
        actor_boundary="LAB_ENGINEER",
    ),
    HttpStep(
        step_id="TECHNICAL_REVIEW",
        method="POST",
        path="/api/v1/test-sessions/{identifier}/reviews",
        purpose="Independent technical review",
        actor_boundary="REVIEWER",
    ),
    HttpStep(
        step_id="FINAL_APPROVAL",
        method="POST",
        path="/api/v1/test-sessions/{identifier}/approve",
        purpose="Create immutable final approval snapshot",
        actor_boundary="APPROVING_OFFICER",
    ),
    HttpStep(
        step_id="REPORT_GENERATE",
        method="POST",
        path="/api/v1/test-sessions/{identifier}/reports",
        purpose="Generate official PDF and DOCX from approval snapshot",
        actor_boundary="report:generate",
    ),
    HttpStep(
        step_id="REPORT_ISSUE",
        method="POST",
        path="/api/v1/reports/{identifier}/issue",
        purpose="Issue only after REG-17 and frozen issuer gates",
        actor_boundary="report:issue",
    ),
    HttpStep(
        step_id="REPORT_FILES",
        method="GET",
        path="/api/v1/reports/{identifier}/files",
        purpose="Verify immutable generated file identities/hashes",
        actor_boundary="report:read",
    ),
    HttpStep(
        step_id="RUN_HISTORY",
        method="GET",
        path="/api/v1/test-runs/{identifier}/history",
        purpose="Verify retest/result/selection history",
        actor_boundary="test:read",
    ),
)


class SectionEvidence(Frozen):
    section_number: int = Field(ge=1, le=17)
    applicability_status: Literal[
        "REQUIRED",
        "OPTIONAL",
        "NOT_APPLICABLE",
    ]
    evaluation_status: Literal["COMPLETE"]
    compliance_outcome: Literal[
        "COMPLIANT",
        "NONCOMPLIANT",
        "NOT_APPLICABLE",
    ]


class FileEvidence(Frozen):
    format: Literal["PDF", "DOCX"]
    attachment_id: str = Field(min_length=1)
    sha256: str = Field(pattern=HASH64)
    object_version: str = Field(min_length=1)


class Stage8AuthoritativeRunRecord(Frozen):
    schema_version: Literal[1]
    status: Literal["COMPLETE"]
    stage7_verified_artifact_ready: Literal[True]
    synthetic_fixture: Literal[False]
    ruleset_status: Literal["ACTIVE"]
    ruleset_id: str = Field(min_length=1)
    ruleset_configuration_hash: str = Field(pattern=HASH64)
    stage7_manifest_hash: str = Field(pattern=HASH64)
    test_session_id: str = Field(min_length=1)
    regulatory_revision: int = Field(gt=0)
    workflow_status: Literal["REPORT_ISSUED"]
    evaluation_status: Literal["COMPLETE"]
    compliance_outcome: Literal["COMPLIANT", "NONCOMPLIANT"]
    approval_snapshot_hash: str = Field(pattern=HASH64)
    sections: tuple[SectionEvidence, ...] = Field(min_length=17, max_length=17)
    report_id: str = Field(min_length=1)
    report_number: str = Field(pattern=r"^R76-[0-9]{4}-[1-9][0-9]*$")
    report_revision_no: int = Field(gt=0)
    report_status: Literal["ISSUED"]
    generation_id: str = Field(min_length=1)
    report_hash: str = Field(pattern=HASH64)
    files: tuple[FileEvidence, ...] = Field(min_length=2, max_length=2)
    audit_evidence_reference: str = Field(min_length=1)
    acceptance_evidence_package_sha256: str = Field(pattern=HASH64)

    @model_validator(mode="after")
    def complete_authoritative_record(self):
        section_numbers = [item.section_number for item in self.sections]
        if set(section_numbers) != set(range(1, 18)) or len(section_numbers) != 17:
            raise ValueError("Stage 8 record must contain Sections 1 through 17 exactly once")

        formats = [item.format for item in self.files]
        if set(formats) != {"PDF", "DOCX"} or len(formats) != 2:
            raise ValueError("Stage 8 record requires exactly one PDF and one DOCX")

        return self

    @property
    def record_hash(self) -> str:
        encoded = json.dumps(
            self.model_dump(mode="json"),
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
        ).encode("utf-8")
        return hashlib.sha256(encoded).hexdigest()


@dataclass(frozen=True)
class Stage8Preflight:
    engineering_ready: bool
    authoritative_ready: bool
    blockers: tuple[str, ...]
    required_http_steps: int
    stage7_candidate_hash: str
    stage7_verified_hash: str | None
    stage7_manifest_hash: str | None


def stage8_preflight() -> Stage8Preflight:
    """Fail closed until an independently verified Stage 7 artifact exists."""

    readiness = inspect_verified_artifact()
    blockers: set[str] = set()

    if not readiness.ready:
        blockers.add("STAGE8:STAGE7_VERIFIED_ARTIFACT_REQUIRED")
        blockers.update(
            f"STAGE8:UPSTREAM:{item}" for item in readiness.blockers
        )

    return Stage8Preflight(
        engineering_ready=True,
        authoritative_ready=not blockers,
        blockers=tuple(sorted(blockers)),
        required_http_steps=len(REQUIRED_HTTP_STEPS),
        stage7_candidate_hash=readiness.candidate_hash,
        stage7_verified_hash=readiness.verified_hash,
        stage7_manifest_hash=readiness.manifest_hash,
    )


@dataclass(frozen=True)
class Stage8EvidenceReadiness:
    complete: bool
    blockers: tuple[str, ...]
    record_hash: str | None = None


def inspect_stage8_evidence(
    directory=VERIFIED_ROOT,
) -> Stage8EvidenceReadiness:
    """Validate the external authoritative-run evidence record if present."""

    preflight = stage8_preflight()
    blockers = set(preflight.blockers)
    record_path = directory / RUN_RECORD_NAME

    if not record_path.is_file():
        blockers.add(f"STAGE8:MISSING:{RUN_RECORD_NAME}")
        return Stage8EvidenceReadiness(
            complete=False,
            blockers=tuple(sorted(blockers)),
        )

    try:
        record = Stage8AuthoritativeRunRecord.model_validate_json(
            record_path.read_text(encoding="utf-8")
        )
    except Exception as exc:
        blockers.add(
            f"STAGE8:INVALID_AUTHORITATIVE_RUN_RECORD:{type(exc).__name__}"
        )
        return Stage8EvidenceReadiness(
            complete=False,
            blockers=tuple(sorted(blockers)),
        )

    if preflight.stage7_manifest_hash != record.stage7_manifest_hash:
        blockers.add("STAGE8:STAGE7_MANIFEST_HASH_MISMATCH")

    if (
        preflight.stage7_verified_hash
        != record.ruleset_configuration_hash
    ):
        blockers.add("STAGE8:RULESET_HASH_MISMATCH")

    return Stage8EvidenceReadiness(
        complete=not blockers,
        blockers=tuple(sorted(blockers)),
        record_hash=record.record_hash,
    )


__all__ = [
    "FileEvidence",
    "HttpStep",
    "REQUIRED_HTTP_STEPS",
    "RUN_RECORD_NAME",
    "SectionEvidence",
    "Stage8AuthoritativeRunRecord",
    "Stage8EvidenceReadiness",
    "Stage8Preflight",
    "inspect_stage8_evidence",
    "stage8_preflight",
]
