"""Phase 25 Stage 2C3A contracts for dual v1/v2 regulatory dispatch."""

import json
from datetime import UTC, datetime
from pathlib import Path

import pytest

from app.compliance.domain import InstrumentSnapshot
from app.compliance.numbers import decimal_value
from app.compliance.parameterized import MpeProfileSetV2
from app.compliance.regulatory import (
    MpeProfile,
    RegulatoryBlocked,
    calculate_mpe_compatible,
    rule_policy_variant,
)
from app.compliance.ruleset import (
    Metadata,
    Parameter,
    Rule,
    RuleSet,
    Source,
    Verification,
)

SOURCE = Source(
    part="R76-1",
    edition="2006",
    identity="SYNTHETIC STAGE2C3A CONTRACT SOURCE",
    clause="3.5.1",
    digest="a" * 64,
)
VERIFIED = Verification(
    status="VERIFIED",
    verified_by="phase25-contract-fixture",
    verified_at=datetime(2026, 9, 27, tzinfo=UTC),
    evidence="synthetic contract fixture only",
)


def instrument():
    return InstrumentSnapshot.model_validate(
        {
            "accuracy_class": "III",
            "min_capacity_g": "200",
            "max_capacity_g": "20000",
            "verification_interval_e_g": "10",
            "scale_interval_d_g": "10",
            "verification_intervals_n": "2000",
            "ranges": [
                {
                    "range_no": 1,
                    "min_capacity_g": "200",
                    "max_capacity_g": "20000",
                    "verification_interval_e_g": "10",
                    "scale_interval_d_g": "10",
                    "verification_intervals_n": "2000",
                }
            ],
            "range_type": "SINGLE",
            "indication_type": "DIGITAL",
            "is_self_indicating": True,
        }
    )


def policy_json(kind: str):
    profile = {
        "schema_version": "v1",
        "accuracy_class": "III",
        "evaluation_context": "TYPE_EVALUATION",
        "operator": "<=",
        "semantics": "ABSOLUTE",
        "bands": [
            {
                "lower_e": "0",
                "upper_e": "500",
                "lower_operator": ">=",
                "upper_operator": "<=",
                "multiplier_e": "0.5",
            },
            {
                "lower_e": "500",
                "upper_e": "2000",
                "lower_operator": ">",
                "upper_operator": "<=",
                "multiplier_e": "1",
            },
        ],
    }
    if kind == "mpe_profile_v1":
        return profile
    return {"schema_version": "v2", "profiles": [profile]}


def ruleset(kind: str) -> RuleSet:
    source = SOURCE
    rule = Rule(
        key="TEST_MPE",
        section=1,
        kind=kind,
        description="Synthetic Stage 2C3A dispatch fixture",
        source=source,
        verification=VERIFIED,
        parameters=(
            Parameter(
                name="POLICY_JSON",
                value=json.dumps(policy_json(kind), separators=(",", ":")),
                numeric=False,
            ),
        ),
    )
    return RuleSet(
        metadata=Metadata(
            schema_version=1,
            standard_code="OIML_R76",
            standard_name="Synthetic Stage 2C3A contract",
            edition="R76-1:2006",
            version=f"SYNTHETIC_STAGE2C3A_{kind}",
            standard_parts=(source,),
            supported_test_codes=(),
            source_reference="SYNTHETIC CONTRACT FIXTURE ONLY",
        ),
        rules=(rule,),
        tests=(),
        checklist=(),
    )


def test_stage2c3a_rule_policy_variant_resolves_v1_without_changing_schema():
    kind, policy = rule_policy_variant(
        ruleset("mpe_profile_v1"),
        "TEST_MPE",
        (
            ("mpe_profile_v1", MpeProfile),
            ("mpe_profile_set_v2", MpeProfileSetV2),
        ),
    )
    assert kind == "mpe_profile_v1"
    assert isinstance(policy, MpeProfile)


def test_stage2c3a_rule_policy_variant_resolves_v2_typed_schema():
    kind, policy = rule_policy_variant(
        ruleset("mpe_profile_set_v2"),
        "TEST_MPE",
        (
            ("mpe_profile_v1", MpeProfile),
            ("mpe_profile_set_v2", MpeProfileSetV2),
        ),
    )
    assert kind == "mpe_profile_set_v2"
    assert isinstance(policy, MpeProfileSetV2)


@pytest.mark.parametrize("kind", ["mpe_profile_v1", "mpe_profile_set_v2"])
def test_stage2c3a_compatible_mpe_produces_same_exact_result(kind):
    item = instrument()
    selected = item.select_range(1)
    result = calculate_mpe_compatible(
        load_g="10000",
        selected_range=selected,
        accuracy_class=item.accuracy_class,
        evaluation_context="TYPE_EVALUATION",
        ruleset=ruleset(kind),
        rule_id="TEST_MPE",
    )
    assert result.value == decimal_value("10")
    assert result.operator == "<="
    assert result.semantics == "ABSOLUTE"


def test_stage2c3a_incompatible_kind_fails_closed():
    rs = ruleset("mpe_profile_v1")
    with pytest.raises(RegulatoryBlocked):
        rule_policy_variant(
            rs,
            "TEST_MPE",
            (("mpe_profile_set_v2", MpeProfileSetV2),),
        )


def test_stage2c3a_candidate_ruleset_remains_unpromoted():
    repo = Path(__file__).resolve().parents[2]
    rules = repo / "backend" / "app" / "compliance" / "rules" / "oiml_r76_2006"
    metadata = json.loads((rules / "metadata.yaml").read_text(encoding="utf-8"))
    mpe = json.loads((rules / "mpe.yaml").read_text(encoding="utf-8"))

    assert metadata["version"] == "candidate-v1"
    assert metadata["supported_test_codes"] == []
    assert mpe["rules"][0]["key"] == "MPE_PENDING"
    assert mpe["rules"][0]["parameters"][0]["value"] is None
