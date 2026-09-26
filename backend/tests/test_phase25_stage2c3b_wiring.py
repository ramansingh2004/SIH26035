"""Phase 25 Stage 2C3B contracts: Sections 1-5 use dual v1/v2 policy dispatch."""

import json
from datetime import UTC, datetime
from pathlib import Path

from app.compliance.domain import InstrumentSnapshot
from app.compliance.eccentricity import _eccentricity_policy
from app.compliance.numbers import decimal_value
from app.compliance.parameterized import (
    DirectedLoadExpression,
    DiscriminationPolicyCaseV2,
    DiscriminationPolicyV2,
    EccentricityPolicyCaseV2,
    EccentricityPolicyV2,
    EccentricityPositionV2,
    MassExpression,
    PolicySelector,
    RepeatabilityPolicyCaseV2,
    RepeatabilityPolicyV2,
    RepeatabilitySeriesPolicyV2,
    SensitivityPolicyCaseV2,
    SensitivityPolicyV2,
    TemperatureExpression,
    TemperatureZeroPolicyCaseV2,
    TemperatureZeroPolicyV2,
    WeighingPolicyCaseV2,
    WeighingPolicyV2,
)
from app.compliance.phase7 import _discrimination_policy, _sensitivity_policy
from app.compliance.phase8 import _temperature_zero_policy
from app.compliance.repeatability import _repeatability_policy
from app.compliance.ruleset import Metadata, Parameter, Rule, RuleSet, Source, Verification
from app.compliance.weighing import _weighing_policy

SOURCE = Source(
    part="R76-1",
    edition="2006",
    identity="SYNTHETIC STAGE2C3B CONTRACT SOURCE",
    clause="TEST",
    digest="b" * 64,
)
VERIFIED = Verification(
    status="VERIFIED",
    verified_by="phase25-contract-fixture",
    verified_at=datetime(2026, 9, 27, tzinfo=UTC),
    evidence="synthetic contract fixture only",
)
SELECTOR = PolicySelector(
    accuracy_classes=("III",),
    evaluation_contexts=("TYPE_EVALUATION",),
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
        "load_receptor_type": "PLATFORM",
        "support_point_count": 4,
        "maximum_tare_g": "5000",
        "declared_temp_min_c": "-10",
        "declared_temp_max_c": "40",
    }
    data.update(changes)
    return InstrumentSnapshot.model_validate(data)


def ruleset(key: str, kind: str, policy) -> RuleSet:
    rule = Rule(
        key=key,
        section=1,
        kind=kind,
        description="Synthetic Stage 2C3B policy fixture",
        source=SOURCE,
        verification=VERIFIED,
        parameters=(
            Parameter(
                name="POLICY_JSON",
                value=policy.model_dump_json(),
                numeric=False,
            ),
        ),
    )
    return RuleSet(
        metadata=Metadata(
            schema_version=1,
            standard_code="OIML_R76",
            standard_name="Synthetic Stage 2C3B contract",
            edition="R76-1:2006",
            version=f"SYNTHETIC_STAGE2C3B_{kind}",
            standard_parts=(SOURCE,),
            supported_test_codes=(),
            source_reference="SYNTHETIC CONTRACT FIXTURE ONLY",
        ),
        rules=(rule,),
        tests=(),
        checklist=(),
    )


