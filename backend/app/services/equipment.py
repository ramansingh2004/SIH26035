"""Equipment master facts and immutable snapshot serialization; REG-16 unresolved."""

from datetime import datetime
from uuid import uuid4

from pydantic import ValidationError

from app.core.concurrency import etag, require_match
from app.core.errors import AppError, denied, missing
from app.models import TestEquipment
from app.repositories.foundations import FoundationRepository
from app.schemas.foundations import CalibrationSnapshot, EquipmentData, EquipmentView
from app.services.administration import paged, view
from app.services.audit import AuditService
from app.services.authorization import AuthorizationService
from app.services.master_data import stored_values


def calibration_snapshot(
    equipment: EquipmentView,
    captured_at: datetime,
    *,
    certificate=None,
) -> CalibrationSnapshot:
    values = equipment.model_dump()
    metadata = values.pop("metadata_json")
    return CalibrationSnapshot(
        equipment_id=values.pop("id"),
        equipment_version=values.pop("lock_version"),
        captured_at=captured_at,
        calibration_attachment_id=getattr(certificate, "id", None),
        calibration_attachment_sha256=getattr(certificate, "sha256", None),
        calibration_attachment_object_version=getattr(
            certificate,
            "object_version",
            None,
        ),
        **{k: v for k, v in values.items() if k in CalibrationSnapshot.model_fields},
        **metadata,
    )


class EquipmentService:
    def __init__(self, session, context):
        self.session = session
        self.repo = FoundationRepository(session)
        self.authz = AuthorizationService(self.repo)
        self.audit = AuditService(self.repo, context)

    async def scoped(self, actor, identifier, permission, *, mutation=False):
        _, grants = await self.authz.current(actor, lock=mutation)
        labs = grants.labs_for(permission)
        if not labs:
            raise denied()
        row = await self.repo.get(TestEquipment, identifier)
        if row is None or row.laboratory_id not in labs:
            raise missing()
        if mutation:
            await self.active_lab(row.laboratory_id)
            row = await self.repo.get(TestEquipment, identifier, lock=True)
        return row

    async def active_lab(self, identifier):
        lab = await self.repo.lab(identifier, lock=True)
        if lab is None or not lab.is_active:
            raise AppError(409, "LABORATORY_INACTIVE", "Active laboratory required")

    async def listing(self, actor, page, size, lab=None, active=None):
        async with self.session.begin():
            _, grants = await self.authz.current(actor)
            labs = grants.labs_for("equipment:read")
            if not labs or (lab and lab not in labs):
                raise denied()
            rows, total = await self.repo.equipment(labs, page, size, lab, active)
            return paged(EquipmentView, rows, total, page, size)

    async def detail(self, actor, identifier):
        async with self.session.begin():
            return view(EquipmentView, await self.scoped(actor, identifier, "equipment:read"))

    async def create(self, actor, data):
        async with self.session.begin():
            _, grants = await self.authz.current(actor, lock=True)
            grants.require("equipment:create", data.laboratory_id)
            await self.active_lab(data.laboratory_id)
            row = TestEquipment(id=uuid4(), created_by=actor.user_id, **stored_values(data))
            self.repo.add(row)
            await self.repo.flush()
            result = view(EquipmentView, row)
            self.audit.record(
                "equipment.created",
                actor.user_id,
                "test_equipment",
                row.id,
                lab=row.laboratory_id,
                after=result,
                target=1,
            )
            return result

    async def mutate(self, actor, identifier, match, data=None, reason=None):
        async with self.session.begin():
            action = "update" if data is not None else "archive"
            row = await self.scoped(actor, identifier, f"equipment:{action}", mutation=True)
            require_match(match, etag(row.lock_version))
            if not row.is_active:
                raise AppError(409, "EQUIPMENT_ARCHIVED", "Archived equipment is read-only")
            before = view(EquipmentView, row)
            if data is None:
                row.is_active = False
            else:
                changes = data.model_dump(exclude_unset=True)
                if not changes:
                    raise AppError(422, "INVALID_INPUT", "Supply a changed field")
                try:
                    merged = EquipmentData.model_validate(
                        {k: before[k] for k in EquipmentData.model_fields} | changes
                    )
                except ValidationError:
                    raise AppError(422, "INVALID_INPUT", "Invalid equipment data") from None
                for key, value in stored_values(merged).items():
                    setattr(row, key, value)
            row.lock_version += 1
            await self.repo.flush()
            after = view(EquipmentView, row)
            self.audit.record(
                f"equipment.{action}d",
                actor.user_id,
                "test_equipment",
                row.id,
                lab=row.laboratory_id,
                before=before,
                after=after,
                source=before["lock_version"],
                target=row.lock_version,
                reason=reason,
            )
            return after
