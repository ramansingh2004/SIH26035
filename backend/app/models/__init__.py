"""Persistence models registered through the current build phase."""

from app.models.foundations import (
    Attachment,
    AttachmentLink,
    AttachmentUpload,
    ChecklistRule,
    RuleDefinition,
    RuleSetRecord,
    TestDefinitionRecord,
    TestEquipment,
)
from app.models.identity import (
    AuditEvent,
    IdempotencyKey,
    Laboratory,
    Permission,
    RefreshSession,
    Role,
    RolePermission,
    User,
    UserRoleAssignment,
)
from app.models.master_data import Instrument, InstrumentComponent, InstrumentRange, Manufacturer

__all__ = [
    "Attachment",
    "AttachmentLink",
    "AttachmentUpload",
    "ChecklistRule",
    "RuleDefinition",
    "RuleSetRecord",
    "TestDefinitionRecord",
    "TestEquipment",
    "Instrument",
    "InstrumentComponent",
    "InstrumentRange",
    "Manufacturer",
    "AuditEvent",
    "IdempotencyKey",
    "Laboratory",
    "Permission",
    "RefreshSession",
    "Role",
    "RolePermission",
    "User",
    "UserRoleAssignment",
]