def test_stage2c3b_section1_resolves_v2_weighing_policy():
    policy = WeighingPolicyV2(
        schema_version="v2",
        cases=(
            WeighingPolicyCaseV2(
                selector=SELECTOR,
                minimum_count=2,
                stages=("UP", "DOWN"),
                required_loads=(
                    DirectedLoadExpression(
                        direction="UP",
                        load=MassExpression(basis="MAX", value="0.5"),
                    ),
                ),
                require_min=False,
                require_max=False,
                require_preload=True,
                require_stabilization=True,
                minimum_warmup_seconds="0",
                zero_condition="ZERO",
                require_environment=False,
                require_equipment=False,
                require_certificate=False,
                require_evidence=False,
                require_monotonic_timestamps=True,
            ),
        ),
    )
    resolved = _weighing_policy(
        instrument_snapshot=instrument(),
        procedure_context=type(
            "Context",
            (),
            {"evaluation_context": "TYPE_EVALUATION", "range_no": 1},
        )(),
        ruleset=ruleset("SECTION1_PROCEDURE", "weighing_procedure_v2", policy),
    )
    assert resolved.required_loads[0].load_g == decimal_value("10000")


def test_stage2c3b_section2_resolves_v2_temperature_policy():
    policy = TemperatureZeroPolicyV2(
        schema_version="v2",
        cases=(
            TemperatureZeroPolicyCaseV2(
                selector=SELECTOR,
                minimum_count=3,
                temperature_sequence=(
                    TemperatureExpression(basis="DECLARED_MIN"),
                    TemperatureExpression(basis="ABSOLUTE_C", value="5"),
                    TemperatureExpression(basis="DECLARED_MAX"),
                ),
                normalization_span_c="5",
                limit_multiplier_e="1",
                operator="<=",
                semantics="ABSOLUTE",
                require_stabilized_observations=True,
                require_zero_tracking_disabled=True,
                require_declared_temperature_range=True,
                require_environment=False,
                require_equipment=False,
                require_certificate=False,
                require_evidence=False,
                require_monotonic_timestamps=True,
            ),
        ),
    )
    resolved = _temperature_zero_policy(
        instrument_snapshot=instrument(),
        procedure_context=type(
            "Context",
            (),
            {"evaluation_context": "TYPE_EVALUATION"},
        )(),
        ruleset=ruleset(
            "SECTION2_TEMPERATURE_ZERO_PROCEDURE",
            "temperature_zero_procedure_v2",
            policy,
        ),
    )
    assert resolved.required_temperature_sequence_c == (
        decimal_value("-10"),
        decimal_value("5"),
        decimal_value("40"),
    )


def test_stage2c3b_section3_resolves_v2_eccentricity_policy():
    policy = EccentricityPolicyV2(
        schema_version="v2",
        cases=(
            EccentricityPolicyCaseV2(
                selector=SELECTOR,
                procedure_variant="WEIGHTS",
                test_load=MassExpression(basis="MAX_PLUS_TARE", value="0.3"),
                minimum_count=1,
                position_strategy="EXPLICIT",
                explicit_positions=(EccentricityPositionV2(position_code="P1"),),
                allowed_receptor_types=("PLATFORM",),
                required_support_count=4,
                require_position_coordinates=True,
                require_environment=False,
                require_equipment=False,
                require_certificate=False,
                require_evidence=False,
                require_monotonic_timestamps=True,
            ),
        ),
    )
    resolved = _eccentricity_policy(
        instrument_snapshot=instrument(),
        procedure_context=type(
            "Context",
            (),
            {"evaluation_context": "TYPE_EVALUATION", "range_no": 1},
        )(),
        ruleset=ruleset("SECTION3_PROCEDURE", "eccentricity_procedure_v2", policy),
    )
    assert resolved.test_load_g == decimal_value("7500")
    assert resolved.required_positions[0].position_code == "P1"


