"""SYNTHETIC TEST FIXTURES for Phase 6 core reusable evaluators only.

Nothing here is seedable production configuration or regulatory authority.
"""

import json
from dataclasses import replace
from datetime import UTC, datetime, timedelta

from app.compliance.eccentricity import (
    CALIBRATION as E_CALIBRATION,
)
from app.compliance.eccentricity import (
    CLASSIFICATION as E_CLASSIFICATION,
)
from app.compliance.eccentricity import (
    CODE as ECCENTRICITY,
)
from app.compliance.eccentricity import (
    GEOMETRY as E_GEOMETRY,
)
from app.compliance.eccentricity import (
    MPE as E_MPE,
)
from app.compliance.eccentricity import (
    POLICY as E_POLICY,
)
from app.compliance.eccentricity import (
    EccentricityContext,
    section3_registration,
)
from app.compliance.engine import R76Engine
from app.compliance.evaluators import EvaluatorRegistry
from app.compliance.repeatability import (
    CALIBRATION as R_CALIBRATION,
)
from app.compliance.repeatability import (
    CLASSIFICATION as R_CLASSIFICATION,
)
from app.compliance.repeatability import (
    CODE as REPEATABILITY,
)
from app.compliance.repeatability import (
    MPE as R_MPE,
)
from app.compliance.repeatability import (
    POLICY as R_POLICY,
)
from app.compliance.repeatability import (
    RepeatabilityContext,
    section5_registration,
)
from app.compliance.ruleset import RuleSet
from app.compliance.tare import (
    CALIBRATION as T_CALIBRATION,
)
from app.compliance.tare import (
    CLASSIFICATION as T_CLASSIFICATION,
)
from app.compliance.tare import (
    CODE as TARE,
)
from app.compliance.tare import (
    MPE as T_MPE,
)
from app.compliance.tare import (
    POLICY as T_POLICY,
)
from app.compliance.tare import (
    TARE_RULE,
    TareContext,
    section9_registration,
)
from domain_tests.fixtures.synthetic import SOURCE, VERIFICATION, instrument


def _app_policy(variant):
    return dict(
        schema_version="v1",
        scope="EACH_RANGE",
        scenarios=[dict(procedure_variant=variant, scenario="fixture")],
        cases=[dict(when={"kind": "always"}, decision="REQUIRED", reason="Synthetic required")],
    )


def _mpe_policy(operator="<="):
    return dict(
        schema_version="v1",
        accuracy_class="III",
        evaluation_context="SYNTHETIC",
        operator=operator,
        semantics="ABSOLUTE",
        bands=[
            dict(
                lower_e="0",
                upper_e=None,
                lower_operator=">=",
                upper_operator="<=",
                multiplier_e="1",
            )
        ],
    )


def _rule(key, kind, policy=None, *, verification=VERIFICATION, dependencies=("BASE",)):
    return dict(
        key=key,
        kind=kind,
        description="SYNTHETIC TEST FIXTURE ONLY",
        source=SOURCE,
        verification=verification,
        dependencies=list(dependencies),
        parameters=[] if policy is None else [dict(name="POLICY_JSON", value=json.dumps(policy))],
    )


def _ruleset(*, code, section, variant, policy_key, policy_kind, policy, mpe_key, extras=()):
    rules = [
        _rule("BASE", "dependency_v1", dependencies=()),
        _rule("APP", "applicability_policy_v1", _app_policy(variant)),
        _rule(mpe_key, "mpe_profile_v1", _mpe_policy()),
        _rule(policy_key, policy_kind, policy),
    ]
    rules.extend(_rule(key, "dependency_v1") for key in extras)
    dependencies = ["APP", mpe_key, policy_key, *extras]
    return RuleSet.model_validate(
        dict(
            metadata=dict(
                schema_version=1,
                standard_code="OIML_R76",
                standard_name="SYNTHETIC",
                edition="TEST-v1",
                version=f"SYNTHETIC_TEST_PHASE6_{code}",
                standard_parts=[SOURCE],
                supported_test_codes=[code],
                source_reference="SYNTHETIC TEST FIXTURE ONLY",
            ),
            rules=rules,
            tests=[
                dict(
                    code=code,
                    section=section,
                    name="SYNTHETIC TEST FIXTURE ONLY",
                    source=SOURCE,
                    dependencies=dependencies,
                    verification=VERIFICATION,
                )
            ],
            checklist=[],
        )
    )


def _unverify(ruleset, key):
    data = ruleset.model_dump(mode="json")
    for rule in data["rules"]:
        if rule["key"] == key:
            rule["verification"] = {}
    return RuleSet.model_validate(data)


