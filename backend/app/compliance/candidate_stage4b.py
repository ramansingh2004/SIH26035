"""Phase 25 Stage 4B controlled candidate facts for Sections 11–15."""

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
    / "phase25_stage4b_candidate.json"
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
    report_sections: tuple[str, ...] = ()


class RuntimeProjection(Frozen):
    target_policy_kind: str = Field(min_length=1)
    context_schema: str = Field(min_length=1)
    observation_schema: str = Field(min_length=1)
    status: Literal[
        "NATIVE_SCHEMA_PRESENT_EXECUTION_PENDING",
        "SCHEMA_PRESENT_SEMANTIC_DERIVATION_PENDING",
    ]
    blockers: tuple[str, ...] = Field(min_length=1)


class CandidateFact(Frozen):
    fact_id: str = Field(pattern=r"^STAGE4B_[A-Z0-9_]+$")
    family: Literal[
        "VOLTAGE_VARIATION",
        "ELECTRICAL_DISTURBANCES",
        "DAMP_HEAT",
        "SPAN_STABILITY",
        "ENDURANCE",
    ]
    register_ids: tuple[Literal["REG-12", "REG-13", "REG-14"], ...]
    source_refs: tuple[EvidenceRef, ...] = Field(min_length=1)
    verification_status: Literal[
        "SOURCE_MAPPED_PENDING_INDEPENDENT_SIGNOFF"
    ] = CANDIDATE_STATUS
    activation_allowed: Literal[False] = False
    runtime_projection: RuntimeProjection
    details: dict[str, Any] = Field(min_length=1)


class CandidateBundle(Frozen):
    schema_version: Literal[1]
    bundle_id: str
    standard_code: Literal["OIML_R76"]
    edition: Literal["R76-1:2006 / R76-2:2007"]
    verification_status: Literal[
        "SOURCE_MAPPED_PENDING_INDEPENDENT_SIGNOFF"
    ] = CANDIDATE_STATUS
    activation_allowed: Literal[False] = False
    independent_verifier: Literal["PENDING"] = "PENDING"
    sources: tuple[CandidateSource, ...] = Field(min_length=2)
    facts: tuple[CandidateFact, ...] = Field(min_length=5)

    @model_validator(mode="after")
    def consistency(self):
        source_ids = [item.source_id for item in self.sources]
        if len(source_ids) != len(set(source_ids)):
            raise ValueError("Duplicate Stage 4 source identifier")

        fact_ids = [item.fact_id for item in self.facts]
        if len(fact_ids) != len(set(fact_ids)):
            raise ValueError("Duplicate Stage 4 fact identifier")

        known_sources = set(source_ids)
        for fact in self.facts:
            for reference in fact.source_refs:
                if reference.source_id not in known_sources:
                    raise ValueError("Stage 4 fact references unknown source")

        if {item.family for item in self.facts} != {
            "VOLTAGE_VARIATION",
            "ELECTRICAL_DISTURBANCES",
            "DAMP_HEAT",
            "SPAN_STABILITY",
            "ENDURANCE",
        }:
            raise ValueError("Stage 4 candidate must cover Sections 11–15")

        registers = {
            register_id
            for fact in self.facts
            for register_id in fact.register_ids
        }
        if registers != {"REG-12", "REG-13", "REG-14"}:
            raise ValueError("Stage 4 candidate must cover REG-12/13/14 exactly")

        if any(source.digest is not None for source in self.sources):
            raise ValueError("Stage 4 source digests must remain pending here")
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


def load_stage4b_candidate(path: Path = ROOT) -> CandidateBundle:
    return CandidateBundle.model_validate_json(path.read_text(encoding="utf-8"))


__all__ = [
    "ACQUISITION_PENDING",
    "CANDIDATE_STATUS",
    "CandidateBundle",
    "CandidateFact",
    "CandidateSource",
    "EvidenceRef",
    "RuntimeProjection",
    "load_stage4b_candidate",
]
