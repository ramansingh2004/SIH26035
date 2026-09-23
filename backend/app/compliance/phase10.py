"""Phase 10 electrical-disturbance mechanics.

REG-13 and REG-16 remain regulatory gates. This module provides typed
procedure/observation contracts and deterministic shared disturbance mechanics
for the seven Section 12 evaluator families. It does not embed candidate OIML,
IEC or ISO severity values, repetition counts, ports, polarities, timings or
accepted significant-fault responses.

Physical waveform/configuration evidence is recorded by reference/evidence
hash. The compliance engine does not synthesize a laboratory waveform.
"""

from dataclasses import dataclass
from typing import Literal

from pydantic import Field, StrictBool, model_validator

from app.compliance.applicability import ApplicabilityEngine, ApplicabilityPolicy
from app.compliance.domain import (
    AcceptanceLimit,
    CalculationTraceEntry,
    ComplianceOutcome,
    Digest,
    EvaluationOutput,
    FailedCondition,
    Frozen,
    Number,
    Observation,
    PositiveInt,
    ProcedureValidationIssue,
    RangeProcedureContext,
    Text,
    ordered_unique,
)
from app.compliance.evaluators import EvaluatorRegistration, RulePolicyRegistration
from app.compliance.numbers import compare, exact
from app.compliance.registries import (
    ContextRegistration,
    ObservationRegistration,
    ObservationSchemaRegistry,
    ProcedureContextRegistry,
)
from app.compliance.regulatory import dependencies, rule_policy
from app.compliance.weighing import (
    MeasurementTime,
    WeighingEnvironment,
    WeighingEquipment,
)

DISTURBANCE_VOLTAGE_DIP = "DISTURBANCE_VOLTAGE_DIP"
DISTURBANCE_BURST = "DISTURBANCE_BURST"
DISTURBANCE_SURGE = "DISTURBANCE_SURGE"
DISTURBANCE_ESD = "DISTURBANCE_ESD"
DISTURBANCE_RADIATED_RF = "DISTURBANCE_RADIATED_RF"
DISTURBANCE_CONDUCTED_RF = "DISTURBANCE_CONDUCTED_RF"
DISTURBANCE_VEHICLE_SUPPLY = "DISTURBANCE_VEHICLE_SUPPLY"

DISTURBANCE_CODES = (
    DISTURBANCE_VOLTAGE_DIP,
    DISTURBANCE_BURST,
    DISTURBANCE_SURGE,
    DISTURBANCE_ESD,
    DISTURBANCE_RADIATED_RF,
    DISTURBANCE_CONDUCTED_RF,
    DISTURBANCE_VEHICLE_SUPPLY,
)

DISTURBANCE_POLICY_KEYS = {
    DISTURBANCE_VOLTAGE_DIP: "SECTION12_VOLTAGE_DIP_PROCEDURE",
    DISTURBANCE_BURST: "SECTION12_BURST_PROCEDURE",
    DISTURBANCE_SURGE: "SECTION12_SURGE_PROCEDURE",
    DISTURBANCE_ESD: "SECTION12_ESD_PROCEDURE",
    DISTURBANCE_RADIATED_RF: "SECTION12_RADIATED_RF_PROCEDURE",
    DISTURBANCE_CONDUCTED_RF: "SECTION12_CONDUCTED_RF_PROCEDURE",
    DISTURBANCE_VEHICLE_SUPPLY: "SECTION12_VEHICLE_SUPPLY_PROCEDURE",
}
DISTURBANCE_CLASSIFICATION = "SECTION12_DISTURBANCE_CLASSIFICATION"
DISTURBANCE_CALIBRATION = "SECTION12_CALIBRATION"


def _issue(refs, category, reason, *, sequence=None, missing=False):
    return ProcedureValidationIssue(
        code=("MISSING_REQUIRED_OBSERVATIONS" if missing else "EVALUATION_NOT_POSSIBLE"),
        category=category,
        reason=reason,
        sequence_no=sequence,
        rule_references=refs,
    )


