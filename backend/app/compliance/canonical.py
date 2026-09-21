"""F08 v1 semantic normalization. Ordered arrays are never generically sorted."""

import hashlib
import json
import unicodedata
from datetime import UTC, date, datetime
from decimal import Decimal
from enum import Enum
from typing import Literal

from pydantic import BaseModel, SerializeAsAny, model_validator

from app.compliance.domain import (
    Digest,
    Frozen,
    InstrumentSnapshot,
    Observation,
    ObservationBatch,
    ProcedureContext,
    Text,
    ordered_unique,
)

ENGINE_VERSION = "r76-domain-0.4.0"


def normalize(value):
    if isinstance(value, BaseModel):
        # Access each actual concrete field: preserve typed schema extensions.
        return normalize({name: getattr(value, name) for name in type(value).model_fields})
    if isinstance(value, Decimal):
        if not value.is_finite():
            raise ValueError("Nonfinite number")
        text = format(value, "f")
        if "." in text:
            text = text.rstrip("0").rstrip(".")
        return "0" if value == 0 else text
    if isinstance(value, datetime):
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("Timestamp requires timezone")
        return value.astimezone(UTC).isoformat(timespec="microseconds").replace("+00:00", "Z")
    if isinstance(value, date):
        return value.isoformat()
    if isinstance(value, Enum):
        return normalize(value.value)
    if isinstance(value, str):
        return unicodedata.normalize("NFC", value)
    if isinstance(value, dict):
        result = {}
        for key, item in value.items():
            if not isinstance(key, str):
                raise ValueError("JSON object keys must be strings")
            key = normalize(key)
            if key in result:
                raise ValueError("Duplicate normalized JSON key")
            result[key] = normalize(item)
        return result
    if isinstance(value, (tuple, list)):
        return [normalize(item) for item in value]
    if value is None or type(value) in (int, bool):
        return value
    raise ValueError("Unsupported canonical value; floats and storage objects are forbidden")


def canonical_bytes(value) -> bytes:
    return json.dumps(
        normalize(value), sort_keys=True, ensure_ascii=False, separators=(",", ":"), allow_nan=False
    ).encode("utf-8")


def content_hash(value) -> str:
    return hashlib.sha256(canonical_bytes(value)).hexdigest()


def strict_json(text: str):
    def pairs(items):
        result = {}
        for key, value in items:
            key = unicodedata.normalize("NFC", key)
            if key in result:
                raise ValueError("Duplicate JSON key")
            result[key] = value
        return result

    def nonfinite(value):
        raise ValueError("Nonfinite JSON")

    # Numeric metrology remains decimal strings; JSON fractions are rejected by
    # typed schemas (never silently converted from binary float).
    return json.loads(text, object_pairs_hook=pairs, parse_constant=nonfinite)


class EvaluationInputSnapshot(Frozen):
    hash_schema_version: Literal["v1"] = "v1"
    instrument_snapshot: InstrumentSnapshot
    test_code: Text
    procedure_context: SerializeAsAny[ProcedureContext]
    observations: tuple[SerializeAsAny[Observation], ...]
    ruleset_configuration_hash: Digest
    observation_schema_version: Text
    engine_version: Text

    @model_validator(mode="after")
    def identities(self):
        if self.procedure_context.test_code != self.test_code or any(
            row.test_code != self.test_code
            or row.protocol != self.procedure_context.protocol
            or row.observation_schema_version != self.observation_schema_version
            for row in self.observations
        ):
            raise ValueError("Incompatible canonical input schemas")
        object.__setattr__(
            self, "observations", ordered_unique(self.observations, lambda r: r.sequence_no)
        )
        return self

    @property
    def input_hash(self) -> str:
        return content_hash(self)


def evaluation_input_snapshot(
    *,
    test_code: str,
    instrument_snapshot: InstrumentSnapshot,
    procedure_context: ProcedureContext,
    observations: ObservationBatch,
    ruleset_configuration_hash: str,
    engine_version: str = ENGINE_VERSION,
) -> EvaluationInputSnapshot:
    if (
        test_code != procedure_context.test_code
        or test_code != observations.test_code
        or procedure_context.protocol != observations.protocol
    ):
        raise ValueError("Incompatible test/context/observation identities")
    return EvaluationInputSnapshot(
        instrument_snapshot=instrument_snapshot,
        test_code=test_code,
        procedure_context=procedure_context,
        observations=observations.rows,
        ruleset_configuration_hash=ruleset_configuration_hash,
        observation_schema_version=observations.observation_schema_version,
        engine_version=engine_version,
    )