def eccentricity_rules(**changes):
    policy = dict(
        schema_version="v1",
        evaluation_context="SYNTHETIC",
        indication_type="DIGITAL",
        range_type="SINGLE",
        procedure_variant="WEIGHTS",
        test_load_g="5000",
        minimum_count=4,
        required_positions=[
            dict(position_code="Q1", rolling_direction=None),
            dict(position_code="Q2", rolling_direction=None),
            dict(position_code="Q3", rolling_direction=None),
            dict(position_code="Q4", rolling_direction=None),
        ],
        allowed_receptor_types=["RECTANGULAR"],
        required_support_count=4,
        require_position_coordinates=True,
        require_environment=True,
        require_equipment=True,
        require_certificate=False,
        require_evidence=True,
        require_monotonic_timestamps=True,
    )
    policy.update(changes)
    return _ruleset(
        code=ECCENTRICITY,
        section=3,
        variant=policy["procedure_variant"],
        policy_key=E_POLICY,
        policy_kind="eccentricity_procedure_v1",
        policy=policy,
        mpe_key=E_MPE,
        extras=(E_CLASSIFICATION, E_CALIBRATION, E_GEOMETRY),
    )


def eccentricity_context(**changes):
    return EccentricityContext.model_validate(
        dict(
            evaluation_context="SYNTHETIC",
            range_no=1,
            scenario="fixture",
            procedure_variant="WEIGHTS",
            load_receptor_type="RECTANGULAR",
            support_count=4,
            positions=[
                dict(position_code="Q1", x_mm="-100", y_mm="100"),
                dict(position_code="Q2", x_mm="100", y_mm="100"),
                dict(position_code="Q3", x_mm="100", y_mm="-100"),
                dict(position_code="Q4", x_mm="-100", y_mm="-100"),
            ],
            environment=[dict(measured_at="2000-01-01T00:00:00Z", temperature_c="20")],
            equipment=[dict(reference="SYNTHETIC_WEIGHT", category="SYNTHETIC")],
            evidence_hashes=["b" * 64],
        )
        | changes
    )


def eccentricity_observations(*, errors=("0", "5", "-5", "10"), rolling=False):
    registration = section3_registration()
    rows = []
    for index, (position, error) in enumerate(
        zip(("Q1", "Q2", "Q3", "Q4"), errors, strict=True), 1
    ):
        rows.append(
            dict(
                sequence_no=index,
                position_code=position,
                rolling_direction="FORWARD" if rolling else None,
                load_g="5000",
                indication_g=str(5000 + int(error)),
                additional_load_g="5",
                zero_error_g="0",
                measured_at=(
                    datetime(2000, 1, 1, tzinfo=UTC) + timedelta(seconds=index)
                ).isoformat(),
            )
        )
    return registration.observations.parse(
        test_code=ECCENTRICITY, protocol="ECCENTRICITY_V1", version="v1", rows=rows
    )


def eccentricity_engine():
    return R76Engine(EvaluatorRegistry((replace(section3_registration(), synthetic_fixture=True),)))


def evaluate_eccentricity(**changes):
    arguments = dict(
        test_code=ECCENTRICITY,
        instrument_snapshot=instrument(
            indication_type="DIGITAL", load_receptor_type="RECTANGULAR", support_point_count=4
        ),
        procedure_context=eccentricity_context(),
        observations=eccentricity_observations(),
        ruleset=eccentricity_rules(),
    )
    arguments.update(changes)
    return eccentricity_engine().evaluate(**arguments)


def repeatability_policy(**changes):
    policy = dict(
        schema_version="v1",
        evaluation_context="SYNTHETIC",
        indication_type="DIGITAL",
        range_type="SINGLE",
        error_basis="CORRECTED",
        series=[
            dict(
                series_code="MID",
                load_g="5000",
                minimum_repetitions=3,
                range_limit_basis="E",
                range_limit_multiplier="1",
                range_operator="<=",
                range_semantics="SIGNED",
            ),
            dict(
                series_code="HIGH",
                load_g="10000",
                minimum_repetitions=3,
                range_limit_basis="MPE",
                range_limit_multiplier="1",
                range_operator="<=",
                range_semantics="SIGNED",
            ),
        ],
        required_zero_reset=True,
        require_stabilization=True,
        require_environment=True,
        require_equipment=True,
        require_certificate=False,
        require_evidence=True,
        require_monotonic_timestamps=True,
    )
    policy.update(changes)
    return policy


def repeatability_rules(**changes):
    return _ruleset(
        code=REPEATABILITY,
        section=5,
        variant="DIGITAL_PRE_ROUNDING",
        policy_key=R_POLICY,
        policy_kind="repeatability_procedure_v1",
        policy=repeatability_policy(**changes),
        mpe_key=R_MPE,
        extras=(R_CLASSIFICATION, R_CALIBRATION),
    )


def repeatability_context(**changes):
    return RepeatabilityContext.model_validate(
        dict(
            evaluation_context="SYNTHETIC",
            range_no=1,
            scenario="fixture",
            stabilized=True,
            environment=[dict(measured_at="2000-01-01T00:00:00Z", temperature_c="20")],
            equipment=[dict(reference="SYNTHETIC_WEIGHT", category="SYNTHETIC")],
            evidence_hashes=["c" * 64],
        )
        | changes
    )