class DisturbanceSeverity(Frozen):
    """Typed generic severity/configuration record."""

    severity_id: Text
    case: str | None = None
    line_type: str | None = None
    port: str | None = None
    polarity: str | None = None
    coupling_mode: str | None = None
    application_type: str | None = None
    discharge_mode: str | None = None
    location: str | None = None
    pulse: str | None = None
    reduction_percent: Number | None = Field(None, ge=0, le=100)
    cycles: Number | None = Field(None, ge=0)
    amplitude_v: Number | None = None
    duration_s: Number | None = Field(None, ge=0)
    phase_angle_deg: Number | None = None
    frequency_hz: Number | None = Field(None, gt=0)
    field_strength_v_per_m: Number | None = Field(None, ge=0)
    modulation_percent: Number | None = Field(None, ge=0, le=100)
    modulation_frequency_hz: Number | None = Field(None, gt=0)
    voltage_kv: Number | None = None
    battery_voltage_v: Number | None = Field(None, ge=0)
    conducted_voltage_v: Number | None = None
    waveform_reference: str | None = None
    standard_profile_reference: str | None = None


class DisturbanceProfile(Frozen):
    procedure_variant: Text
    evaluation_context: Text
    required_severities: tuple[DisturbanceSeverity, ...] = Field(min_length=1)
    repetitions_per_severity: PositiveInt
    deviation_limit_multiplier_e: Number = Field(ge=0)
    deviation_operator: Literal["<", "<=", ">", ">=", "==", "!="]
    deviation_semantics: Literal["SIGNED", "ABSOLUTE"]
    accepted_fault_responses: tuple[Text, ...] = ()
    require_warm_up: StrictBool
    require_environment_stabilized: StrictBool
    require_peripherals_connected: StrictBool
    require_no_load_deviation: StrictBool
    require_environment: StrictBool
    require_equipment: StrictBool
    require_certificate: StrictBool
    require_evidence: StrictBool
    require_waveform_reference: StrictBool
    require_fault_response_evidence: StrictBool
    require_state_trace: StrictBool
    require_monotonic_timestamps: StrictBool

    @model_validator(mode="after")
    def unique_severities_and_responses(self):
        if len({item.severity_id for item in self.required_severities}) != len(
            self.required_severities
        ):
            raise ValueError("Duplicate disturbance severity identifier")
        object.__setattr__(
            self,
            "accepted_fault_responses",
            tuple(sorted(set(self.accepted_fault_responses))),
        )
        return self


class DisturbancePolicy(Frozen):
    schema_version: Literal["v1"]
    test_code: Literal[
        "DISTURBANCE_VOLTAGE_DIP",
        "DISTURBANCE_BURST",
        "DISTURBANCE_SURGE",
        "DISTURBANCE_ESD",
        "DISTURBANCE_RADIATED_RF",
        "DISTURBANCE_CONDUCTED_RF",
        "DISTURBANCE_VEHICLE_SUPPLY",
    ]
    profiles: tuple[DisturbanceProfile, ...] = Field(min_length=1)

    @model_validator(mode="after")
    def unique_profiles(self):
        if len({item.procedure_variant for item in self.profiles}) != len(self.profiles):
            raise ValueError("Duplicate disturbance procedure variant")
        return self

    def select(self, variant: str) -> DisturbanceProfile | None:
        return next(
            (item for item in self.profiles if item.procedure_variant == variant),
            None,
        )


class _DisturbanceContextBase(RangeProcedureContext):
    procedure_schema_version: Literal["v1"] = "v1"
    protocol: Literal["DISTURBANCE_V1"] = "DISTURBANCE_V1"
    test_load_g: Number = Field(ge=0)
    warm_up_completed: StrictBool
    environment_stabilized: StrictBool
    peripherals_connected: StrictBool
    no_load_deviation_g: Number | None = None
    severity_cases: tuple[DisturbanceSeverity, ...] = Field(min_length=1)
    environment: tuple[WeighingEnvironment, ...] = ()
    equipment: tuple[WeighingEquipment, ...] = ()
    evidence_hashes: tuple[Digest, ...] = ()

    @model_validator(mode="after")
    def canonical_evidence_and_severities(self):
        if len({item.severity_id for item in self.severity_cases}) != len(self.severity_cases):
            raise ValueError("Duplicate disturbance severity identifier")
        object.__setattr__(
            self,
            "equipment",
            ordered_unique(self.equipment, lambda item: item.reference),
        )
        object.__setattr__(
            self,
            "evidence_hashes",
            tuple(sorted(set(self.evidence_hashes))),
        )
        return self


