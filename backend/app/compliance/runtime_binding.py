"""Immutable runtime-schema binding for independent regulatory review.

A runtime review must bind more than labels such as ``v1``/``v2``.  This module
hashes the selected procedure/observation schema contracts, evaluator identity,
registered policy schemas, implementation version and normalized source text of
the evaluator plus shared compliance-core modules.

The binding is intentionally conservative: a relevant source change invalidates
the prior review and requires a new independent runtime review.
"""

from __future__ import annotations

import hashlib
import importlib
import inspect
import json
from typing import Any

from app.compliance.evaluators import EvaluatorRegistration

BINDING_SCHEMA_VERSION = "runtime-binding-v1"

CORE_RUNTIME_MODULES = (
    "app.compliance.applicability",
    "app.compliance.canonical",
    "app.compliance.domain",
    "app.compliance.engine",
    "app.compliance.evaluators",
    "app.compliance.numbers",
    "app.compliance.parameterized",
    "app.compliance.registries",
    "app.compliance.regulatory",
)


class RuntimeBindingError(ValueError):
    pass


def _sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _json_hash(value: Any) -> str:
    encoded = json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    ).encode("utf-8")
    return _sha256_bytes(encoded)


def _schema_identity(schema) -> dict[str, str]:
    return {
        "python_type": f"{schema.__module__}.{schema.__qualname__}",
        "json_schema_sha256": _json_hash(schema.model_json_schema()),
    }


def _module_source_sha256(module_name: str) -> str:
    try:
        module = importlib.import_module(module_name)
        source = inspect.getsource(module)
    except (ImportError, OSError, TypeError) as exc:
        raise RuntimeBindingError(
            f"Runtime source unavailable for binding: {module_name}"
        ) from exc
    normalized = source.replace("\r\n", "\n").replace("\r", "\n")
    return _sha256_bytes(normalized.encode("utf-8"))


def _procedure_protocols(registration, version: str) -> set[str]:
    protocols: set[str] = set()
    for item in registration.contexts.registrations:
        if item.procedure_schema_version != version:
            continue
        field = item.schema.model_fields.get("protocol")
        protocol = None if field is None else field.default
        if not isinstance(protocol, str):
            raise RuntimeBindingError(
                "Procedure schema must expose a literal/default protocol"
            )
        protocols.add(protocol)
    return protocols


def _observation_protocols(registration, version: str) -> set[str]:
    return {
        item.protocol
        for item in registration.observations.registrations
        if item.observation_schema_version == version
    }


def runtime_binding_payload(
    registration: EvaluatorRegistration,
    procedure_schema_version: str,
    observation_schema_version: str,
) -> dict[str, Any]:
    contexts = tuple(
        item
        for item in registration.contexts.registrations
        if item.procedure_schema_version == procedure_schema_version
    )
    observations = tuple(
        item
        for item in registration.observations.registrations
        if item.observation_schema_version == observation_schema_version
    )
    if not contexts:
        raise RuntimeBindingError("Selected procedure schema version is unavailable")
    if not observations:
        raise RuntimeBindingError("Selected observation schema version is unavailable")

    compatible_protocols = sorted(
        _procedure_protocols(registration, procedure_schema_version)
        & _observation_protocols(registration, observation_schema_version)
    )
    if not compatible_protocols:
        raise RuntimeBindingError(
            "Selected procedure/observation versions have no compatible protocol"
        )

    context_rows = sorted(
        (
            {
                "procedure_variant": item.procedure_variant,
                "protocol": item.schema.model_fields["protocol"].default,
                "schema": _schema_identity(item.schema),
            }
            for item in contexts
        ),
        key=lambda item: (
            item["procedure_variant"],
            item["protocol"],
            item["schema"]["python_type"],
        ),
    )
    observation_rows = sorted(
        (
            {
                "protocol": item.protocol,
                "schema": _schema_identity(item.schema),
            }
            for item in observations
        ),
        key=lambda item: (item["protocol"], item["schema"]["python_type"]),
    )
    policy_rows = sorted(
        (
            {
                "kind": item.kind,
                "schema": _schema_identity(item.schema),
            }
            for item in registration.policy_schemas
        ),
        key=lambda item: item["kind"],
    )

    module_names = {
        *CORE_RUNTIME_MODULES,
        type(registration.evaluator).__module__,
        *[item.schema.__module__ for item in contexts],
        *[item.schema.__module__ for item in observations],
        *[item.schema.__module__ for item in registration.policy_schemas],
    }
    source_modules = {
        name: _module_source_sha256(name)
        for name in sorted(module_names)
    }

    return {
        "binding_schema_version": BINDING_SCHEMA_VERSION,
        "test_code": registration.test_code,
        "evaluator_python_type": (
            f"{type(registration.evaluator).__module__}."
            f"{type(registration.evaluator).__qualname__}"
        ),
        "implementation_version": registration.implementation_version,
        "runtime_schema_default": registration.runtime_schema_version,
        "procedure_schema_version": procedure_schema_version,
        "observation_schema_version": observation_schema_version,
        "compatible_protocols": compatible_protocols,
        "contexts": context_rows,
        "observations": observation_rows,
        "policy_schemas": policy_rows,
        "source_module_sha256": source_modules,
    }


def runtime_binding_hash(
    registration: EvaluatorRegistration,
    procedure_schema_version: str,
    observation_schema_version: str,
) -> str:
    return _json_hash(
        runtime_binding_payload(
            registration,
            procedure_schema_version,
            observation_schema_version,
        )
    )


def runtime_binding_options(registration: EvaluatorRegistration) -> tuple[dict[str, Any], ...]:
    procedure_versions = sorted(
        {
            item.procedure_schema_version
            for item in registration.contexts.registrations
        }
    )
    observation_versions = sorted(
        {
            item.observation_schema_version
            for item in registration.observations.registrations
        }
    )

    options = []
    for procedure_version in procedure_versions:
        for observation_version in observation_versions:
            protocols = sorted(
                _procedure_protocols(registration, procedure_version)
                & _observation_protocols(registration, observation_version)
            )
            if not protocols:
                continue
            options.append(
                {
                    "procedure_schema_version": procedure_version,
                    "observation_schema_version": observation_version,
                    "compatible_protocols": protocols,
                    "runtime_binding_sha256": runtime_binding_hash(
                        registration,
                        procedure_version,
                        observation_version,
                    ),
                }
            )
    return tuple(options)


def runtime_binding_catalog_json(registration: EvaluatorRegistration) -> str:
    return json.dumps(
        runtime_binding_options(registration),
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    )


__all__ = [
    "BINDING_SCHEMA_VERSION",
    "RuntimeBindingError",
    "runtime_binding_catalog_json",
    "runtime_binding_hash",
    "runtime_binding_options",
    "runtime_binding_payload",
]
