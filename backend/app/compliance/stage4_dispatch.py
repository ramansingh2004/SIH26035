"""Safe dual-policy dispatch boundary for Phase 25 Stage 4.

Legacy v1 policies remain executable. Native v2 policies are schema-valid but
deliberately blocked from authoritative runtime until independent verification
and final activation gates are complete.
"""

from app.compliance.regulatory import (
    DependencyResolution,
    RegulatoryBlocked,
    dependencies,
    rule_policy_variant,
)


def _blocked(ruleset, key):
    refs = dependencies(ruleset, (key,)).rule_references
    return RegulatoryBlocked(
        DependencyResolution(
            unresolved_rule_ids=(key,),
            rule_references=refs,
        )
    )


def load_stage4_policy_for_runtime(
    *,
    ruleset,
    key,
    legacy_kind,
    legacy_schema,
    v2_kind,
    v2_schema,
):
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


__all__ = ["load_stage4_policy_for_runtime"]