class VoltageDipContext(_DisturbanceContextBase):
    test_code: Literal["DISTURBANCE_VOLTAGE_DIP"] = DISTURBANCE_VOLTAGE_DIP
    procedure_variant: Literal["AC_MAINS_DIPS_INTERRUPTION"] = "AC_MAINS_DIPS_INTERRUPTION"


class BurstContext(_DisturbanceContextBase):
    test_code: Literal["DISTURBANCE_BURST"] = DISTURBANCE_BURST
    procedure_variant: Literal["BURST_LINES"] = "BURST_LINES"


class SurgeContext(_DisturbanceContextBase):
    test_code: Literal["DISTURBANCE_SURGE"] = DISTURBANCE_SURGE
    procedure_variant: Literal["SURGE_LINES"] = "SURGE_LINES"


class EsdContext(_DisturbanceContextBase):
    test_code: Literal["DISTURBANCE_ESD"] = DISTURBANCE_ESD
    procedure_variant: Literal["ESD"] = "ESD"


class RadiatedRfContext(_DisturbanceContextBase):
    test_code: Literal["DISTURBANCE_RADIATED_RF"] = DISTURBANCE_RADIATED_RF
    procedure_variant: Literal["RADIATED_RF"] = "RADIATED_RF"


class ConductedRfContext(_DisturbanceContextBase):
    test_code: Literal["DISTURBANCE_CONDUCTED_RF"] = DISTURBANCE_CONDUCTED_RF
    procedure_variant: Literal["CONDUCTED_RF"] = "CONDUCTED_RF"


class VehicleSupplyContext(_DisturbanceContextBase):
    test_code: Literal["DISTURBANCE_VEHICLE_SUPPLY"] = DISTURBANCE_VEHICLE_SUPPLY
    procedure_variant: Literal[
        "SUPPLY_LINE_CONDUCTION",
        "NON_SUPPLY_LINE_COUPLING",
    ]


class _DisturbanceObservationBase(Observation):
    protocol: Literal["DISTURBANCE_V1"] = "DISTURBANCE_V1"
    observation_schema_version: Literal["v1"] = "v1"
    severity_id: Text
    repetition_no: PositiveInt
    reference_indication_g: Number
    disturbed_indication_g: Number
    fault_detected: StrictBool
    fault_response: str | None = None
    fault_response_evidence_hash: Digest | None = None
    state_before: str | None = None
    state_during: str | None = None
    state_after: str | None = None
    measured_at: MeasurementTime

    @model_validator(mode="after")
    def fault_fields(self):
        if not self.fault_detected and (
            self.fault_response is not None or self.fault_response_evidence_hash is not None
        ):
            raise ValueError("Fault response data requires fault_detected=true")
        return self


class VoltageDipObservation(_DisturbanceObservationBase):
    test_code: Literal["DISTURBANCE_VOLTAGE_DIP"] = DISTURBANCE_VOLTAGE_DIP


class BurstObservation(_DisturbanceObservationBase):
    test_code: Literal["DISTURBANCE_BURST"] = DISTURBANCE_BURST


class SurgeObservation(_DisturbanceObservationBase):
    test_code: Literal["DISTURBANCE_SURGE"] = DISTURBANCE_SURGE


class EsdObservation(_DisturbanceObservationBase):
    test_code: Literal["DISTURBANCE_ESD"] = DISTURBANCE_ESD


class RadiatedRfObservation(_DisturbanceObservationBase):
    test_code: Literal["DISTURBANCE_RADIATED_RF"] = DISTURBANCE_RADIATED_RF


class ConductedRfObservation(_DisturbanceObservationBase):
    test_code: Literal["DISTURBANCE_CONDUCTED_RF"] = DISTURBANCE_CONDUCTED_RF


