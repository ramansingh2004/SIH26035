"""Independent immutable configuration loader. No evaluation or ORM dependencies."""

import hashlib
import json
import unicodedata
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path
from typing import Annotated, Literal

import yaml
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

TODO = "TODO_REGULATORY_VALIDATION"
FILES = ("classes", "mpe", "applicability", "voltage", "disturbances", "endurance", "checklist")
ROOT = Path(__file__).parent / "rules" / "oiml_r76_2006"
Code = Annotated[str, Field(pattern=r"^[A-Z][A-Z0-9_]*$", max_length=100)]


class Frozen(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class Source(Frozen):
    part: str
    edition: str
    identity: str
    clause: str | None = None
    digest: Annotated[str, Field(pattern=r"^[a-f0-9]{64}$")] | None = None


class Verification(Frozen):
    status: Literal["TODO_REGULATORY_VALIDATION", "VERIFIED"] = TODO
    verified_by: str | None = None
    verified_at: datetime | None = None
    evidence: str | None = None

    @model_validator(mode="after")
    def evidence_required(self):
        if self.status == "VERIFIED" and not all(
            (self.verified_by, self.verified_at, self.evidence)
        ):
            raise ValueError("VERIFIED requires verifier, time and evidence")
        if self.verified_at and self.verified_at.tzinfo is None:
            raise ValueError("Verification timestamp must include timezone")
        return self


class Parameter(Frozen):
    name: Code
    # All numeric normative values must be exact strings; null means unresolved.
    value: str | None = None
    unit: str | None = None
    numeric: bool = False

    @field_validator("value", mode="before")
    @classmethod
    def strings_only(cls, value):
        if value is not None and not isinstance(value, str):
            raise ValueError("Parameter values must be strings or null")
        return value

    @model_validator(mode="after")
    def exact_number(self):
        if self.numeric and self.value is not None:
            value = Decimal(self.value)
            if not value.is_finite():
                raise ValueError("Nonfinite parameter")
            text = format(value, "f")
            if "." in text:
                text = text.rstrip("0").rstrip(".")
            object.__setattr__(self, "value", "0" if value == 0 else text)
        return self


class Rule(Frozen):
    key: Code
    section: int | None = Field(None, ge=1, le=17)
    kind: str
    description: str
    source: Source
    verification: Verification = Verification()
    dependencies: tuple[Code, ...] = ()
    blockers: tuple[str, ...] = ()
    parameters: tuple[Parameter, ...] = ()

    @model_validator(mode="after")
    def unique_parameters(self):
        if len({p.name for p in self.parameters}) != len(self.parameters):
            raise ValueError("Duplicate parameter")
        return self


class TestDefinition(Frozen):
    code: Code
    section: int = Field(ge=1, le=17)
    name: str
    parent: Code | None = None
    family: str | None = None
    source: Source
    dependencies: tuple[Code, ...]
    applicability: Literal["TODO_REGULATORY_VALIDATION"] = TODO
    implemented: Literal[False] = False
    verification: Verification = Verification()


class ChecklistDefinition(Frozen):
    key: Code
    group: Literal["GENERAL", "DIRECT_SALES", "ELECTRONIC", "SOFTWARE_CONTROLLED"]
    text: str
    source: Source
    applicability: Literal["TODO_REGULATORY_VALIDATION"] = TODO
    evidence_required: bool | None = None
    verification: Verification = Verification()


class Metadata(Frozen):
    schema_version: Literal[1]
    standard_code: Literal["OIML_R76"]
    standard_name: str
    edition: str
    version: str
    standard_parts: tuple[Source, ...]
    supported_test_codes: tuple[Code, ...]
    source_reference: str


class RuleFile(Frozen):
    schema_version: Literal[1]
    rules: tuple[Rule, ...]
    checklist: tuple[ChecklistDefinition, ...] = ()


class CatalogFile(Frozen):
    schema_version: Literal[1]
    tests: tuple[TestDefinition, ...]


def normalized(value):
    if isinstance(value, dict):
        result = {unicodedata.normalize("NFC", k): normalized(v) for k, v in value.items()}
        if len(result) != len(value):
            raise ValueError("Conflicting normalized keys")
        return result
    if isinstance(value, (tuple, list)):
        # Configuration arrays are sets of named items, never procedure observation sequences.
        values = [normalized(v) for v in value]
        return sorted(values, key=lambda v: json.dumps(v, sort_keys=True, ensure_ascii=False))
    if isinstance(value, datetime):
        return value.astimezone(UTC).isoformat()
    if isinstance(value, str):
        return unicodedata.normalize("NFC", value)
    if isinstance(value, float):
        raise ValueError("Binary floats are forbidden")
    return value


class RuleSet(Frozen):
    metadata: Metadata
    rules: tuple[Rule, ...]
    tests: tuple[TestDefinition, ...]
    checklist: tuple[ChecklistDefinition, ...]

    @model_validator(mode="after")
    def consistency(self):
        for values in (
            [r.key for r in self.rules],
            [t.code for t in self.tests],
            [c.key for c in self.checklist],
            list(self.metadata.supported_test_codes),
        ):
            if len(values) != len(set(values)):
                raise ValueError("Duplicate/conflicting identifier")
        rules = {r.key: r for r in self.rules}
        tests = {t.code: t for t in self.tests}
        for rule in self.rules:
            if not set(rule.dependencies) <= rules.keys():
                raise ValueError("Unknown rule dependency")

        def visit(key, ancestors):
            if key in ancestors:
                raise ValueError("Cyclic rule dependencies")
            for dependency in rules[key].dependencies:
                visit(dependency, ancestors | {key})

        for key in rules:
            visit(key, set())
        for test in self.tests:
            if not test.dependencies or not set(test.dependencies) <= rules.keys():
                raise ValueError("Unknown/missing test dependencies")
            if test.parent and (
                test.parent not in tests
                or tests[test.parent].parent
                or tests[test.parent].section != test.section
            ):
                raise ValueError("Invalid catalog parent")
        if not set(self.metadata.supported_test_codes) <= tests.keys():
            raise ValueError("Unknown supported test")
        declared = {(s.part, s.edition, s.identity) for s in self.metadata.standard_parts}
        for item in (*self.rules, *self.tests, *self.checklist):
            if (item.source.part, item.source.edition, item.source.identity) not in declared:
                raise ValueError("Undeclared standard/source")
        return self

    def snapshot(self) -> dict:
        return normalized(self.model_dump(mode="python"))

    @property
    def configuration_hash(self) -> str:
        encoded = json.dumps(
            self.snapshot(),
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
            allow_nan=False,
        ).encode()
        return hashlib.sha256(encoded).hexdigest()

    def activation_blockers(self) -> tuple[str, ...]:
        blockers = set()
        if not self.metadata.supported_test_codes:
            blockers.add("NO_SUPPORTED_TESTS")
        rules = {r.key: r for r in self.rules}
        tests = {t.code: t for t in self.tests}

        def check(item, key):
            if (
                item.verification.status != "VERIFIED"
                or not item.source.clause
                or not item.source.digest
            ):
                blockers.add(f"{key}:{TODO}")

        def dependency(key):
            rule = rules[key]
            check(rule, key)
            blockers.update(rule.blockers)
            if any(p.value is None for p in rule.parameters):
                blockers.add(f"{key}:UNRESOLVED_PARAMETER")
            for child in rule.dependencies:
                dependency(child)

        for code in self.metadata.supported_test_codes:
            test = tests[code]
            check(test, code)
            if not test.implemented:
                blockers.add(f"{code}:NOT_IMPLEMENTED")
            for key in test.dependencies:
                dependency(key)
        return tuple(sorted(blockers))


class UniqueLoader(yaml.SafeLoader):
    pass


def unique_mapping(loader, node, deep=False):
    pairs = loader.construct_pairs(node, deep=deep)
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("Duplicate YAML key")
        result[key] = value
    return result


UniqueLoader.add_constructor(yaml.resolver.BaseResolver.DEFAULT_MAPPING_TAG, unique_mapping)


def load_ruleset(directory: Path = ROOT) -> RuleSet:
    def read(name):
        path = directory / f"{name}.yaml"
        if path.stat().st_size > 1_000_000:
            raise ValueError("Configuration file too large")
        return yaml.load(path.read_text(encoding="utf-8"), Loader=UniqueLoader)

    metadata = Metadata.model_validate(read("metadata"))
    files = [RuleFile.model_validate(read(name)) for name in FILES]
    catalog = CatalogFile.model_validate(read("report_sections"))
    return RuleSet(
        metadata=metadata,
        rules=tuple(r for f in files for r in f.rules),
        tests=catalog.tests,
        checklist=tuple(c for f in files for c in f.checklist),
    )


class RuleSetRegistry:
    def __init__(self):
        self._versions: dict[tuple[str, str, str], RuleSet] = {}

    def register(self, ruleset: RuleSet):
        m = ruleset.metadata
        key = (m.standard_code, m.edition, m.version)
        existing = self._versions.get(key)
        if existing and existing.configuration_hash != ruleset.configuration_hash:
            raise ValueError("Version already registered with different content")
        self._versions[key] = ruleset

    def get(self, standard, edition, version, *, authoritative=False) -> RuleSet:
        result = self._versions[(standard, edition, version)]
        if authoritative and result.activation_blockers():
            raise ValueError("RULESET_NOT_VERIFIED")
        return result