def repeatability_observations(*, mid_errors=("0", "5", "10"), high_errors=("0", "-5", "5")):
    registration = section5_registration()
    rows = []
    index = 1
    for series, load, errors in (("MID", 5000, mid_errors), ("HIGH", 10000, high_errors)):
        for repetition, error in enumerate(errors, 1):
            rows.append(
                dict(
                    sequence_no=index,
                    series_code=series,
                    repetition_no=repetition,
                    load_g=str(load),
                    indication_g=str(load + int(error)),
                    additional_load_g="5",
                    zero_error_g="0",
                    zero_reset_performed=True,
                    measured_at=(
                    datetime(2000, 1, 1, tzinfo=UTC) + timedelta(seconds=index)
                ).isoformat(),
                )
            )
            index += 1
    return registration.observations.parse(
        test_code=REPEATABILITY, protocol="REPEATABILITY_V1", version="v1", rows=rows
    )


def repeatability_engine():
    return R76Engine(EvaluatorRegistry((replace(section5_registration(), synthetic_fixture=True),)))


def evaluate_repeatability(**changes):
    arguments = dict(
        test_code=REPEATABILITY,
        instrument_snapshot=instrument(indication_type="DIGITAL"),
        procedure_context=repeatability_context(),
        observations=repeatability_observations(),
        ruleset=repeatability_rules(),
    )
    arguments.update(changes)
    return repeatability_engine().evaluate(**arguments)


def tare_policy(**changes):
    policy = dict(
        schema_version="v1",
        evaluation_context="SYNTHETIC",
        indication_type="DIGITAL",
        range_type="SINGLE",
        scenarios=[
            dict(
                scenario_code="T1",
                tare_type="SUBTRACTIVE",
                tare_value_g="1000",
                minimum_count=4,
                stages=["UP", "DOWN"],
                required_net_loads_g=["1000", "5000"],
            )
        ],
        enforce_gross_equals_tare_plus_net=True,
        require_declared_tare_capacity=True,
        require_stabilization=True,
        require_environment=True,
        require_equipment=True,
        require_certificate=False,
        require_evidence=True,
        require_monotonic_timestamps=True,
    )
    policy.update(changes)
    return policy


def tare_rules(**changes):
    return _ruleset(
        code=TARE,
        section=9,
        variant="DIGITAL_PRE_ROUNDING",
        policy_key=T_POLICY,
        policy_kind="tare_procedure_v1",
        policy=tare_policy(**changes),
        mpe_key=T_MPE,
        extras=(T_CLASSIFICATION, T_CALIBRATION, TARE_RULE),
    )


def tare_context(**changes):
    return TareContext.model_validate(
        dict(
            evaluation_context="SYNTHETIC",
            range_no=1,
            scenario="fixture",
            stages=["UP", "DOWN"],
            tare_scenarios=[dict(scenario_code="T1", tare_type="SUBTRACTIVE", tare_value_g="1000")],
            stabilized=True,
            environment=[dict(measured_at="2000-01-01T00:00:00Z", temperature_c="20")],
            equipment=[dict(reference="SYNTHETIC_WEIGHT", category="SYNTHETIC")],
            evidence_hashes=["d" * 64],
        )
        | changes
    )


def tare_observations(*, errors=("0", "5", "5", "0")):
    registration = section9_registration()
    points = (("UP", 1000), ("UP", 5000), ("DOWN", 5000), ("DOWN", 1000))
    rows = []
    for index, ((direction, net), error) in enumerate(zip(points, errors, strict=True), 1):
        rows.append(
            dict(
                sequence_no=index,
                tare_scenario_code="T1",
                tare_type="SUBTRACTIVE",
                tare_value_g="1000",
                net_load_g=str(net),
                gross_load_g=str(net + 1000),
                indication_g=str(net + int(error)),
                additional_load_g="5",
                zero_error_g="0",
                direction=direction,
                measured_at=(
                    datetime(2000, 1, 1, tzinfo=UTC) + timedelta(seconds=index)
                ).isoformat(),
            )
        )
    return registration.observations.parse(
        test_code=TARE, protocol="TARE_V1", version="v1", rows=rows
    )


def tare_engine():
    return R76Engine(EvaluatorRegistry((replace(section9_registration(), synthetic_fixture=True),)))


def evaluate_tare(**changes):
    arguments = dict(
        test_code=TARE,
        instrument_snapshot=instrument(
            indication_type="DIGITAL", tare_type="SUBTRACTIVE", maximum_tare_g="5000"
        ),
        procedure_context=tare_context(),
        observations=tare_observations(),
        ruleset=tare_rules(),
    )
    arguments.update(changes)
    return tare_engine().evaluate(**arguments)


__all__ = [
    "ECCENTRICITY",
    "REPEATABILITY",
    "TARE",
    "_unverify",
    "eccentricity_context",
    "eccentricity_engine",
    "eccentricity_observations",
    "eccentricity_rules",
    "evaluate_eccentricity",
    "evaluate_repeatability",
    "evaluate_tare",
    "repeatability_context",
    "repeatability_observations",
    "repeatability_rules",
    "tare_context",
    "tare_observations",
    "tare_rules",
]