class VehicleSupplyObservation(_DisturbanceObservationBase):
    test_code: Literal["DISTURBANCE_VEHICLE_SUPPLY"] = DISTURBANCE_VEHICLE_SUPPLY


CONTEXT_SCHEMAS = {
    DISTURBANCE_VOLTAGE_DIP: (("AC_MAINS_DIPS_INTERRUPTION", VoltageDipContext),),
    DISTURBANCE_BURST: (("BURST_LINES", BurstContext),),
    DISTURBANCE_SURGE: (("SURGE_LINES", SurgeContext),),
    DISTURBANCE_ESD: (("ESD", EsdContext),),
    DISTURBANCE_RADIATED_RF: (("RADIATED_RF", RadiatedRfContext),),
    DISTURBANCE_CONDUCTED_RF: (("CONDUCTED_RF", ConductedRfContext),),
    DISTURBANCE_VEHICLE_SUPPLY: (
        ("SUPPLY_LINE_CONDUCTION", VehicleSupplyContext),
        ("NON_SUPPLY_LINE_COUPLING", VehicleSupplyContext),
    ),
}

OBSERVATION_SCHEMAS = {
    DISTURBANCE_VOLTAGE_DIP: VoltageDipObservation,
    DISTURBANCE_BURST: BurstObservation,
    DISTURBANCE_SURGE: SurgeObservation,
    DISTURBANCE_ESD: EsdObservation,
    DISTURBANCE_RADIATED_RF: RadiatedRfObservation,
    DISTURBANCE_CONDUCTED_RF: ConductedRfObservation,
    DISTURBANCE_VEHICLE_SUPPLY: VehicleSupplyObservation,
}


def _common_issues(profile, context, refs):
    issues = []

    def check(condition, category, reason, *, missing=False):
        if not condition:
            issues.append(
                _issue(
                    refs,
                    category,
                    reason,
                    missing=missing,
                )
            )

    check(
        context.evaluation_context == profile.evaluation_context,
        "STAGE",
        "Evaluation context incompatible with verified disturbance profile",
    )
    check(
        not profile.require_warm_up or context.warm_up_completed,
        "STABILIZATION",
        "Verified disturbance procedure requires completed warm-up",
    )
    check(
        not profile.require_environment_stabilized or context.environment_stabilized,
        "STABILIZATION",
        "Verified disturbance procedure requires stable environment",
    )
    check(
        not profile.require_peripherals_connected or context.peripherals_connected,
        "EQUIPMENT",
        "Verified disturbance procedure requires applicable peripherals/interfaces",
    )
    check(
        not profile.require_no_load_deviation or context.no_load_deviation_g is not None,
        "LOAD_COVERAGE",
        "Verified disturbance procedure requires no-load deviation",
        missing=True,
    )
    check(
        not profile.require_environment or bool(context.environment),
        "ENVIRONMENT",
        "Required environment evidence missing",
        missing=True,
    )
    check(
        not profile.require_equipment or bool(context.equipment),
        "EQUIPMENT",
        "Required disturbance equipment missing",
        missing=True,
    )
    if profile.require_certificate:
        check(
            bool(context.equipment)
            and all(
                item.calibration_certificate_no and item.certificate_content_hash
                for item in context.equipment
            ),
            "EQUIPMENT",
            "Required calibration certificate evidence missing",
            missing=True,
        )
    check(
        not profile.require_evidence or bool(context.evidence_hashes),
        "EVIDENCE",
        "Required supporting disturbance evidence missing",
        missing=True,
    )
    return issues


