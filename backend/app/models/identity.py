"""Relational identity, token, audit and retry foundations."""

from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import CITEXT, JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class Identity:
    id: Mapped[UUID] = mapped_column(
        primary_key=True, default=uuid4, server_default=text("gen_random_uuid()")
    )


class Mutable:
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
    lock_version: Mapped[int] = mapped_column(Integer, default=1, server_default="1")


class User(Identity, Mutable, Base):
    __tablename__ = "users"
    __table_args__ = (CheckConstraint("lock_version > 0", name="ck_users_version"),)
    email: Mapped[str] = mapped_column(CITEXT, unique=True)
    password_hash: Mapped[str] = mapped_column(Text)
    full_name: Mapped[str] = mapped_column(String(200))
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, server_default=text("true"))
    last_login_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_by: Mapped[UUID | None] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"))


class Role(Identity, Base):
    __tablename__ = "roles"
    code: Mapped[str] = mapped_column(String(40), unique=True)
    name: Mapped[str] = mapped_column(String(100))
    description: Mapped[str | None] = mapped_column(Text)


class Permission(Identity, Base):
    __tablename__ = "permissions"
    code: Mapped[str] = mapped_column(String(80), unique=True)
    description: Mapped[str] = mapped_column(Text)


class RolePermission(Base):
    __tablename__ = "role_permissions"
    role_id: Mapped[UUID] = mapped_column(
        ForeignKey("roles.id", ondelete="RESTRICT"), primary_key=True
    )
    permission_id: Mapped[UUID] = mapped_column(
        ForeignKey("permissions.id", ondelete="RESTRICT"), primary_key=True
    )


class Laboratory(Identity, Mutable, Base):
    __tablename__ = "laboratories"
    __table_args__ = (
        CheckConstraint("lock_version > 0", name="ck_labs_version"),
        CheckConstraint("logo_attachment_id IS NULL", name="ck_labs_logo_phase1"),
    )
    name: Mapped[str] = mapped_column(String(200))
    code: Mapped[str] = mapped_column(String(50), unique=True)
    address_line1: Mapped[str] = mapped_column(String(300))
    address_line2: Mapped[str] = mapped_column(String(300))
    city: Mapped[str] = mapped_column(String(100))
    state: Mapped[str] = mapped_column(String(100))
    postal_code: Mapped[str] = mapped_column(String(30))
    country: Mapped[str] = mapped_column(String(100))
    phone: Mapped[str] = mapped_column(String(40))
    email: Mapped[str] = mapped_column(CITEXT)
    accreditation_no: Mapped[str] = mapped_column(String(100))
    logo_attachment_id: Mapped[UUID | None] = mapped_column()
    timezone: Mapped[str] = mapped_column(String(100), default="UTC", server_default="UTC")
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, server_default=text("true"))
    created_by: Mapped[UUID] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"))


class UserRoleAssignment(Identity, Base):
    __tablename__ = "user_role_assignments"
    __table_args__ = (
        CheckConstraint(
            "(scope_type = 'GLOBAL' AND laboratory_id IS NULL) OR (scope_type = "
            "'LABORATORY' AND laboratory_id IS NOT NULL)",
            name="ck_assignment_scope",
        ),
        CheckConstraint("lock_version > 0", name="ck_assignment_version"),
        CheckConstraint(
            "(revoked_at IS NULL AND revoked_by IS NULL AND revocation_reason IS "
            "NULL) OR (revoked_at IS NOT NULL AND revoked_by IS NOT NULL AND "
            "revocation_reason IS NOT NULL)",
            name="ck_assignment_revocation",
        ),
        Index(
            "uq_assignment_global_active",
            "user_id",
            "role_id",
            unique=True,
            postgresql_where=text("revoked_at IS NULL AND scope_type = 'GLOBAL'"),
        ),
        Index(
            "uq_assignment_lab_active",
            "user_id",
            "role_id",
            "laboratory_id",
            unique=True,
            postgresql_where=text("revoked_at IS NULL AND scope_type = 'LABORATORY'"),
        ),
    )
    user_id: Mapped[UUID] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"), index=True)
    role_id: Mapped[UUID] = mapped_column(ForeignKey("roles.id", ondelete="RESTRICT"))
    scope_type: Mapped[str] = mapped_column(String(20))
    laboratory_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("laboratories.id", ondelete="RESTRICT"), index=True
    )
    assigned_by: Mapped[UUID] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"))
    assigned_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    revoked_by: Mapped[UUID | None] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"))
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    revocation_reason: Mapped[str | None] = mapped_column(Text)
    lock_version: Mapped[int] = mapped_column(Integer, default=1, server_default="1")


