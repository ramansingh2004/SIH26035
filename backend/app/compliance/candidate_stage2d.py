"""Phase 25 Stage 2D controlled candidate regulatory artifacts.

This module validates source-mapped candidate facts only. It is deliberately
not connected to RuleSet loading, activation, evaluator dispatch, approval, or
report issue.

A candidate fact becoming schema-valid here does not make it VERIFIED.
Independent human/domain-expert sign-off remains mandatory.
"""

import hashlib
import json
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

CANDIDATE_STATUS = "SOURCE_MAPPED_PENDING_INDEPENDENT_SIGNOFF"
ACQUISITION_PENDING = "PENDING_CONTROLLED_ACQUISITION"
ROOT = (
    Path(__file__).parent
    / "rules"
    / "oiml_r76_2006"
    / "phase25_stage2d_candidate.json"
)


class Frozen(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class CandidateSource(Frozen):
    source_id: str = Field(min_length=1)
    part: Literal["R76-1", "R76-2"]
    edition: str = Field(min_length=1)
    official_url: str = Field(min_length=1)
    digest: str | None = Field(default=None, pattern=r"^[a-f0-9]{64}$")
    acquisition_status: Literal["PENDING_CONTROLLED_ACQUISITION"] = ACQUISITION_PENDING


class EvidenceRef(Frozen):
    source_id: str = Field(min_length=1)
    clauses: tuple[str, ...] = Field(min_length=1)
    publication_pages: tuple[int, ...] = Field(min_length=1)


class RuntimeProjection(Frozen):
    status: Literal[
        "SCHEMA_READY_PENDING_SIGNOFF",
        "PARTIAL_SCHEMA_GAP",
        "SCHEMA_GAP",
    ]
    target_policy_kind: str | None = None
    blockers: tuple[str, ...] = Field(min_length=1)


class CandidateFact(Frozen):
    fact_id: str = Field(pattern=r"^STAGE2D_[A-Z0-9_]+$")
    family: Literal[
        "EDITION_SCOPE",
        "CLASSIFICATION",
        "MPE",
        "WEIGHING",
        "TEMPERATURE_ZERO",
        "ECCENTRICITY",
        "DISCRIMINATION",
        "SENSITIVITY",
        "REPEATABILITY",
    ]
    register_ids: tuple[str, ...] = Field(min_length=1)
    source_refs: tuple[EvidenceRef, ...] = Field(min_length=1)
    verification_status: Literal[
        "SOURCE_MAPPED_PENDING_INDEPENDENT_SIGNOFF"
    ] = CANDIDATE_STATUS
    activation_allowed: Literal[False] = False
    runtime_projection: RuntimeProjection
    details: dict[str, Any] = Field(min_length=1)


class CandidateBundle(Frozen):
    schema_version: Literal[1]
    bundle_id: str = Field(min_length=1)
    standard_code: Literal["OIML_R76"]
    edition: Literal["R76-1:2006 / R76-2:2007"]
    verification_status: Literal[
        "SOURCE_MAPPED_PENDING_INDEPENDENT_SIGNOFF"
    ] = CANDIDATE_STATUS
    activation_allowed: Literal[False] = False
    independent_verifier: Literal["PENDING"] = "PENDING"
    sources: tuple[CandidateSource, ...] = Field(min_length=2)
    facts: tuple[CandidateFact, ...] = Field(min_length=1)

    @model_validator(mode="after")
    def consistency(self):
        source_ids = [item.source_id for item in self.sources]
        if len(source_ids) != len(set(source_ids)):
            raise ValueError("Duplicate Stage 2D source identifier")

        fact_ids = [item.fact_id for item in self.facts]
        if len(fact_ids) != len(set(fact_ids)):
            raise ValueError("Duplicate Stage 2D fact identifier")

        known_sources = set(source_ids)
        for fact in self.facts:
            for reference in fact.source_refs:
                if reference.source_id not in known_sources:
                    raise ValueError("Candidate fact references an unknown source")

        covered_registers = {
            register_id
            for fact in self.facts
            for register_id in fact.register_ids
        }
        required = {f"REG-{number:02d}" for number in range(1, 9)}
        if not required <= covered_registers:
            raise ValueError("Stage 2D must cover REG-01 through REG-08")

        if any(item.digest is not None for item in self.sources):
            raise ValueError(
                "Stage 2D package must not fabricate controlled-source digests"
            )

        return self

    @property
    def candidate_hash(self) -> str:
        encoded = json.dumps(
            self.model_dump(mode="json"),
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
        ).encode("utf-8")
        return hashlib.sha256(encoded).hexdigest()

    def fact(self, family: str) -> CandidateFact:
        matches = [item for item in self.facts if item.family == family]
        if len(matches) != 1:
            raise KeyError(f"Expected exactly one Stage 2D fact for {family}")
        return matches[0]


def load_stage2d_candidate(path: Path = ROOT) -> CandidateBundle:
    return CandidateBundle.model_validate_json(path.read_text(encoding="utf-8"))


__all__ = [
    "ACQUISITION_PENDING",
    "CANDIDATE_STATUS",
    "CandidateBundle",
    "CandidateFact",
    "CandidateSource",
    "EvidenceRef",
    "RuntimeProjection",
    "load_stage2d_candidate",
]