@dataclass(frozen=True)
class DisturbanceEvaluator:
    test_code: str
    policy_key: str

    def required_rules(self, **kwargs):
        return (
            self.policy_key,
            DISTURBANCE_CLASSIFICATION,
            DISTURBANCE_CALIBRATION,
        )

    def applicability(
        self,
        *,
        instrument_snapshot,
        procedure_context,
        ruleset,
    ):
        return ApplicabilityEngine().determine(
            test_code=self.test_code,
            instrument_snapshot=instrument_snapshot,
            ruleset=ruleset,
            range_no=procedure_context.range_no,
            scenario=procedure_context.scenario,
            procedure_variant=procedure_context.procedure_variant,
        )

    def validate_procedure(
        self,
        *,
        instrument_snapshot,
        procedure_context,
        observations,
        ruleset,
    ):
        policy = rule_policy(
            ruleset,
            self.policy_key,
            "disturbance_procedure_v1",
            DisturbancePolicy,
        )
        refs = dependencies(
            ruleset,
            self.required_rules(),
        ).rule_references
        issues = []
        if policy.test_code != self.test_code:
            return (
                _issue(
                    refs,
                    "STAGE",
                    "Disturbance policy belongs to another test code",
                ),
            )
        profile = policy.select(procedure_context.procedure_variant)
        if profile is None:
            return (
                _issue(
                    refs,
                    "STAGE",
                    "Procedure variant missing from verified disturbance policy",
                ),
            )

        issues.extend(_common_issues(profile, procedure_context, refs))
        selected = instrument_snapshot.select_range(procedure_context.range_no)

        def check(
            condition,
            category,
            reason,
            *,
            sequence=None,
            missing=False,
        ):
            if not condition:
                issues.append(
                    _issue(
                        refs,
                        category,
                        reason,
                        sequence=sequence,
                        missing=missing,
                    )
                )

        check(
            procedure_context.test_load_g <= selected.max_capacity_g,
            "RANGE",
            "Disturbance test load exceeds selected range",
        )
        check(
            procedure_context.severity_cases == profile.required_severities,
            "SEVERITY",
            "Configured disturbance severities differ from verified profile",
            missing=(len(procedure_context.severity_cases) < len(profile.required_severities)),
        )
        if profile.require_waveform_reference:
            check(
                all(item.waveform_reference for item in procedure_context.severity_cases),
                "EVIDENCE",
                "Verified disturbance severity requires waveform/configuration reference",
                missing=True,
            )

        expected = tuple(
            (severity.severity_id, repetition)
            for severity in profile.required_severities
            for repetition in range(1, profile.repetitions_per_severity + 1)
        )
        actual = tuple((row.severity_id, row.repetition_no) for row in observations.rows)
        check(
            len(actual) == len(expected),
            "COUNT",
            "Required disturbance repetitions are incomplete",
            missing=len(actual) < len(expected),
        )
        check(
            actual == expected,
            "ORDER",
            "Disturbance severity/repetition sequence is incomplete or out of order",
            missing=len(actual) < len(expected),
        )

        known = {item.severity_id for item in profile.required_severities}
        previous = None
        for row in observations.rows:
            check(
                row.severity_id in known,
                "SEVERITY",
                "Observation references an unexpected disturbance severity",
                sequence=row.sequence_no,
            )
            if row.fault_detected:
                check(
                    bool(row.fault_response),
                    "FUNCTIONAL",
                    "Detected fault is missing recorded response",
                    sequence=row.sequence_no,
                    missing=True,
                )
                if profile.require_fault_response_evidence:
                    check(
                        row.fault_response_evidence_hash is not None,
                        "EVIDENCE",
                        "Detected fault is missing response evidence",
                        sequence=row.sequence_no,
                        missing=True,
                    )
            if profile.require_state_trace:
                check(
                    bool(row.state_before) and bool(row.state_during) and bool(row.state_after),
                    "EVIDENCE",
                    "Required before/during/after disturbance state trace is incomplete",
                    sequence=row.sequence_no,
                    missing=True,
                )
            if profile.require_monotonic_timestamps and previous is not None:
                check(
                    row.measured_at >= previous,
                    "TIMING",
                    "Disturbance observation timestamp order invalid",
                    sequence=row.sequence_no,
                )
            previous = row.measured_at
        return tuple(issues)

    def evaluate(
        self,
        *,
        instrument_snapshot,
        procedure_context,
        observations,
        ruleset,
    ):
        policy = rule_policy(
            ruleset,
            self.policy_key,
            "disturbance_procedure_v1",
            DisturbancePolicy,
        )
        profile = policy.select(procedure_context.procedure_variant)
        if profile is None:
            raise ValueError("Verified disturbance profile unavailable")
        refs = dependencies(
            ruleset,
            self.required_rules(),
        ).rule_references
        selected = instrument_snapshot.select_range(procedure_context.range_no)
        limit = AcceptanceLimit(
            name="disturbance_indication_deviation",
            value=exact(
                "multiply",
                selected.verification_interval_e_g,
                profile.deviation_limit_multiplier_e,
            ),
            unit="g",
            operator=profile.deviation_operator,
            semantics=profile.deviation_semantics,
            rule_references=refs,
        )

        calculations = []
        limits = []
        failures = []
        accepted_responses = set(profile.accepted_fault_responses)

        for row in observations.rows:
            deviation = exact(
                "subtract",
                row.disturbed_indication_g,
                row.reference_indication_g,
            )
            calculations.append(
                CalculationTraceEntry(
                    name=(f"{row.sequence_no}:{row.severity_id}:indication_deviation"),
                    expression=("disturbed_indication - reference_indication"),
                    value=deviation,
                    unit="g",
                    rule_references=refs,
                )
            )
            limits.append(limit)

            within_limit = compare(
                deviation,
                limit.value,
                operator=limit.operator,
                semantics=limit.semantics,
            )
            handled_fault = bool(
                row.fault_detected
                and row.fault_response
                and row.fault_response in accepted_responses
            )
            if not within_limit and not handled_fault:
                failures.append(
                    FailedCondition(
                        code="DISTURBANCE_EFFECT_NOT_ACCEPTABLY_HANDLED",
                        reason=(
                            f"Observation {row.sequence_no} exceeds the "
                            "verified deviation limit without an accepted "
                            "significant-fault response"
                        ),
                        actual=deviation,
                        limit=limit,
                    )
                )

        return EvaluationOutput(
            compliance_outcome=(
                ComplianceOutcome.NONCOMPLIANT if failures else ComplianceOutcome.COMPLIANT
            ),
            calculations=tuple(calculations),
            acceptance_limits=tuple(limits),
            failed_conditions=tuple(failures),
            reasons=(
                "Complete disturbance procedure evaluated using pinned "
                "verified severity and fault-response dependencies",
            ),
        )


