"""Controlled Phase 25 Stage 5 candidate facts for Sections 16–17."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

CANDIDATE_STATUS = "SOURCE_MAPPED_PENDING_INDEPENDENT_SIGNOFF"
ACQUISITION_PENDING = "PENDING_CONTROLLED_ACQUISITION"
ROOT = Path(__file__).parent / "rules" / "oiml_r76_2006" / "phase25_stage5_candidate.json"


class Frozen(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class CandidateSource(Frozen):
    source_id: str = Field(min_length=1)
    part: Literal["R76-1", "R76-2"]
    edition: str = Field(min_length=1)
    official_url: str = Field(min_length=1)
    digest: str | None = Field(default=None, pattern=r"^[a-f0-9]{64}$")
    acquisition_status: Literal["PENDING_CONTROLLED_ACQUISITION"] = ACQUISITION_PENDING


class Stage5CandidateBundle(Frozen):
    schema_version: Literal[1]
    bundle_id: str
    standard_code: Literal["OIML_R76"]
    edition: Literal["R76-1:2006 / R76-2:2007"]
    verification_status: Literal["SOURCE_MAPPED_PENDING_INDEPENDENT_SIGNOFF"] = CANDIDATE_STATUS
    activation_allowed: Literal[False] = False
    independent_verifier: Literal["PENDING"] = "PENDING"
    register_ids: tuple[Literal["REG-15"], ...]
    sources: tuple[CandidateSource, ...] = Field(min_length=2)
    section16: dict[str, Any]
    section17: dict[str, Any]

    @model_validator(mode="after")
    def safe_boundary(self):
        if self.register_ids != ("REG-15",):
            raise ValueError("Stage 5 candidate must cover REG-15 only")
        if any(source.digest is not None for source in self.sources):
            raise ValueError("Stage 5 official source digests remain pending")
        if self.section16.get("activation_allowed") is not False:
            raise ValueError("Section 16 candidate cannot be activated")
        if self.section17.get("activation_allowed") is not False:
            raise ValueError("Section 17 candidate cannot be activated")
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


def load_stage5_candidate(path: Path = ROOT) -> Stage5CandidateBundle:
    return Stage5CandidateBundle.model_validate_json(path.read_text(encoding="utf-8"))


__all__ = ["ACQUISITION_PENDING","CANDIDATE_STATUS","Stage5CandidateBundle","load_stage5_candidate"]
