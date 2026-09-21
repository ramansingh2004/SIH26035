"""Laboratory-owned mutable master data, independent of future evaluation snapshots."""

from decimal import Decimal
from uuid import UUID

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    ForeignKey,
    ForeignKeyConstraint,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    text,
)
from sqlalchemy.dialects.postgresql import CITEXT, JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.models.identity import Identity, Mutable


class Attributed:
    __mapper_args__ = {"eager_defaults": True}
    created_by: Mapped[UUID] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"))


class Manufacturer(Identity, Mutable, Attributed, Base):
    __tablename__ = "manufacturers"
    __table_args__ = (
        UniqueConstraint("id", "laboratory_id", name="uq_manufacturer_lab"),
        CheckConstraint("lock_version > 0", name="ck_manufacturer_version"),
        CheckConstraint(
            "address ? 'schema_version' AND address->>'schema_version' = '1' AND "
            "jsonb_typeof(address) = 'object'",
            name="ck_manufacturer_address",
        ),
        Index("ix_manufacturer_lab_name", "laboratory_id", "name"),
    )
    laboratory_id: Mapped[UUID] = mapped_column(ForeignKey("laboratories.id", ondelete="RESTRICT"))
    name: Mapped[str] = mapped_column(String(200))
    registration_no: Mapped[str | None] = mapped_column(String(200))
    address: Mapped[dict] = mapped_column(JSONB)
    contact_person: Mapped[str | None] = mapped_column(String(200))
    email: Mapped[str | None] = mapped_column(CITEXT)
    phone: Mapped[str | None] = mapped_column(String(200))
    country: Mapped[str | None] = mapped_column(String(200))
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, server_default=text("true"))


def capacity_constraints(prefix):
    return (
        CheckConstraint(
            "max_capacity_g > 0 AND max_capacity_g <> 'NaN'::numeric AND "
            "scale_interval_d_g > 0 AND scale_interval_d_g <> 'NaN'::numeric AND "
            "verification_interval_e_g > 0 AND verification_interval_e_g <> "
            "'NaN'::numeric",
            name=f"ck_{prefix}_positive",
        ),
        CheckConstraint(
            "min_capacity_g IS NULL OR (min_capacity_g >= 0 AND min_capacity_g < max_capacity_g)",
            name=f"ck_{prefix}_min",
        ),
        CheckConstraint("lock_version > 0", name=f"ck_{prefix}_version"),
    )


class Capacities:
    max_capacity_g: Mapped[Decimal] = mapped_column(Numeric(20, 6))
    min_capacity_g: Mapped[Decimal | None] = mapped_column(Numeric(20, 6))
    scale_interval_d_g: Mapped[Decimal] = mapped_column(Numeric(20, 6))
    verification_interval_e_g: Mapped[Decimal] = mapped_column(Numeric(20, 6))


