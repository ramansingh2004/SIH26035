"""SYNTHETIC TEST FIXTURES for Phase 11 endurance.

Every applicability cutoff, cycle count, load fraction, timing rule and
durability limit in this module is synthetic-only and has no OIML authority.
"""

import json
from dataclasses import replace
from datetime import UTC, datetime

from app.compliance.domain import InstrumentSnapshot, ObservationBatch
from app.compliance.engine import R76Engine
from app.compliance.evaluators import EvaluatorRegistry
from app.compliance.numbers import exact
from app.compliance.phase11 import (
    ENDURANCE,
    ENDURANCE_CALIBRATION,
    ENDURANCE_CLASSIFICATION,
    ENDURANCE_MPE,
    ENDURANCE_POLICY,
    EnduranceContext,
    EnduranceObservation,
    endurance_registration,
)
from app.compliance.ruleset import RuleSet
from domain_tests.fixtures.synthetic import SOURCE, VERIFICATION, instrument

SYNTHETIC_REQUIRED_CYCLES = 10
SYNTHETIC_CYCLING_FRACTION = "0.4"
SYNTHETIC_CAPACITY_CUTOFF_G = "20000"


def _rule(
    key,
    kind,
    policy=None,
    *,
    verified=True,
    dependencies=("BASE",),
):
    return dict(
        key=key,
        kind=kind,
        description="SYNTHETIC TEST FIXTURE ONLY",
        source=SOURCE,
        verification=VERIFICATION if verified else {},
        dependencies=list(dependencies),
        parameters=(
            []
            if policy is None
            else [
                dict(
                    name="POLICY_JSON",
                    value=json.dumps(policy),
                )
            ]
        ),
    )


def endurance_instrument(
    *,
    accuracy_class="III",
    max_capacity_g="20000",
):
    base = instrument(accuracy_class=accuracy_class)
    payload = base.model_dump(mode="python")
    payload["accuracy_class"] = accuracy_class
    payload["max_capacity_g"] = max_capacity_g
    payload["verification_intervals_n"] = exact(
        "divide",
        max_capacity_g,
        payload["verification_interval_e_g"],
    )
    payload["ranges"][0]["max_capacity_g"] = max_capacity_g
    payload["ranges"][0]["verification_intervals_n"] = payload["verification_intervals_n"]
    return InstrumentSnapshot.model_validate(payload)


def endurance_rules(*, unverified=None):
    applicability = dict(
        schema_version="v1",
        scope="EACH_RANGE",
        scenarios=[
            dict(
                procedure_variant="MECHANICAL_CYCLING",
                scenario="fixture",
            )
        ],
        cases=[
            dict(
                when=dict(
                    kind="all",
                    conditions=[
                        dict(
                            kind="choice",
                            feature="accuracy_class",
                            expected="III",
                        ),
                        dict(
                            kind="number",
                            feature="max_capacity_g",
                            scope="RANGE",
                            operator="<=",
                            value=SYNTHETIC_CAPACITY_CUTOFF_G,
                        ),
                    ],
                ),
                decision="REQUIRED",
                reason="SYNTHETIC class/capacity required branch",
            ),
            dict(
                when={"kind": "always"},
                decision="NOT_APPLICABLE",
                reason="SYNTHETIC class/capacity exclusion branch",
            ),
        ],
    )
    mpe = dict(
        schema_version="v1",
        accuracy_class="III",
        evaluation_context="SYNTHETIC",
        operator="<=",
        semantics="ABSOLUTE",
        bands=[
            dict(
                lower_e="0",
                upper_e="3000",
                lower_operator=">=",
                upper_operator="<=",
                multiplier_e="1",
            )
        ],
    )
    procedure = dict(
        schema_version="v1",
        evaluation_context="SYNTHETIC",
        required_cycles=SYNTHETIC_REQUIRED_CYCLES,
        completed_cycles_operator=">=",
        cycling_load_fraction_of_max=SYNTHETIC_CYCLING_FRACTION,
        cycling_load_tolerance_g="5",
        cycling_load_operator="<=",
        require_cycle_timestamps=True,
        minimum_cycle_duration_s="60",
        cycle_duration_operator=">=",
        required_load_points=[
            dict(
                point_id="P25",
                load_fraction_of_max="0.25",
                load_tolerance_g="20",
            ),
            dict(
                point_id="PMAX",
                load_fraction_of_max="1",
                load_tolerance_g="20",
            ),
        ],
        require_same_reference_weights=True,
        require_environment=True,
        require_equipment=True,
        require_certificate=True,
        require_evidence=True,
        require_monotonic_timestamps=True,
        require_abnormal_events_resolved=True,
        durability_formula="ABS_CORRECTED_ERROR_CHANGE",
        durability_mpe_multiplier="1",
        durability_operator="<=",
        durability_semantics="ABSOLUTE",
    )

    definitions = [
        _rule("BASE", "dependency_v1", dependencies=()),
        _rule(
            "SECTION15_APP",
            "applicability_policy_v1",
            applicability,
            verified=unverified != "SECTION15_APP",
        ),
        _rule(
            ENDURANCE_MPE,
            "mpe_profile_v1",
            mpe,
            verified=unverified != ENDURANCE_MPE,
        ),
        _rule(
            ENDURANCE_POLICY,
            "endurance_procedure_v1",
            procedure,
            verified=unverified != ENDURANCE_POLICY,
        ),
        _rule(
            ENDURANCE_CLASSIFICATION,
            "dependency_v1",
            verified=unverified != ENDURANCE_CLASSIFICATION,
        ),
        _rule(
            ENDURANCE_CALIBRATION,
            "dependency_v1",
            verified=unverified != ENDURANCE_CALIBRATION,
        ),
    ]

    return RuleSet.model_validate(
        dict(
            metadata=dict(
                schema_version=1,
                standard_code="OIML_R76",
                standard_name="SYNTHETIC",
                edition="TEST-PHASE11-v1",
                version="SYNTHETIC_TEST_PHASE11_ENDURANCE",
                standard_parts=[SOURCE],
                supported_test_codes=[ENDURANCE],
                source_reference="SYNTHETIC TEST FIXTURE ONLY",
            ),
            rules=definitions,
            tests=[
                dict(
                    code=ENDURANCE,
                    section=15,
                    name="SYNTHETIC ENDURANCE TEST FIXTURE",
                    source=SOURCE,
                    dependencies=[
                        "SECTION15_APP",
                        ENDURANCE_MPE,
                        ENDURANCE_POLICY,
                        ENDURANCE_CLASSIFICATION,
                        ENDURANCE_CALIBRATION,
                    ],
                    implemented=True,
                    verification=VERIFICATION,
                )
            ],
            checklist=[],
        )
    )


