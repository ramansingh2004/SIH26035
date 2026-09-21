"""Pure adapters over the unchanged Phase 3 RuleSet. Never load files during evaluation."""

from typing import Literal

from pydantic import Field, model_validator

from app.compliance.canonical import strict_json
from app.compliance.domain import (
    AcceptanceLimit,
    Frozen,
    InstrumentRangeSnapshot,
    Number,
    RuleReference,
)
from app.compliance.numbers import Operator, Semantics, compare_ratio, decimal_value, exact
from app.compliance.ruleset import TODO, RuleSet

SUPPORTED_KINDS = ("applicability_policy_v1", "mpe_profile_v1", "procedure_v1", "dependency_v1")


class RegulatoryBlocked(ValueError):
    def __init__(self, resolution):
        self.resolution = resolution
        super().__init__(TODO + ": " + ", ".join(resolution.unresolved_rule_ids))


class DependencyResolution(Frozen):
    unresolved_rule_ids: tuple[str, ...]
    rule_references: tuple[RuleReference, ...]

    @property
    def verified(self):
        return not self.unresolved_rule_ids


def reference(item, key: str) -> RuleReference:
    source = item.source
    return RuleReference(
        rule_id=key,
        part=source.part,
        edition=source.edition,
        source_identity=source.identity,
        clause=source.clause,
        source_digest=source.digest,
    )


def verified(item) -> bool:
    return bool(
        item.verification.status == "VERIFIED"
        and item.source.clause
        and item.source.digest
        and item.verification.evidence
        and item.verification.verified_at
        and item.verification.verified_by
    )


def dependencies(
    ruleset: RuleSet,
    required: tuple[str, ...],
    *,
    supported_kinds: tuple[str, ...] = SUPPORTED_KINDS,
) -> DependencyResolution:
    rules = {r.key: r for r in ruleset.rules}
    visited, unresolved, refs = set(), set(), {}

    def visit(key):
        if key in visited:
            return
        visited.add(key)
        rule = rules.get(key)
        if rule is None:
            unresolved.add(key)
            return
        refs[key] = reference(rule, key)
        if (
            not verified(rule)
            or rule.kind not in supported_kinds
            or any(p.value is None for p in rule.parameters)
        ):
            unresolved.add(key)
        for blocker in rule.blockers:
            unresolved.add(blocker.split(":", 1)[0])
        for dependency in rule.dependencies:
            visit(dependency)

    for key in required:
        visit(key)
    return DependencyResolution(
        unresolved_rule_ids=tuple(sorted(unresolved)),
        rule_references=tuple(refs[k] for k in sorted(refs)),
    )


def rule_policy(ruleset: RuleSet, key: str, kind: str, schema):
    resolution = dependencies(ruleset, (key,))
    if not resolution.verified:
        raise RegulatoryBlocked(resolution)
    rule = next(r for r in ruleset.rules if r.key == key)
    try:
        if rule.kind != kind:
            raise ValueError("Rule kind incompatible with policy schema")
        parameters = {p.name: p for p in rule.parameters}
        if set(parameters) != {"POLICY_JSON"} or parameters["POLICY_JSON"].numeric:
            raise ValueError("Policy requires exactly one typed POLICY_JSON parameter")
        return schema.model_validate(strict_json(parameters["POLICY_JSON"].value))
    except ValueError as exc:
        raise RegulatoryBlocked(
            DependencyResolution(
                unresolved_rule_ids=(key,), rule_references=resolution.rule_references
            )
        ) from exc


class MpeBand(Frozen):
    lower_e: Number = Field(ge=0)
    upper_e: Number | None = Field(None, gt=0)
    lower_operator: Literal[">", ">="]
    upper_operator: Literal["<", "<="]
    multiplier_e: Number = Field(ge=0)

    @model_validator(mode="after")
    def bounds(self):
        if self.upper_e is not None and self.upper_e <= self.lower_e:
            raise ValueError("Invalid MPE band")
        return self


class MpeProfile(Frozen):
    schema_version: Literal["v1"]
    accuracy_class: Literal["I", "II", "III", "IIII"]
    evaluation_context: str
    operator: Operator
    semantics: Semantics
    bands: tuple[MpeBand, ...] = Field(min_length=1)

    @model_validator(mode="after")
    def bands_disjoint(self):
        ordered = tuple(sorted(self.bands, key=lambda b: b.lower_e))
        for previous, current in zip(ordered, ordered[1:], strict=False):
            if (
                previous.upper_e is None
                or previous.upper_e > current.lower_e
                or (
                    previous.upper_e == current.lower_e
                    and previous.upper_operator == "<="
                    and current.lower_operator == ">="
                )
            ):
                raise ValueError("Conflicting MPE bands")
        object.__setattr__(self, "bands", ordered)
        return self


def calculate_mpe(
    *,
    load_g,
    selected_range: InstrumentRangeSnapshot,
    accuracy_class: str,
    evaluation_context: str,
    ruleset: RuleSet,
    rule_id: str,
) -> AcceptanceLimit:
    profile = rule_policy(ruleset, rule_id, "mpe_profile_v1", MpeProfile)
    if (profile.accuracy_class, profile.evaluation_context) != (accuracy_class, evaluation_context):
        raise ValueError("MPE profile incompatible with class/evaluation context")
    load = decimal_value(load_g)
    if load < 0 or load > selected_range.max_capacity_g:
        raise ValueError("Load outside selected range")
    matches = [
        b
        for b in profile.bands
        if (
            compare_ratio(
                load, selected_range.verification_interval_e_g, b.lower_e, operator=b.lower_operator
            )
            and (
                b.upper_e is None
                or compare_ratio(
                    load,
                    selected_range.verification_interval_e_g,
                    b.upper_e,
                    operator=b.upper_operator,
                )
            )
        )
    ]
    if len(matches) != 1:
        raise RegulatoryBlocked(
            DependencyResolution(
                unresolved_rule_ids=(rule_id,),
                rule_references=dependencies(ruleset, (rule_id,)).rule_references,
            )
        )
    return AcceptanceLimit(
        name="mpe",
        value=exact("multiply", matches[0].multiplier_e, selected_range.verification_interval_e_g),
        unit="g",
        operator=profile.operator,
        semantics=profile.semantics,
        rule_references=dependencies(ruleset, (rule_id,)).rule_references,
    )
