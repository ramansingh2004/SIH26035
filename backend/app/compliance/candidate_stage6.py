"""Controlled Phase 25 Stage 6 candidate facts for REG-16 and REG-17."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

ROOT = (
    Path(__file__).parent
    / "rules"
    / "oiml_r76_2006"
    / "phase25_stage6_candidate.json"
)


class Frozen(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class CandidateSource(Frozen):
    source_id: str = Field(min_length=1)
    publisher: str = Field(min_length=1)
    title: str = Field(min_length=1)
    official_url: str = Field(min_length=1)
    digest: str | None = Field(default=None, pattern=r"^[a-f0-9]{64}$")
    status: Literal[
        "PENDING_CONTROLLED_ACQUISITION",
        "NATIONAL_MAPPING_PENDING_EXPERT_REVIEW",
        "AUTHORITY_SCOPE_MAPPING_PENDING",
    ]


class Stage6CandidateBundle(Frozen):
    schema_version: Literal[1]
    bundle_id: str = Field(min_length=1)
    standard_code: Literal["OIML_R76"]
    edition: str = Field(min_length=1)
    verification_status: Literal[
        "SOURCE_MAPPED_PENDING_INDEPENDENT_SIGNOFF"
    ]
    activation_allowed: Literal[False] = False
    independent_verifier: Literal["PENDING"] = "PENDING"
    register_ids: tuple[Literal["REG-16", "REG-17"], ...]
    sources: tuple[CandidateSource, ...] = Field(min_length=5)
    reg16: tuple[dict[str, Any], ...] = Field(min_length=4)
    reg17: tuple[dict[str, Any], ...] = Field(min_length=5)

    @model_validator(mode="after")
    def safe_boundary(self):
        if set(self.register_ids) != {"REG-16", "REG-17"}:
            raise ValueError("Stage 6 candidate must cover REG-16 and REG-17")
        if any(source.digest is not None for source in self.sources):
            raise ValueError("Stage 6 source digests remain pending")
        for item in (*self.reg16, *self.reg17):
            if item.get("implementation_status") is None:
                raise ValueError("Stage 6 fact requires implementation status")
            if not item.get("blockers"):
                raise ValueError("Stage 6 fact requires explicit blockers")
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


def load_stage6_candidate(path: Path = ROOT) -> Stage6CandidateBundle:
    return Stage6CandidateBundle.model_validate_json(path.read_text(encoding="utf-8"))


__all__ = ["CandidateSource", "Stage6CandidateBundle", "load_stage6_candidate"]
