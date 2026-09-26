"""Phase 25 Stage 2C3C native Section 4 multi-load/MPE contracts."""

import json
from dataclasses import replace
from datetime import UTC, datetime
from pathlib import Path

from app.compliance.domain import ComplianceOutcome, EvaluationStatus, InstrumentSnapshot
from app.compliance.engine import R76Engine
from app.compliance.evaluators import EvaluatorRegistry
from app.compliance.parameterized import (
    DiscriminationPolicyCaseV2,
    DiscriminationPolicyV2,
    MassExpression,
    MpeProfileSetV2,
    PolicySelector,
    SensitivityPolicyCaseV2,
    SensitivityPolicyV2,
)
from app.compliance.phase7 import (
    DISCRIMINATION,
    DISCRIMINATION_CALIBRATION,
    DISCRIMINATION_CLASSIFICATION,
    DISCRIMINATION_POLICY,
    SENSITIVITY,
    SENSITIVITY_CALIBRATION,
    SENSITIVITY_CLASSIFICATION,
    SENSITIVITY_POLICY,
    DiscriminationContext,
    SensitivityContext,
    discrimination_registration,
    sensitivity_registration,
)
from app.compliance.ruleset import RuleSet
from app.compliance.section4_v2 import (
    ResolvedDiscriminationPolicyV2,
    ResolvedSensitivityPolicyV2,
)

SOURCE = {
    "part": "R76-1",
    "edition": "2006",
    "identity": "SYNTHETIC TEST FIXTURE STAGE2C3C",
    "clause": "SYNTHETIC",
    "digest": "c" * 64,
}
VERIFICATION = {
    "status": "VERIFIED",
    "verified_by": "phase25-contract-fixture",
    "verified_at": datetime(2026, 9, 27, tzinfo=UTC).isoformat(),
    "evidence": "synthetic contract fixture only",
}
SELECTOR = PolicySelector(
    accuracy_classes=("III",),
    evaluation_contexts=("SYNTHETIC",),
)