def test_stage2c3b_section4_resolves_single_load_v2_policies():
    discrimination = DiscriminationPolicyV2(
        schema_version="v2",
        cases=(
            DiscriminationPolicyCaseV2(
                selector=SELECTOR,
                indication_mode="DIGITAL",
                minimum_count=1,
                test_loads=(MassExpression(basis="MAX", value="0.5"),),
                extra_load=MassExpression(basis="D", value="1.4"),
                minimum_indication_change=MassExpression(basis="D", value="1"),
                operator=">=",
                semantics="SIGNED",
                require_stabilization=True,
                require_environment=False,
                require_equipment=False,
                require_certificate=False,
                require_evidence=False,
                require_monotonic_timestamps=True,
            ),
        ),
    )
    d = _discrimination_policy(
        instrument_snapshot=instrument(),
        procedure_context=type(
            "Context",
            (),
            {"evaluation_context": "TYPE_EVALUATION", "range_no": 1},
        )(),
        ruleset=ruleset(
            "SECTION4_DISCRIMINATION_PROCEDURE",
            "discrimination_procedure_v2",
            discrimination,
        ),
    )
    assert d.test_load_g == decimal_value("10000")
    assert d.extra_load_g == decimal_value("14")

    sensitivity = SensitivityPolicyV2(
        schema_version="v2",
        cases=(
            SensitivityPolicyCaseV2(
                selector=PolicySelector(
                    accuracy_classes=("III",),
                    evaluation_contexts=("TYPE_EVALUATION",),
                    self_indicating=False,
                ),
                minimum_count=1,
                test_loads=(MassExpression(basis="MAX", value="1"),),
                extra_load=MassExpression(basis="ABSOLUTE_G", value="10"),
                minimum_displacement_mm="1",
                operator=">=",
                semantics="SIGNED",
                require_stabilization=True,
                require_environment=False,
                require_equipment=False,
                require_certificate=False,
                require_evidence=False,
                require_monotonic_timestamps=True,
            ),
        ),
    )
    s = _sensitivity_policy(
        instrument_snapshot=instrument(
            is_self_indicating=False,
            indication_type="ANALOG",
        ),
        procedure_context=type(
            "Context",
            (),
            {"evaluation_context": "TYPE_EVALUATION", "range_no": 1},
        )(),
        ruleset=ruleset(
            "SECTION4_SENSITIVITY_PROCEDURE",
            "sensitivity_procedure_v2",
            sensitivity,
        ),
    )
    assert s.test_load_g == decimal_value("20000")
    assert s.extra_load_g == decimal_value("10")


def test_stage2c3b_section5_resolves_v2_repeatability_policy():
    policy = RepeatabilityPolicyV2(
        schema_version="v2",
        cases=(
            RepeatabilityPolicyCaseV2(
                selector=SELECTOR,
                error_basis="CORRECTED",
                series=(
                    RepeatabilitySeriesPolicyV2(
                        series_code="HALF_MAX",
                        load=MassExpression(basis="MAX", value="0.5"),
                        minimum_repetitions=3,
                        range_limit_basis="MPE",
                        range_limit_multiplier="1",
                        range_operator="<=",
                        range_semantics="ABSOLUTE",
                    ),
                ),
                require_stabilization=True,
                require_environment=False,
                require_equipment=False,
                require_certificate=False,
                require_evidence=False,
                require_monotonic_timestamps=True,
            ),
        ),
    )
    resolved = _repeatability_policy(
        instrument_snapshot=instrument(),
        procedure_context=type(
            "Context",
            (),
            {"evaluation_context": "TYPE_EVALUATION", "range_no": 1},
        )(),
        ruleset=ruleset("SECTION5_PROCEDURE", "repeatability_procedure_v2", policy),
    )
    assert resolved.series[0].load_g == decimal_value("10000")


def test_stage2c3b_candidate_ruleset_remains_unpromoted():
    repo = Path(__file__).resolve().parents[2]
    root = repo / "backend" / "app" / "compliance" / "rules" / "oiml_r76_2006"
    metadata = json.loads((root / "metadata.yaml").read_text(encoding="utf-8"))
    mpe = json.loads((root / "mpe.yaml").read_text(encoding="utf-8"))

    assert metadata["version"] == "candidate-v1"
    assert metadata["supported_test_codes"] == []
    assert mpe["rules"][0]["key"] == "MPE_PENDING"
    assert mpe["rules"][0]["parameters"][0]["value"] is None
