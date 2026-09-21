"""Immutable semantic values. No storage identities, ambient state or framework objects."""

from datetime import date
from enum import StrEnum
from typing import Annotated, Literal
from unicodedata import normalize

from pydantic import (
    AwareDatetime,
    BaseModel,
    ConfigDict,
    Field,
    SerializeAsAny,
    StrictBool,
    field_validator,
    model_validator,
)

from app.compliance.numbers import Number, Operator, Semantics, exact

Text = Annotated[str, Field(min_length=1)]
PositiveInt = Annotated[int, Field(gt=0, strict=True)]
Digest = Annotated[str, Field(pattern=r"^[a-f0-9]{64}$")]
Unit = Literal["g", "V", "degC", "%", "hPa", "s", "1"]


class Frozen(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, validate_default=True)

    @field_validator("*", mode="after")
    @classmethod
    def text_normalization(cls, value, info):
        if isinstance(value, str) and not isinstance(value, StrEnum):
            return normalize("NFC", value)
        if isinstance(value, tuple) and all(isinstance(v, str) for v in value):
            normalized = tuple(normalize("NFC", v) for v in value)
            if info.field_name == "unresolved_rule_ids":
                return tuple(sorted(set(normalized)))
            return normalized
        if info.field_name == "rule_references":
            return ordered_unique(value, lambda r: r.rule_id)
        return value


class WorkflowStatus(StrEnum):
    DRAFT = "DRAFT"
    INSTRUMENT_CONFIGURATION = "INSTRUMENT_CONFIGURATION"
    APPLICABILITY_CONFIRMED = "APPLICABILITY_CONFIRMED"
    TESTING = "TESTING"
    EXAMINATION = "EXAMINATION"
    UNDER_REVIEW = "UNDER_REVIEW"
    APPROVED = "APPROVED"
    REPORT_ISSUED = "REPORT_ISSUED"
    REJECTED = "REJECTED"
    CANCELLED = "CANCELLED"


class EvaluationStatus(StrEnum):
    NOT_STARTED = "NOT_STARTED"
    IN_PROGRESS = "IN_PROGRESS"
    INCOMPLETE = "INCOMPLETE"
    STALE = "STALE"
    REVIEW_REQUIRED = "REVIEW_REQUIRED"
    COMPLETE = "COMPLETE"


class ComplianceOutcome(StrEnum):
    UNDETERMINED = "UNDETERMINED"
    COMPLIANT = "COMPLIANT"
    NONCOMPLIANT = "NONCOMPLIANT"
    NOT_APPLICABLE = "NOT_APPLICABLE"


class Applicability(StrEnum):
    REQUIRED = "REQUIRED"
    OPTIONAL = "OPTIONAL"
    NOT_APPLICABLE = "NOT_APPLICABLE"
    REQUIRES_REVIEW = "REQUIRES_REVIEW"


def ordered_unique(values, key):
    keys = [key(v) for v in values]
    keys = [normalize("NFC", k) if isinstance(k, str) else k for k in keys]
    if len(keys) != len(set(keys)):
        raise ValueError("Duplicate semantic identifier")
    return tuple(v for _, v in sorted(zip(keys, values, strict=True), key=lambda p: p[0]))


class Capacity(Frozen):
    min_capacity_g: Number | None = Field(None, ge=0)
    max_capacity_g: Number = Field(gt=0)
    verification_interval_e_g: Number = Field(gt=0)
    scale_interval_d_g: Number = Field(gt=0)
    verification_intervals_n: Number | None = Field(None, gt=0)

    @model_validator(mode="after")
    def capacities(self):
        if self.min_capacity_g is not None and self.min_capacity_g >= self.max_capacity_g:
            raise ValueError("Min must be smaller than Max")
        if (
            self.verification_intervals_n is not None
            and exact("multiply", self.verification_intervals_n, self.verification_interval_e_g)
            != self.max_capacity_g
        ):
            raise ValueError("n * e must equal Max exactly")
        return self


class InstrumentRangeSnapshot(Capacity):
    range_no: PositiveInt


class InterfaceSnapshot(Frozen):
    name: Text
    interface_type: str | None = None
    purpose: str | None = None
    externally_accessible: StrictBool | None = None


class ComponentSnapshot(Frozen):
    # Semantic component designation, not a database UUID.
    designation: Text
    component_type: Text
    manufacturer_name: str | None = None
    model: str | None = None
    serial_or_type: str | None = None
    certificate_reference: str | None = None
    description: str | None = None
    rated_capacity_g: Number | None = Field(None, gt=0)
    nominal_voltage: Number | None = Field(None, gt=0)
    interface_type: str | None = None
    software_identifier: str | None = None
    notes: str | None = None