def instrument(**changes):
    data = {
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
    data.update(changes)
    return InstrumentSnapshot.model_validate(data)


def _rule(key, kind, *, policy=None, dependencies=()):
    parameters = []
    if policy is not None:
        parameters.append(
            {
                "name": "POLICY_JSON",
                "value": policy.model_dump_json(),
                "numeric": False,
            }
        )
    return {
        "key": key,
        "section": 4,
        "kind": kind,
        "description": "SYNTHETIC TEST FIXTURE ONLY",
        "source": SOURCE,
        "verification": VERIFICATION,
        "dependencies": list(dependencies),
        "parameters": parameters,
    }


def _app_policy(variant, *, sensitivity=False):
    cases = (
        [
            {
                "when": {
                    "kind": "boolean",
                    "feature": "is_self_indicating",
                    "expected": False,
                },
                "decision": "REQUIRED",
                "reason": "SYNTHETIC non-self-indicating case",
            },
            {
                "when": {"kind": "always"},
                "decision": "NOT_APPLICABLE",
                "reason": "SYNTHETIC self-indicating exclusion",
            },
        ]
        if sensitivity
        else [
            {
                "when": {"kind": "always"},
                "decision": "REQUIRED",
                "reason": "SYNTHETIC required case",
            }
        ]
    )
    return {
        "schema_version": "v1",
        "scope": "EACH_RANGE",
        "scenarios": [{"procedure_variant": variant, "scenario": "fixture"}],
        "cases": cases,
    }


def _ruleset(*,code, variant, policy_key, policy_kind, policy, extras, sensitivity=False, mpe=None):
    app_key = f"{code}_APP"
    rules = [
        _rule("BASE", "dependency_v1"),
        _rule(
            app_key,
            "applicability_policy_v1",
            policy=type(policy).model_validate(_app_policy(variant, sensitivity=sensitivity))
            if False
            else None,
        ),
    ]
    # ApplicabilityPolicy is intentionally encoded directly to keep this fixture local.
    rules[-1]["parameters"] = [
        {
            "name": "POLICY_JSON",
            "value": json.dumps(_app_policy(variant, sensitivity=sensitivity)),
            "numeric": False,
        }
    ]
    rules.append(_rule(policy_key, policy_kind, policy=policy))
    rules.extend(_rule(key, "dependency_v1") for key in extras)

    dependencies = [app_key, policy_key, *extras]
    if mpe is not None:
        rules.append(_rule("SECTION4_MPE_TEST", "mpe_profile_set_v2", policy=mpe))
        dependencies.append("SECTION4_MPE_TEST")

    return RuleSet.model_validate(
        {
            "metadata": {
                "schema_version": 1,
                "standard_code": "OIML_R76",
                "standard_name": "SYNTHETIC",
                "edition": "TEST-PHASE25-2C3C",
                "version": f"SYNTHETIC_TEST_STAGE2C3C_{code}",
                "standard_parts": [SOURCE],
                "supported_test_codes": [code],
                "source_reference": "SYNTHETIC TEST FIXTURE ONLY",
            },
            "rules": rules,
            "tests": [
                {
                    "code": code,
                    "section": 4,
                    "name": "SYNTHETIC TEST FIXTURE ONLY",
                    "source": SOURCE,
                    "dependencies": dependencies,
                    "implemented": True,
                    "verification": VERIFICATION,
                }
            ],
            "checklist": [],
        }
    )


def discrimination_policy():
    return DiscriminationPolicyV2(
        schema_version="v2",
        cases=(
            DiscriminationPolicyCaseV2(
                selector=SELECTOR,
                indication_mode="DIGITAL",
                minimum_count=2,
                test_loads=(
                    MassExpression(basis="MIN", value="1"),
                    MassExpression(basis="MAX", value="0.5"),
                ),
                extra_load=MassExpression(basis="D", value="1.4"),
                minimum_indication_change=MassExpression(basis="D", value="1"),
                operator=">=",
                semantics="SIGNED",
                require_stabilization=False,
                require_environment=False,
                require_equipment=False,
                require_certificate=False,
                require_evidence=False,
                require_monotonic_timestamps=True,
            ),
        ),
    )


def sensitivity_policy():
    return SensitivityPolicyV2(
        schema_version="v2",
        cases=(
            SensitivityPolicyCaseV2(
                selector=PolicySelector(
                    accuracy_classes=("III",),
                    evaluation_contexts=("SYNTHETIC",),
                    self_indicating=False,
                ),
                minimum_count=2,
                test_loads=(
                    MassExpression(basis="E", value="500"),
                    MassExpression(basis="E", value="1000"),
                ),
                extra_load=MassExpression(basis="MPE", value="1"),
                minimum_displacement_mm="1",
                operator=">=",
                semantics="SIGNED",
                require_stabilization=False,
                require_environment=False,
                require_equipment=False,
                require_certificate=False,
                require_evidence=False,
                require_monotonic_timestamps=True,
            ),
        ),
    )


def mpe_policy():
    return MpeProfileSetV2.model_validate(
        {
            "schema_version": "v2",
            "profiles": [
                {
                    "schema_version": "v1",
                    "accuracy_class": "III",
                    "evaluation_context": "SYNTHETIC",
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
            ],
        }
    )


def _engine(registration):
    return R76Engine(
        EvaluatorRegistry((replace(registration, synthetic_fixture=True),))
    )


def test_stage2c3c_discrimination_multi_load_executes_natively():
    policy = discrimination_policy()
    ruleset = _ruleset(
        code=DISCRIMINATION,
        variant="DIGITAL",
        policy_key=DISCRIMINATION_POLICY,
        policy_kind="discrimination_procedure_v2",
        policy=policy,
        extras=(DISCRIMINATION_CLASSIFICATION, DISCRIMINATION_CALIBRATION),
    )
    registration = discrimination_registration()
    context = DiscriminationContext.model_validate(
        {
            "evaluation_context": "SYNTHETIC",
            "range_no": 1,
            "scenario": "fixture",
            "procedure_variant": "DIGITAL",
            "indication_mode": "DIGITAL",
        }
    )
    observations = registration.observations.parse(
        test_code=DISCRIMINATION,
        protocol="DISCRIMINATION_V1",
        version="v1",
        rows=[
            {
                "sequence_no": 1,
                "load_g": "200",
                "extra_load_g": "14",
                "indication_before_g": "200",
                "indication_after_g": "210",
                "measured_at": "2000-01-01T00:00:01Z",
            },
            {
                "sequence_no": 2,
                "load_g": "10000",
                "extra_load_g": "14",
                "indication_before_g": "10000",
                "indication_after_g": "10010",
                "measured_at": "2000-01-01T00:00:02Z",
            },
        ],
    )

    result = _engine(registration).evaluate(
        test_code=DISCRIMINATION,
        instrument_snapshot=instrument(),
        procedure_context=context,
        observations=observations,
        ruleset=ruleset,
    )

    assert result.evaluation_status == EvaluationStatus.COMPLETE
    assert result.compliance_outcome == ComplianceOutcome.COMPLIANT
    assert len(result.acceptance_limits) == 2


def test_stage2c3c_discrimination_requires_every_v2_test_load():
    policy = discrimination_policy()
    ruleset = _ruleset(
        code=DISCRIMINATION,
        variant="DIGITAL",
        policy_key=DISCRIMINATION_POLICY,
        policy_kind="discrimination_procedure_v2",
        policy=policy,
        extras=(DISCRIMINATION_CLASSIFICATION, DISCRIMINATION_CALIBRATION),
    )
    registration = discrimination_registration()
    context = DiscriminationContext.model_validate(
        {
            "evaluation_context": "SYNTHETIC",
            "range_no": 1,
            "scenario": "fixture",
            "procedure_variant": "DIGITAL",
            "indication_mode": "DIGITAL",
        }
    )
    observations = registration.observations.parse(
        test_code=DISCRIMINATION,
        protocol="DISCRIMINATION_V1",
        version="v1",
        rows=[
            {
                "sequence_no": 1,
                "load_g": "200",
                "extra_load_g": "14",
                "indication_before_g": "200",
                "indication_after_g": "210",
                "measured_at": "2000-01-01T00:00:01Z",
            }
        ],
    )
    result = _engine(registration).evaluate(
        test_code=DISCRIMINATION,
        instrument_snapshot=instrument(),
        procedure_context=context,
        observations=observations,
        ruleset=ruleset,
    )
    assert result.evaluation_status == EvaluationStatus.INCOMPLETE
    assert result.compliance_outcome == ComplianceOutcome.UNDETERMINED


def test_stage2c3c_sensitivity_multi_load_resolves_mpe_per_load():
    policy = sensitivity_policy()
    ruleset = _ruleset(
        code=SENSITIVITY,
        variant="NON_SELF_INDICATING",
        policy_key=SENSITIVITY_POLICY,
        policy_kind="sensitivity_procedure_v2",
        policy=policy,
        extras=(SENSITIVITY_CLASSIFICATION, SENSITIVITY_CALIBRATION),
        sensitivity=True,
        mpe=mpe_policy(),
    )
    registration = sensitivity_registration()
    context = SensitivityContext.model_validate(
        {
            "evaluation_context": "SYNTHETIC",
            "range_no": 1,
            "scenario": "fixture",
        }
    )
    observations = registration.observations.parse(
        test_code=SENSITIVITY,
        protocol="SENSITIVITY_V1",
        version="v1",
        rows=[
            {
                "sequence_no": 1,
                "load_g": "5000",
                "extra_load_g": "5",
                "permanent_displacement_mm": "1",
                "measured_at": "2000-01-01T00:00:01Z",
            },
            {
                "sequence_no": 2,
                "load_g": "10000",
                "extra_load_g": "10",
                "permanent_displacement_mm": "1",
                "measured_at": "2000-01-01T00:00:02Z",
            },
        ],
    )

    result = _engine(registration).evaluate(
        test_code=SENSITIVITY,
        instrument_snapshot=instrument(
            is_self_indicating=False,
            indication_type="ANALOG",
        ),
        procedure_context=context,
        observations=observations,
        ruleset=ruleset,
    )

    assert result.evaluation_status == EvaluationStatus.COMPLETE
    assert result.compliance_outcome == ComplianceOutcome.COMPLIANT
    assert len(result.acceptance_limits) == 2


def test_stage2c3c_runtime_helpers_return_native_resolved_v2_shapes():
    from app.compliance.phase7 import _discrimination_policy, _sensitivity_policy

    d_rules = _ruleset(
        code=DISCRIMINATION,
        variant="DIGITAL",
        policy_key=DISCRIMINATION_POLICY,
        policy_kind="discrimination_procedure_v2",
        policy=discrimination_policy(),
        extras=(DISCRIMINATION_CLASSIFICATION, DISCRIMINATION_CALIBRATION),
    )
    d = _discrimination_policy(
        instrument_snapshot=instrument(),
        procedure_context=type(
            "Context",
            (),
            {"evaluation_context": "SYNTHETIC", "range_no": 1},
        )(),
        ruleset=d_rules,
    )
    assert isinstance(d, ResolvedDiscriminationPolicyV2)
    assert len(d.loads) == 2

    s_rules = _ruleset(
        code=SENSITIVITY,
        variant="NON_SELF_INDICATING",
        policy_key=SENSITIVITY_POLICY,
        policy_kind="sensitivity_procedure_v2",
        policy=sensitivity_policy(),
        extras=(SENSITIVITY_CLASSIFICATION, SENSITIVITY_CALIBRATION),
        sensitivity=True,
        mpe=mpe_policy(),
    )
    s = _sensitivity_policy(
        instrument_snapshot=instrument(
            is_self_indicating=False,
            indication_type="ANALOG",
        ),
        procedure_context=type(
            "Context",
            (),
            {"evaluation_context": "SYNTHETIC", "range_no": 1},
        )(),
        ruleset=s_rules,
    )
    assert isinstance(s, ResolvedSensitivityPolicyV2)
    assert [str(item.extra_load_g) for item in s.loads] == ["5.0", "10"]


def test_stage2c3c_candidate_ruleset_remains_unpromoted():
    repo = Path(__file__).resolve().parents[2]
    root = repo / "backend" / "app" / "compliance" / "rules" / "oiml_r76_2006"
    metadata = json.loads((root / "metadata.yaml").read_text(encoding="utf-8"))
    mpe = json.loads((root / "mpe.yaml").read_text(encoding="utf-8"))

    assert metadata["version"] == "candidate-v1"
    assert metadata["supported_test_codes"] == []
    assert mpe["rules"][0]["key"] == "MPE_PENDING"
    assert mpe["rules"][0]["parameters"][0]["value"] is None
