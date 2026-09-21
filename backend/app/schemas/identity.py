from datetime import datetime
from typing import Annotated, Literal
from uuid import UUID
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from pydantic import (
    BaseModel,
    ConfigDict,
    EmailStr,
    Field,
    SecretStr,
    field_validator,
    model_validator,
)


class Schema(BaseModel):
    model_config = ConfigDict(extra="forbid", from_attributes=True)


Password = Annotated[SecretStr, Field(min_length=12, max_length=128)]


class Login(Schema):
    email: EmailStr
    password: SecretStr = Field(min_length=1, max_length=128)


class PasswordChange(Schema):
    current_password: SecretStr = Field(min_length=1, max_length=128)
    new_password: Password


class PasswordReset(Schema):
    new_password: Password


class AssignmentCreate(Schema):
    role_code: Literal[
        "ADMIN", "LAB_TECHNICIAN", "LAB_ENGINEER", "REVIEWER", "APPROVING_OFFICER", "VIEWER"
    ]
    scope_type: Literal["GLOBAL", "LABORATORY"]
    laboratory_id: UUID | None = None

    @model_validator(mode="after")
    def scope_matches(self):
        if (self.scope_type == "GLOBAL") != (self.laboratory_id is None):
            raise ValueError("GLOBAL requires no lab; LABORATORY requires a lab")
        if self.scope_type == "GLOBAL" and self.role_code != "ADMIN":
            raise ValueError("Only ADMIN supports GLOBAL assignments")
        return self


class UserCreate(Schema):
    email: EmailStr
    full_name: str = Field(min_length=1, max_length=200)
    password: Password
    initial_assignment: AssignmentCreate | None = None


class UserPatch(Schema):
    full_name: str | None = Field(default=None, min_length=1, max_length=200)
    is_active: bool | None = None

    @model_validator(mode="after")
    def supplied_values(self):
        if not self.model_fields_set or any(
            getattr(self, f) is None for f in self.model_fields_set
        ):
            raise ValueError("Supply at least one non-null field")
        return self


class UserView(Schema):
    id: UUID
    email: str
    full_name: str
    is_active: bool
    lock_version: int
    last_login_at: datetime | None


class LaboratoryCreate(Schema):
    name: str = Field(min_length=1, max_length=200)
    code: str = Field(min_length=1, max_length=50, pattern=r"^[A-Za-z0-9_-]+$")
    address_line1: str = Field(min_length=1, max_length=300)
    address_line2: str = Field(max_length=300)
    city: str = Field(min_length=1, max_length=100)
    state: str = Field(min_length=1, max_length=100)
    postal_code: str = Field(min_length=1, max_length=30)
    country: str = Field(min_length=1, max_length=100)
    phone: str = Field(min_length=1, max_length=40)
    email: EmailStr
    accreditation_no: str = Field(min_length=1, max_length=100)
    timezone: str = "UTC"

    @field_validator("timezone")
    @classmethod
    def valid_timezone(cls, value: str) -> str:
        try:
            ZoneInfo(value)
        except ZoneInfoNotFoundError:
            raise ValueError("Unknown IANA timezone") from None
        return value


class LaboratoryPatch(Schema):
    name: str | None = Field(default=None, min_length=1, max_length=200)
    address_line1: str | None = Field(default=None, min_length=1, max_length=300)
    address_line2: str | None = Field(default=None, max_length=300)
    city: str | None = Field(default=None, min_length=1, max_length=100)
    state: str | None = Field(default=None, min_length=1, max_length=100)
    postal_code: str | None = Field(default=None, min_length=1, max_length=30)
    country: str | None = Field(default=None, min_length=1, max_length=100)
    phone: str | None = Field(default=None, min_length=1, max_length=40)
    email: EmailStr | None = None
    accreditation_no: str | None = Field(default=None, min_length=1, max_length=100)
    timezone: str | None = None
    is_active: bool | None = None

    @model_validator(mode="after")
    def supplied_values(self):
        if not self.model_fields_set or any(
            getattr(self, f) is None for f in self.model_fields_set
        ):
            raise ValueError("Supply at least one non-null field")
        if self.timezone is not None:
            LaboratoryCreate.valid_timezone(self.timezone)
        return self


class LaboratoryView(LaboratoryCreate):
    id: UUID
    is_active: bool
    lock_version: int
    logo_attachment_id: UUID | None


class AssignmentView(Schema):
    id: UUID
    user_id: UUID
    role_id: UUID
    scope_type: str
    laboratory_id: UUID | None
    assigned_by: UUID
    assigned_at: datetime
    revoked_by: UUID | None
    revoked_at: datetime | None
    revocation_reason: str | None
    lock_version: int


class TokenView(Schema):
    access_token: str
    token_type: str = "bearer"
    expires_in: int


class Page[T](Schema):
    items: list[T]
    page: int
    page_size: int
    total: int
