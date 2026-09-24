"""Phase 3 query and lock ownership."""

from datetime import UTC, datetime

from sqlalchemy import and_, exists, or_, select, text

from app.models import (
    AttachmentLink,
    AttachmentUpload,
    AuditEvent,
    RuleSetRecord,
    TestEquipment,
)
from app.repositories.identity import IdentityRepository


class FoundationRepository(IdentityRepository):
    async def staged_cleanup_candidates(self, now, limit):
        succeeded = (
            select(AuditEvent.id)
            .where(
                AuditEvent.action == "attachment.staged_deleted",
                AuditEvent.entity_type == "attachment_uploads",
                AuditEvent.entity_id == AttachmentUpload.id,
            )
            .correlate(AttachmentUpload)
            .exists()
        )
        statement = (
            select(AttachmentUpload)
            .where(
                ~succeeded,
                or_(
                    and_(
                        AttachmentUpload.upload_status == "PENDING",
                        AttachmentUpload.expires_at <= now,
                    ),
                    AttachmentUpload.upload_status.in_(("FAILED", "EXPIRED", "COMPLETED")),
                ),
            )
            .order_by(
                AttachmentUpload.expires_at,
                AttachmentUpload.id,
            )
            .limit(limit)
        )
        return list((await self.session.scalars(statement)).all())

    async def staged_cleanup_succeeded(self, upload_id):
        return bool(
            await self.session.scalar(
                select(
                    exists().where(
                        AuditEvent.action == "attachment.staged_deleted",
                        AuditEvent.entity_type == "attachment_uploads",
                        AuditEvent.entity_id == upload_id,
                    )
                )
            )
        )

    async def calibration_reference_exists(self, attachment_id):
        from app.models.testing import TestRunEquipment

        return (
            await self.session.scalar(
                select(TestRunEquipment.id)
                .where(TestRunEquipment.calibration_attachment_id == attachment_id)
                .limit(1)
            )
            is not None
        )

    async def generated_document_reference_exists(self, attachment_id):
        from app.models.report import ReportFile, ReportPreview

        if await self.session.scalar(
            select(exists().where(ReportFile.attachment_id == attachment_id))
        ):
            return True

        text_id = str(attachment_id)
        return bool(
            await self.session.scalar(
                select(
                    exists().where(
                        ReportPreview.preview_status == "READY",
                        ReportPreview.expires_at > datetime.now(UTC),
                        or_(
                            ReportPreview.file_attachment_ids["pdf"].astext == text_id,
                            ReportPreview.file_attachment_ids["docx"].astext == text_id,
                        ),
                    )
                )
            )
        )

    async def get(self, model, identifier, *, lock=False):
        stmt = select(model).where(model.id == identifier).execution_options(populate_existing=True)
        return await self.session.scalar(stmt.with_for_update() if lock else stmt)

    async def equipment(self, labs, page, size, lab=None, active=None):
        stmt = select(TestEquipment).where(TestEquipment.laboratory_id.in_(labs))
        if lab:
            stmt = stmt.where(TestEquipment.laboratory_id == lab)
        if active is not None:
            stmt = stmt.where(TestEquipment.is_active == active)
        return await self.page(
            stmt.order_by(TestEquipment.created_at, TestEquipment.id), page, size
        )

    async def rulesets(self, page, size):
        return await self.page(
            select(RuleSetRecord).order_by(RuleSetRecord.created_at, RuleSetRecord.id), page, size
        )

    async def ruleset_version(self, metadata):
        return await self.session.scalar(
            select(RuleSetRecord).where(
                RuleSetRecord.standard_code == metadata.standard_code,
                RuleSetRecord.edition == metadata.edition,
                RuleSetRecord.version == metadata.version,
            )
        )

    async def catalog(self, model, identifier):
        return list(
            (
                await self.session.scalars(
                    select(model)
                    .where(model.rule_set_id == identifier)
                    .order_by(model.sort_order, model.id)
                )
            ).all()
        )

    async def ruleset_lock(self):
        await self.session.execute(
            text("SELECT pg_advisory_xact_lock(hashtext('phase3:rulesets'))")
        )

    async def active_links(self, identifier):
        return list(
            (
                await self.session.scalars(
                    select(AttachmentLink)
                    .where(
                        AttachmentLink.attachment_id == identifier,
                        AttachmentLink.unlinked_at.is_(None),
                    )
                    .order_by(AttachmentLink.entity_type, AttachmentLink.entity_id)
                )
            ).all()
        )

    async def link(self, attachment_id, target):
        return await self.session.scalar(
            select(AttachmentLink)
            .where(
                AttachmentLink.attachment_id == attachment_id,
                AttachmentLink.entity_type == target.entity_type,
                AttachmentLink.entity_id == target.entity_id,
                AttachmentLink.purpose == target.purpose,
            )
            .with_for_update()
        )