def endurance_context(**changes):
    payload = dict(
        evaluation_context="SYNTHETIC",
        range_no=1,
        scenario="fixture",
        cycling_target_load_g="8000",
        planned_cycles=SYNTHETIC_REQUIRED_CYCLES,
        completed_cycles=SYNTHETIC_REQUIRED_CYCLES,
        cycle_started_at="2000-01-02T00:00:00Z",
        cycle_ended_at="2000-01-02T00:10:00Z",
        same_reference_weights_confirmed=True,
        abnormal_events=(),
        abnormal_events_resolved=True,
        environment=[
            dict(
                measured_at="2000-01-01T00:00:00Z",
                temperature_c="20",
                relative_humidity_percent="50",
                pressure_hpa="1000",
                phase="SYNTHETIC_PHASE11",
            )
        ],
        equipment=[
            dict(
                reference="SYNTHETIC_ENDURANCE_MACHINE",
                category="SYNTHETIC",
                calibration_certificate_no="SYNTHETIC-CERT",
                certificate_content_hash="c" * 64,
            ),
            dict(
                reference="SYNTHETIC_REFERENCE_WEIGHTS",
                category="SYNTHETIC",
                calibration_certificate_no="SYNTHETIC-WEIGHT-CERT",
                certificate_content_hash="d" * 64,
            ),
        ],
        evidence_hashes=["e" * 64],
    )
    payload.update(changes)
    return EnduranceContext.model_validate(payload)


def endurance_observations(
    *,
    final_errors=("10", "10"),
    initial_errors=("0", "0"),
    omit_final=False,
    reverse_final=False,
    mismatched_pair=False,
    final_before_cycle_end=False,
):
    points = (
        ("P25", "5000"),
        ("PMAX", "20000"),
    )
    rows = []
    sequence = 1

    for (point, load), error in zip(points, initial_errors, strict=True):
        rows.append(
            EnduranceObservation(
                sequence_no=sequence,
                phase="INITIAL",
                point_id=point,
                load_g=load,
                indication_g=exact("add", load, error),
                additional_load_g="5",
                zero_error_g="0",
                measured_at=datetime(
                    2000,
                    1,
                    1,
                    0,
                    sequence,
                    tzinfo=UTC,
                ),
            )
        )
        sequence += 1

    final_rows = []
    final_time_day = 2 if final_before_cycle_end else 3
    for (point, load), error in zip(points, final_errors, strict=True):
        final_load = load
        if mismatched_pair and point == "PMAX":
            final_load = "19990"
        final_rows.append(
            EnduranceObservation(
                sequence_no=sequence,
                phase="FINAL",
                point_id=point,
                load_g=final_load,
                indication_g=exact("add", final_load, error),
                additional_load_g="5",
                zero_error_g="0",
                measured_at=datetime(
                    2000,
                    1,
                    final_time_day,
                    0,
                    sequence,
                    tzinfo=UTC,
                ),
            )
        )
        sequence += 1

    if reverse_final:
        final_rows = list(reversed(final_rows))
        final_rows = [
            EnduranceObservation.model_validate(
                row.model_dump(mode="python") | {"sequence_no": index}
            )
            for index, row in enumerate(final_rows, start=3)
        ]

    rows.extend(final_rows)
    if omit_final:
        rows = rows[:-1]

    return ObservationBatch(
        test_code=ENDURANCE,
        protocol="ENDURANCE_V1",
        observation_schema_version="v1",
        rows=tuple(rows),
    )


def endurance_engine():
    return R76Engine(
        EvaluatorRegistry(
            (
                replace(
                    endurance_registration(),
                    synthetic_fixture=True,
                ),
            )
        )
    )


def evaluate_endurance(**changes):
    arguments = dict(
        test_code=ENDURANCE,
        instrument_snapshot=endurance_instrument(),
        procedure_context=endurance_context(),
        observations=endurance_observations(),
        ruleset=endurance_rules(),
    )
    arguments.update(changes)
    return endurance_engine().evaluate(**arguments)