def _registration(code):
    contexts = tuple(
        ContextRegistration(
            code,
            variant,
            "v1",
            schema,
        )
        for variant, schema in CONTEXT_SCHEMAS[code]
    )
    return EvaluatorRegistration(
        code,
        DisturbanceEvaluator(
            test_code=code,
            policy_key=DISTURBANCE_POLICY_KEYS[code],
        ),
        ProcedureContextRegistry(contexts),
        ObservationSchemaRegistry(
            (
                ObservationRegistration(
                    code,
                    "DISTURBANCE_V1",
                    "v1",
                    OBSERVATION_SCHEMAS[code],
                ),
            )
        ),
        implementation_version="section12-v1",
        policy_schemas=(
            RulePolicyRegistration(
                "applicability_policy_v1",
                ApplicabilityPolicy,
            ),
            RulePolicyRegistration(
                "disturbance_procedure_v1",
                DisturbancePolicy,
            ),
        ),
    )


def voltage_dip_registration():
    return _registration(DISTURBANCE_VOLTAGE_DIP)


def burst_registration():
    return _registration(DISTURBANCE_BURST)


def surge_registration():
    return _registration(DISTURBANCE_SURGE)


def esd_registration():
    return _registration(DISTURBANCE_ESD)


def radiated_rf_registration():
    return _registration(DISTURBANCE_RADIATED_RF)


def conducted_rf_registration():
    return _registration(DISTURBANCE_CONDUCTED_RF)


def vehicle_supply_registration():
    return _registration(DISTURBANCE_VEHICLE_SUPPLY)


def disturbance_registrations():
    return (
        voltage_dip_registration(),
        burst_registration(),
        surge_registration(),
        esd_registration(),
        radiated_rf_registration(),
        conducted_rf_registration(),
        vehicle_supply_registration(),
    )
