"""Immutable typed schema registries. Specialized schemas arrive with evaluators."""

from dataclasses import dataclass

from app.compliance.canonical import strict_json
from app.compliance.domain import Observation, ObservationBatch, ProcedureContext


@dataclass(frozen=True)
class ContextRegistration:
    test_code: str
    procedure_variant: str
    procedure_schema_version: str
    schema: type[ProcedureContext]

    @property
    def key(self):
        return self.test_code, self.procedure_variant, self.procedure_schema_version


@dataclass(frozen=True)
class ObservationRegistration:
    test_code: str
    protocol: str
    observation_schema_version: str
    schema: type[Observation]

    @property
    def key(self):
        return self.test_code, self.protocol, self.observation_schema_version


@dataclass(frozen=True)
class ProcedureContextRegistry:
    registrations: tuple[ContextRegistration, ...] = ()

    def __post_init__(self):
        object.__setattr__(self, "registrations", tuple(self.registrations))
        if len({r.key for r in self.registrations}) != len(self.registrations):
            raise ValueError("Duplicate context registration")
        if any(not issubclass(r.schema, ProcedureContext) for r in self.registrations):
            raise ValueError("Invalid context schema")

    def resolve(self, test_code, variant, version):
        for registration in self.registrations:
            if registration.key == (test_code, variant, version):
                return registration.schema
        raise ValueError("Unknown procedure schema/version")

    def parse(self, payload) -> ProcedureContext:
        if isinstance(payload, str):
            payload = strict_json(payload)
        schema = self.resolve(
            payload.get("test_code"),
            payload.get("procedure_variant"),
            payload.get("procedure_schema_version"),
        )
        result = schema.model_validate(payload)
        return result

    def validate(self, context: ProcedureContext) -> ProcedureContext:
        schema = self.resolve(
            context.test_code, context.procedure_variant, context.procedure_schema_version
        )
        if type(context) is not schema:
            raise ValueError("Context type incompatible with registration")
        return schema.model_validate(context.model_dump(mode="python"))


@dataclass(frozen=True)
class ObservationSchemaRegistry:
    registrations: tuple[ObservationRegistration, ...] = ()

    def __post_init__(self):
        object.__setattr__(self, "registrations", tuple(self.registrations))
        if len({r.key for r in self.registrations}) != len(self.registrations):
            raise ValueError("Duplicate observation registration")
        if any(not issubclass(r.schema, Observation) for r in self.registrations):
            raise ValueError("Invalid observation schema")

    def resolve(self, test_code, protocol, version):
        for registration in self.registrations:
            if registration.key == (test_code, protocol, version):
                return registration.schema
        raise ValueError("Unknown observation schema/version")

    def parse(self, *, test_code, protocol, version, rows) -> ObservationBatch:
        schema = self.resolve(test_code, protocol, version)
        if isinstance(rows, str):
            rows = strict_json(rows)
        parsed = tuple(schema.model_validate(row) for row in rows)
        return ObservationBatch(
            test_code=test_code, protocol=protocol, observation_schema_version=version, rows=parsed
        )

    def validate(self, batch: ObservationBatch) -> ObservationBatch:
        schema = self.resolve(batch.test_code, batch.protocol, batch.observation_schema_version)
        if any(type(row) is not schema for row in batch.rows):
            raise ValueError("Observation type incompatible with registration")
        return self.parse(
            test_code=batch.test_code,
            protocol=batch.protocol,
            version=batch.observation_schema_version,
            rows=[r.model_dump(mode="python") for r in batch.rows],
        )