class GeometrySnapshot(Frozen):
    shape: Text
    length_mm: Number | None = Field(None, gt=0)
    width_mm: Number | None = Field(None, gt=0)
    diameter_mm: Number | None = Field(None, gt=0)


class InstrumentSnapshot(Capacity):
    accuracy_class: Literal["I", "II", "III", "IIII"]
    ranges: tuple[InstrumentRangeSnapshot, ...] = Field(min_length=1)
    range_type: str | None = None
    indication_type: str | None = None
    is_self_indicating: StrictBool | None = None
    is_electronic: StrictBool | None = None
    is_software_controlled: StrictBool | None = None
    is_portable: StrictBool | None = None
    is_mobile: StrictBool | None = None
    load_receptor_type: str | None = None
    support_point_count: PositiveInt | None = None
    geometry: GeometrySnapshot | None = None
    tare_type: str | None = None
    maximum_tare_g: Number | None = Field(None, ge=0)
    zero_setting_type: str | None = None
    zero_tracking_available: StrictBool | None = None
    level_indicator_available: StrictBool | None = None
    automatic_tilt_sensor: StrictBool | None = None
    power_supply_type: str | None = None
    nominal_voltage: Number | None = Field(None, gt=0)
    min_voltage: Number | None = Field(None, gt=0)
    max_voltage: Number | None = Field(None, gt=0)
    declared_temp_min_c: Number | None = None
    declared_temp_max_c: Number | None = None
    software_identifier: str | None = None
    is_direct_sales: StrictBool | None = None
    is_price_computing: StrictBool | None = None
    is_labeling: StrictBool | None = None
    data_storage_device_present: StrictBool | None = None
    interfaces: tuple[InterfaceSnapshot, ...] | None = None
    peripherals: tuple[Text, ...] | None = None
    components: tuple[ComponentSnapshot, ...] | None = None
    battery_charging_during_operation: StrictBool | None = None
    vehicle_powered: StrictBool | None = None
    vehicle_power_details: str | None = None
    declared_operating_conditions: str | None = None
    declared_installation: str | None = None

    @model_validator(mode="after")
    def structure(self):
        object.__setattr__(self, "ranges", ordered_unique(self.ranges, lambda r: r.range_no))
        if max(r.max_capacity_g for r in self.ranges) != self.max_capacity_g:
            raise ValueError("Explicit ranges must represent the declared Max")
        if len(self.ranges) == 1:
            for field in Capacity.model_fields:
                left, right = getattr(self, field), getattr(self.ranges[0], field)
                if left is not None and right is not None and left != right:
                    raise ValueError("Single range and instrument capacities disagree")
        for field, key in (
            ("interfaces", lambda v: v.name),
            ("peripherals", lambda v: v),
            ("components", lambda v: v.designation),
        ):
            values = getattr(self, field)
            if values is not None:
                object.__setattr__(self, field, ordered_unique(values, key))
        for lower, upper in (
            (self.min_voltage, self.max_voltage),
            (self.declared_temp_min_c, self.declared_temp_max_c),
        ):
            if lower is not None and upper is not None and lower > upper:
                raise ValueError("Declared bounds are reversed")
        if self.nominal_voltage is not None and (
            self.min_voltage is not None
            and self.nominal_voltage < self.min_voltage
            or self.max_voltage is not None
            and self.nominal_voltage > self.max_voltage
        ):
            raise ValueError("Nominal voltage outside declared bounds")
        return self

    def select_range(self, range_no: int) -> InstrumentRangeSnapshot:
        for item in self.ranges:
            if item.range_no == range_no:
                return item
        raise ValueError("Selected range does not exist")


class EnvironmentSnapshot(Frozen):
    measured_at: AwareDatetime
    temperature_c: Number | None = None
    relative_humidity_percent: Number | None = Field(None, ge=0, le=100)
    pressure_hpa: Number | None = Field(None, gt=0)
    voltage_v: Number | None = Field(None, ge=0)


class EquipmentCalibrationSnapshot(Frozen):
    reference: Text
    category: Text
    manufacturer: str | None = None
    model: str | None = None
    serial_number: str | None = None
    calibration_certificate_no: str | None = None
    calibration_date: date | None = None
    calibration_due_date: date | None = None
    accuracy_or_class: str | None = None
    # Exact acceptance/uncertainty values belong in specialized typed extensions.


class ProcedureContext(Frozen):
    test_code: Text
    procedure_variant: Text
    procedure_schema_version: Text
    evaluation_context: Text
    protocol: Text


class RangeProcedureContext(ProcedureContext):
    range_no: PositiveInt
    scenario: Text


class Observation(Frozen):
    test_code: Text
    protocol: Text
    observation_schema_version: Text
    sequence_no: PositiveInt