class Instrument(Identity, Mutable, Attributed, Capacities, Base):
    __tablename__ = "instruments"
    __table_args__ = (
        *capacity_constraints("instrument"),
        ForeignKeyConstraint(
            ["manufacturer_id", "laboratory_id"],
            ["manufacturers.id", "manufacturers.laboratory_id"],
            ondelete="RESTRICT",
            name="fk_instrument_manufacturer_lab",
        ),
        CheckConstraint("accuracy_class IN ('I','II','III','IIII')", name="ck_instrument_class"),
        CheckConstraint("instrument_status IN ('ACTIVE','ARCHIVED')", name="ck_instrument_status"),
        CheckConstraint(
            "verification_intervals_n > 0 AND verification_intervals_n * "
            "verification_interval_e_g = max_capacity_g",
            name="ck_instrument_exact_n",
        ),
        CheckConstraint(
            "metadata_schema_version = 1 AND jsonb_typeof(metadata_json) = 'object'",
            name="ck_instrument_metadata",
        ),
        CheckConstraint(
            "support_point_count IS NULL OR support_point_count > 0", name="ck_instrument_supports"
        ),
        CheckConstraint("maximum_tare_g IS NULL OR maximum_tare_g >= 0", name="ck_instrument_tare"),
        CheckConstraint(
            "(nominal_voltage IS NULL OR nominal_voltage > 0) AND (min_voltage IS NULL OR "
            "min_voltage > 0) AND (max_voltage IS NULL OR max_voltage > 0) AND "
            "(min_voltage IS NULL OR max_voltage IS NULL OR min_voltage <= max_voltage) "
            "AND (nominal_voltage IS NULL OR min_voltage IS NULL OR nominal_voltage >= "
            "min_voltage) AND (nominal_voltage IS NULL OR max_voltage IS NULL OR "
            "nominal_voltage <= max_voltage)",
            name="ck_instrument_voltages",
        ),
        CheckConstraint(
            "declared_temp_min_c IS NULL OR declared_temp_max_c IS NULL OR "
            "declared_temp_min_c <= declared_temp_max_c",
            name="ck_instrument_temperatures",
        ),
        Index("ix_instrument_lab_manufacturer", "laboratory_id", "manufacturer_id"),
    )
    laboratory_id: Mapped[UUID] = mapped_column(ForeignKey("laboratories.id", ondelete="RESTRICT"))
    manufacturer_id: Mapped[UUID] = mapped_column()
    model_name: Mapped[str] = mapped_column(String(200))
    type_designation: Mapped[str | None] = mapped_column(String(200))
    serial_number: Mapped[str | None] = mapped_column(String(200))
    accuracy_class: Mapped[str] = mapped_column(String(4))
    verification_intervals_n: Mapped[Decimal] = mapped_column(Numeric())
    range_type: Mapped[str | None] = mapped_column(String(200))
    indication_type: Mapped[str | None] = mapped_column(String(200))
    is_self_indicating: Mapped[bool | None] = mapped_column(Boolean)
    is_electronic: Mapped[bool | None] = mapped_column(Boolean)
    is_software_controlled: Mapped[bool | None] = mapped_column(Boolean)
    is_portable: Mapped[bool | None] = mapped_column(Boolean)
    is_mobile: Mapped[bool | None] = mapped_column(Boolean)
    load_receptor_type: Mapped[str | None] = mapped_column(String(200))
    support_point_count: Mapped[int | None] = mapped_column(Integer)
    tare_type: Mapped[str | None] = mapped_column(String(200))
    maximum_tare_g: Mapped[Decimal | None] = mapped_column(Numeric(20, 6))
    zero_setting_type: Mapped[str | None] = mapped_column(String(200))
    zero_tracking_available: Mapped[bool | None] = mapped_column(Boolean)
    level_indicator_available: Mapped[bool | None] = mapped_column(Boolean)
    automatic_tilt_sensor: Mapped[bool | None] = mapped_column(Boolean)
    power_supply_type: Mapped[str | None] = mapped_column(String(200))
    nominal_voltage: Mapped[Decimal | None] = mapped_column(Numeric(12, 4))
    min_voltage: Mapped[Decimal | None] = mapped_column(Numeric(12, 4))
    max_voltage: Mapped[Decimal | None] = mapped_column(Numeric(12, 4))
    declared_temp_min_c: Mapped[Decimal | None] = mapped_column(Numeric(8, 3))
    declared_temp_max_c: Mapped[Decimal | None] = mapped_column(Numeric(8, 3))
    software_identifier: Mapped[str | None] = mapped_column(String(200))
    instrument_status: Mapped[str] = mapped_column(
        String(20), default="ACTIVE", server_default="ACTIVE"
    )
    metadata_schema_version: Mapped[int] = mapped_column(Integer, default=1, server_default="1")
    metadata_json: Mapped[dict] = mapped_column(JSONB)


class InstrumentRange(Identity, Mutable, Attributed, Capacities, Base):
    __tablename__ = "instrument_ranges"
    __table_args__ = (
        *capacity_constraints("range"),
        UniqueConstraint("instrument_id", "range_no", name="uq_instrument_range_no"),
        CheckConstraint("range_no > 0", name="ck_range_number"),
    )
    instrument_id: Mapped[UUID] = mapped_column(
        ForeignKey("instruments.id", ondelete="RESTRICT"), index=True
    )
    range_no: Mapped[int] = mapped_column(Integer)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, server_default=text("true"))


class InstrumentComponent(Identity, Mutable, Attributed, Base):
    __tablename__ = "instrument_components"
    __table_args__ = (
        CheckConstraint("lock_version > 0", name="ck_component_version"),
        CheckConstraint(
            "technical_specifications ? 'schema_version' AND "
            "technical_specifications->>'schema_version' = '1' AND "
            "jsonb_typeof(technical_specifications) = 'object'",
            name="ck_component_schema",
        ),
    )
    instrument_id: Mapped[UUID] = mapped_column(
        ForeignKey("instruments.id", ondelete="RESTRICT"), index=True
    )
    component_type: Mapped[str] = mapped_column(String(200))
    manufacturer_name: Mapped[str | None] = mapped_column(String(200))
    model: Mapped[str | None] = mapped_column(String(200))
    serial_or_type: Mapped[str | None] = mapped_column(String(200))
    certificate_reference: Mapped[str | None] = mapped_column(String(200))
    technical_specifications: Mapped[dict] = mapped_column(JSONB)
    notes: Mapped[str | None] = mapped_column(Text)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, server_default=text("true"))
