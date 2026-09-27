"""Phase 25 Stage 3C runtime-dispatch boundary.

Stage 3C recognizes verified v1/v2 policy kinds for Sections 6–10 while
preserving the legacy v1 execution path.

A v2 policy is deliberately blocked here until the evaluator has a native v2
procedure/observation execution path. This prevents a verified v2 policy from
being silently coerced into a legacy schema and losing regulatory semantics.
"""

from app.compliance.regulatory import (
    DependencyResolution,
    RegulatoryBlocked,
    dependencies,
    rule_policy_variant,
)


def _blocked(ruleset, key):
    return RegulatoryBlocked(
        DependencyResolution(
            unresolved_rule_ids=(key,),
            rule_references=dependencies(ruleset, (key,)).rule_references,
        )
    )


def load_stage3_policy_for_runtime(
    *,
    ruleset,
    key,
    legacy_kind,
    legacy_schema,
    v2_kind,
    v2_schema,
):
    """Return the legacy policy or fail closed for a v2 runtime path."""

    kind, policy = rule_policy_variant(
        ruleset,
        key,
        (
            (legacy_kind, legacy_schema),
            (v2_kind, v2_schema),
        ),
    )
    if kind == legacy_kind:
        return policy

    raise _blocked(ruleset, key)


__all__ = ["load_stage3_policy_for_runtime"]