class ObservationBatch(Frozen):
    test_code: Text
    protocol: Text
    observation_schema_version: Text
    rows: tuple[SerializeAsAny[Observation], ...]

    @model_validator(mode="after")
    def identity(self):
        for row in self.rows:
            if (row.test_code, row.protocol, row.observation_schema_version) != (
                self.test_code,
                self.protocol,
                self.observation_schema_version,
            ):
                raise ValueError("Mixed/incompatible observation schemas")
        object.__setattr__(self, "rows", ordered_unique(self.rows, lambda r: r.sequence_no))
        return self


class RuleReference(Frozen):
    rule_id: Text
    part: str
    edition: str
    source_identity: str
    clause: str | None = None
    source_digest: Digest | None = None


class ApplicabilityDecision(Frozen):
    applicability: Applicability
    reason: Text
    rule_references: tuple[RuleReference, ...] = ()
    unresolved_rule_ids: tuple[Text, ...] = ()
    feature: str | None = None
    range_no: PositiveInt | None = None
    scenario: str | None = None


class CalculationTraceEntry(Frozen):
    name: Text
    expression: Text
    value: Number
    unit: Unit
    rule_references: tuple[RuleReference, ...] = ()


class AcceptanceLimit(Frozen):
    name: Text
    value: Number
    unit: Unit
    operator: Operator
    semantics: Semantics
    rule_references: tuple[RuleReference, ...]

    @model_validator(mode="after")
    def sign(self):
        if self.semantics == "ABSOLUTE" and self.value < 0:
            raise ValueError("Negative absolute limit")
        return self


class FailedCondition(Frozen):
    code: Text
    reason: Text
    actual: Number
    limit: AcceptanceLimit


class ProcedureValidationIssue(Frozen):
    code: Literal["MISSING_REQUIRED_OBSERVATIONS", "EVALUATION_NOT_POSSIBLE"]
    category: Literal[
        "COUNT",
        "LOAD_COVERAGE",
        "ORDER",
        "TRANSITION",
        "STAGE",
        "STABILIZATION",
        "TIMING",
        "RANGE",
        "GEOMETRY",
        "ENVIRONMENT",
        "POWER",
        "SEVERITY",
        "EQUIPMENT",
        "FUNCTIONAL",
        "EVIDENCE",
    ]
    reason: Text
    sequence_no: PositiveInt | None = None
    rule_references: tuple[RuleReference, ...] = ()


class EvaluationOutput(Frozen):
    compliance_outcome: Literal[ComplianceOutcome.COMPLIANT, ComplianceOutcome.NONCOMPLIANT]
    calculations: tuple[CalculationTraceEntry, ...]
    acceptance_limits: tuple[AcceptanceLimit, ...]
    failed_conditions: tuple[FailedCondition, ...]
    reasons: tuple[Text, ...]

    @model_validator(mode="after")
    def failures(self):
        if bool(self.failed_conditions) != (
            self.compliance_outcome == ComplianceOutcome.NONCOMPLIANT
        ):
            raise ValueError("Determined outcome and failures disagree")
        return self


class ComplianceResult(Frozen):
    test_code: Text
    applicability: ApplicabilityDecision
    evaluation_status: Literal[
        EvaluationStatus.INCOMPLETE, EvaluationStatus.REVIEW_REQUIRED, EvaluationStatus.COMPLETE
    ]
    compliance_outcome: ComplianceOutcome
    calculations: tuple[CalculationTraceEntry, ...] = ()
    acceptance_limits: tuple[AcceptanceLimit, ...] = ()
    failed_conditions: tuple[FailedCondition, ...] = ()
    procedure_issues: tuple[ProcedureValidationIssue, ...] = ()
    reasons: tuple[Text, ...]
    issue_code: str | None = None
    unresolved_rule_ids: tuple[Text, ...] = ()
    rule_references: tuple[RuleReference, ...] = ()
    ruleset_version: Text
    ruleset_configuration_hash: Digest
    engine_version: Text
    input_hash: Digest
    synthetic_fixture: StrictBool = False

    @model_validator(mode="after")
    def coherent(self):
        if self.evaluation_status != EvaluationStatus.COMPLETE:
            if self.compliance_outcome != ComplianceOutcome.UNDETERMINED or (
                self.calculations or self.acceptance_limits or self.failed_conditions
            ):
                raise ValueError("Blocked/incomplete procedures cannot publish acceptance")
        elif self.compliance_outcome == ComplianceOutcome.UNDETERMINED:
            raise ValueError("Complete run must have a determined outcome")
        if self.compliance_outcome == ComplianceOutcome.NOT_APPLICABLE:
            if self.applicability.applicability != Applicability.NOT_APPLICABLE:
                raise ValueError("N/A requires an explicit applicability decision")
        return self

    @property
    def result_hash(self) -> str:
        from app.compliance.canonical import content_hash

        return content_hash(self)
