"""Version 1 master-data wire shapes; unknown fields/facts remain explicit."""

from datetime import datetime
from decimal import Decimal
from typing import Annotated, Literal
from uuid import UUID

from pydantic import (
    BeforeValidator,
    EmailStr,
    Field,
    PlainSerializer,
    create_model,
    model_validator,
)

from app.core.master_data import decimal_text, stored_decimal
from app.schemas.identity import Schema

Text = Annotated[str, Field(min_length=1, max_length=200, pattern=r"\S")]
Description = Annotated[str, Field(min_length=1, max_length=1000, pattern=r"\S")]
Mass = Annotated[
    Decimal,
    BeforeValidator(lambda v: stored_decimal(v, 20, 6)),
    PlainSerializer(decimal_text, return_type=str, when_used="json"),
]
Voltage = Annotated[
    Decimal,
    BeforeValidator(lambda v: stored_decimal(v, 12, 4)),
    PlainSerializer(decimal_text, return_type=str, when_used="json"),
]
Temperature = Annotated[
    Decimal,
    BeforeValidator(lambda v: stored_decimal(v, 8, 3)),
    PlainSerializer(decimal_text, return_type=str, when_used="json"),
]
ExactNumber = Annotated[Decimal, PlainSerializer(decimal_text, return_type=str, when_used="json")]
ClassCode = Literal["I", "II", "III", "IIII"]


class Address(Schema):
    schema_version: Literal[1] = 1
    address_line1: Description
    address_line2: Description | None = None
    city: Text | None = None
    state: Text | None = None
    postal_code: Text | None = None
    country: Text | None = None


class ManufacturerData(Schema):
    name: Text
    registration_no: Text | None = None
    address: Address
    contact_person: Text | None = None
    email: EmailStr | None = None
    phone: Text | None = None
    country: Text | None = None


class ManufacturerCreate(ManufacturerData):
    laboratory_id: UUID


class Versioned(Schema):
    id: UUID
    lock_version: int
    created_at: datetime
    updated_at: datetime
    created_by: UUID


class ManufacturerView(ManufacturerCreate, Versioned):
    is_active: bool


class InterfacePort(Schema):
    name: Text
    interface_type: Text | None = None
    purpose: Text | None = None
    externally_accessible: bool | None = None


class InstrumentMetadata(Schema):
    is_direct_sales: bool | None = None
    is_price_computing: bool | None = None
    is_labeling: bool | None = None
    data_storage_device_present: bool | None = None
    interfaces: list[InterfacePort] | None = Field(None, max_length=100)
    peripherals: list[Text] | None = Field(None, max_length=100)
    battery_charging_during_operation: bool | None = None
    vehicle_powered: bool | None = None
    vehicle_power_details: Description | None = None
    declared_operating_conditions: Description | None = None
    declared_installation: Description | None = None


class CapacityData(Schema):
    min_capacity_g: Mass | None = None
    max_capacity_g: Mass = Field(gt=0)
    scale_interval_d_g: Mass = Field(gt=0)
    verification_interval_e_g: Mass = Field(gt=0)

    @model_validator(mode="after")
    def capacity_sanity(self):
        if self.min_capacity_g is not None and not (0 <= self.min_capacity_g < self.max_capacity_g):
            raise ValueError("Min must be nonnegative and smaller than Max")
        return self


class InstrumentData(CapacityData):
    manufacturer_id: UUID
    model_name: Text
    type_designation: Text | None = None
    serial_number: Text | None = None
    accuracy_class: ClassCode
    range_type: Text | None = None
    indication_type: Text | None = None
    is_self_indicating: bool | None = None
    is_electronic: bool | None = None
    is_software_controlled: bool | None = None
    is_portable: bool | None = None
    is_mobile: bool | None = None
    load_receptor_type: Text | None = None
    support_point_count: int | None = Field(None, gt=0, le=2147483647, strict=True)
    tare_type: Text | None = None
    maximum_tare_g: Mass | None = Field(None, ge=0)
    zero_setting_type: Text | None = None
    zero_tracking_available: bool | None = None
    level_indicator_available: bool | None = None
    automatic_tilt_sensor: bool | None = None
    power_supply_type: Text | None = None
    nominal_voltage: Voltage | None = Field(None, gt=0)
    min_voltage: Voltage | None = Field(None, gt=0)
    max_voltage: Voltage | None = Field(None, gt=0)
    declared_temp_min_c: Temperature | None = None
    declared_temp_max_c: Temperature | None = None
    software_identifier: Text | None = None
    metadata_schema_version: Literal[1] = 1
    metadata_json: InstrumentMetadata = Field(default_factory=InstrumentMetadata)

    @model_validator(mode="after")
    def declared_envelopes(self):
        if self.min_voltage is not None and self.max_voltage is not None:
            if self.min_voltage > self.max_voltage:
                raise ValueError("Declared voltage bounds are reversed")
        if self.nominal_voltage is not None:
            if self.min_voltage is not None and self.nominal_voltage < self.min_voltage:
                raise ValueError("Nominal voltage below declared minimum")
            if self.max_voltage is not None and self.nominal_voltage > self.max_voltage:
                raise ValueError("Nominal voltage above declared maximum")
        if self.declared_temp_min_c is not None and self.declared_temp_max_c is not None:
            if self.declared_temp_min_c > self.declared_temp_max_c:
                raise ValueError("Declared temperature bounds are reversed")
        return self


class InstrumentCreate(InstrumentData):
    laboratory_id: UUID


class InstrumentView(InstrumentCreate, Versioned):
    verification_intervals_n: ExactNumber
    instrument_status: Literal["ACTIVE", "ARCHIVED"]


class RangeData(CapacityData):
    range_no: int = Field(gt=0, le=2147483647, strict=True)


class RangeView(RangeData, Versioned):
    instrument_id: UUID
    is_active: bool


class ComponentSpecifications(Schema):
    schema_version: Literal[1] = 1
    description: Description | None = None
    rated_capacity_g: Mass | None = Field(None, gt=0)
    nominal_voltage: Voltage | None = Field(None, gt=0)
    interface_type: Text | None = None
    software_identifier: Text | None = None


class ComponentData(Schema):
    component_type: Text
    manufacturer_name: Text | None = None
    model: Text | None = None
    serial_or_type: Text | None = None
    certificate_reference: Text | None = None
    technical_specifications: ComponentSpecifications = Field(
        default_factory=ComponentSpecifications
    )
    notes: Description | None = None


class ComponentView(ComponentData, Versioned):
    instrument_id: UUID
    is_active: bool


def partial(name, source):
    # Partial updates are merged and revalidated as the full data model in the service.
    return create_model(
        name,
        __base__=Schema,
        **{
            key: (
                Annotated[field.annotation | None, *field.metadata]
                if field.metadata
                else field.annotation | None,
                None,
            )
            for key, field in source.model_fields.items()
        },
    )


ManufacturerPatch = partial("ManufacturerPatch", ManufacturerData)
InstrumentPatch = partial("InstrumentPatch", InstrumentData)
RangePatch = partial("RangePatch", RangeData)
ComponentPatch = partial("ComponentPatch", ComponentData)


class ArchiveRequest(Schema):
    reason: Description


class ConfigurationRequest(InstrumentCreate):
    ranges: list[RangeData] = Field(default_factory=list, max_length=100)
    components: list[ComponentData] = Field(default_factory=list, max_length=100)
