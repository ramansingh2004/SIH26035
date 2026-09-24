"""Persistence models registered through the current build phase."""

from app.models import testing as testing
from app.models.checklist import ChecklistResponse
from app.models.construction import ConstructionExamination, ConstructionItem
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
from app.models.report import (
    Report,
    ReportFile,
    ReportGeneration,
    ReportNumberCounter,
    ReportPreview,
)
from app.models.review import ApprovalAction, CorrectionRequest, SessionApprovalSnapshot

__all__ = [
    "ApprovalAction",
    "CorrectionRequest",
    "SessionApprovalSnapshot",
    "ReportNumberCounter",
    "Report",
    "ReportGeneration",
    "ReportFile",
    "ReportPreview",
    "ChecklistResponse",
    "ConstructionExamination",
    "ConstructionItem",
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