class RefreshSession(Identity, Base):
    __tablename__ = "auth_refresh_sessions"
    __table_args__ = (
        CheckConstraint(
            "expires_at <= family_expires_at AND created_at < expires_at", name="ck_refresh_expiry"
        ),
        Index(
            "uq_refresh_successor",
            "parent_session_id",
            unique=True,
            postgresql_where=text("parent_session_id IS NOT NULL"),
        ),
    )
    user_id: Mapped[UUID] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"), index=True)
    family_id: Mapped[UUID] = mapped_column(index=True)
    token_digest: Mapped[str] = mapped_column(String(64), unique=True)
    parent_session_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("auth_refresh_sessions.id", ondelete="RESTRICT")
    )
    replaced_by_session_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("auth_refresh_sessions.id", ondelete="RESTRICT")
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    family_expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    consumed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    revocation_reason: Mapped[str | None] = mapped_column(String(100))
    client_ip: Mapped[str | None] = mapped_column(String(64))
    user_agent: Mapped[str | None] = mapped_column(String(500))


class AuditEvent(Identity, Base):
    __tablename__ = "audit_events"
    __table_args__ = (
        CheckConstraint("actor_type IN ('USER','SYSTEM','ANONYMOUS')", name="ck_audit_actor_type"),
        CheckConstraint("actor_type <> 'USER' OR actor_id IS NOT NULL", name="ck_audit_actor"),
        Index("ix_audit_entity", "entity_type", "entity_id", "created_at"),
        Index("ix_audit_login", "action", "ip_address", "created_at"),
    )
    actor_id: Mapped[UUID | None] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"))
    actor_type: Mapped[str] = mapped_column(String(20))
    laboratory_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("laboratories.id", ondelete="RESTRICT"), index=True
    )
    action: Mapped[str] = mapped_column(String(100))
    entity_type: Mapped[str] = mapped_column(String(80))
    entity_id: Mapped[UUID | None] = mapped_column()
    source_revision: Mapped[int | None] = mapped_column()
    target_revision: Mapped[int | None] = mapped_column()
    request_id: Mapped[str] = mapped_column(String(100))
    correlation_id: Mapped[str] = mapped_column(String(100))
    reason: Mapped[str | None] = mapped_column(Text)
    before_json: Mapped[dict | None] = mapped_column(JSONB)
    after_json: Mapped[dict | None] = mapped_column(JSONB)
    ip_address: Mapped[str | None] = mapped_column(String(64))
    user_agent: Mapped[str | None] = mapped_column(String(500))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class IdempotencyKey(Identity, Base):
    __tablename__ = "idempotency_keys"
    __table_args__ = (
        UniqueConstraint(
            "actor_id", "scope_key", "operation", "key", name="uq_idempotency_request"
        ),
        CheckConstraint(
            "operation_status IN ('IN_PROGRESS','SUCCEEDED','FAILED')", name="ck_idempotency_status"
        ),
    )
    actor_id: Mapped[UUID] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"))
    scope_key: Mapped[str] = mapped_column(String(36))
    operation: Mapped[str] = mapped_column(String(100))
    key: Mapped[str] = mapped_column(String(200))
    request_hash: Mapped[str] = mapped_column(String(64))
    operation_status: Mapped[str] = mapped_column(String(20))
    response_status: Mapped[int | None] = mapped_column()
    response_body: Mapped[dict | None] = mapped_column(JSONB)
    resource_ids: Mapped[dict] = mapped_column(
        JSONB, default=dict, server_default=text("'{}'::jsonb")
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
