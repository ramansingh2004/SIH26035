"""Private evidence orchestration, with source/ownership rechecks at publication."""

from datetime import UTC, datetime, timedelta
from uuid import uuid4

from app.core.concurrency import etag, require_match
from app.core.errors import AppError, denied, missing
from app.models import (
    Attachment,
    AttachmentLink,
    AttachmentUpload,
    Instrument,
    InstrumentComponent,
    InstrumentRange,
    Laboratory,
    Manufacturer,
    TestEquipment,
)
from app.repositories.foundations import FoundationRepository
from app.schemas.foundations import EvidenceTarget
from app.services.audit import AuditService
from app.services.authorization import AuthorizationService
from app.storage.objects import verify_content

TARGETS = {
    m.__tablename__: m
    for m in (
        Laboratory,
        Manufacturer,
        Instrument,
        InstrumentRange,
        InstrumentComponent,
        TestEquipment,
    )
}


def attachment_view(row):
    return {
        "id": str(row.id),
        "laboratory_id": str(row.laboratory_id),
        "file_name": row.file_name,
        "content_type": row.content_type,
        "file_size": row.file_size,
        "sha256": row.sha256,
        "lock_version": row.lock_version,
        "archived_at": row.archived_at.isoformat() if row.archived_at else None,
    }


class AttachmentService:
    def __init__(self, session, context, storage, seconds=300):
        self.session, self.storage, self.seconds = session, storage, seconds
        self.repo = FoundationRepository(session)
        self.authz = AuthorizationService(self.repo)
        self.audit = AuditService(self.repo, context)

    async def target(self, actor, target, permission, match):
        _, grants = await self.authz.current(actor, lock=True)
        labs = grants.labs_for(permission)
        if not labs:
            raise denied()
        model = TARGETS.get(target.entity_type)
        if model is None:
            raise AppError(422, "INVALID_EVIDENCE_TARGET", "Unsupported evidence target")
        row = await self.repo.get(model, target.entity_id)
        if row is None:
            raise missing()
        parent = None
        if isinstance(row, (InstrumentRange, InstrumentComponent)):
            parent = await self.repo.get(Instrument, row.instrument_id)
            lab_id = parent.laboratory_id
        else:
            lab_id = row.id if isinstance(row, Laboratory) else row.laboratory_id
        if lab_id not in labs:
            raise missing()
        lab = await self.repo.lab(lab_id, lock=True)
        if not lab.is_active:
            raise AppError(409, "EVIDENCE_TARGET_PROTECTED", "Inactive laboratory is read-only")
        if parent is not None:
            parent = await self.repo.get(Instrument, parent.id, lock=True)
            if parent.instrument_status != "ACTIVE":
                raise AppError(409, "EVIDENCE_TARGET_PROTECTED", "Archived parent is read-only")
        row = await self.repo.get(model, target.entity_id, lock=True)
        if (
            getattr(row, "is_active", True) is False
            or getattr(row, "instrument_status", "ACTIVE") != "ACTIVE"
        ):
            raise AppError(409, "EVIDENCE_TARGET_PROTECTED", "Archived target is read-only")
        require_match(match, etag(row.lock_version))
        return row, parent, lab_id

    def changed_target(self, actor, row, parent, lab):
        before = row.lock_version
        row.lock_version += 1
        if parent is not None:
            parent.lock_version += 1
        self.audit.record(
            "evidence.target_changed",
            actor.user_id,
            row.__tablename__,
            row.id,
            lab=lab,
            source=before,
            target=row.lock_version,
            after={"lock_version": row.lock_version},
        )

    async def presign(self, actor, data, match):
        # Authorize before revealing storage availability or issuing a capability URL.
        async with self.session.begin():
            _, _, lab = await self.target(actor, data, "attachment:create", match)
            if data.laboratory_id != lab:
                raise AppError(
                    409, "ATTACHMENT_LAB_MISMATCH", "Evidence must belong to target laboratory"
                )
        await self.storage.ready()
        identifier = uuid4()
        key = f"staged/{lab}/{actor.user_id}/{identifier.hex}"
        url = await self.storage.presign_upload(
            key, data.content_type, data.file_size, self.seconds
        )
        async with self.session.begin():
            await self.target(actor, data, "attachment:create", match)
            row = AttachmentUpload(
                id=identifier,
                laboratory_id=lab,
                requested_by=actor.user_id,
                target_type=data.entity_type,
                target_id=data.entity_id,
                purpose=data.purpose,
                storage_key=key,
                expected_file_name=data.file_name,
                expected_content_type=data.content_type,
                expected_size=data.file_size,
                expected_sha256=data.sha256,
                expires_at=datetime.now(UTC) + timedelta(seconds=self.seconds),
            )
            self.repo.add(row)
            await self.repo.flush()
            self.audit.record(
                "attachment.upload_requested",
                actor.user_id,
                "attachment_uploads",
                row.id,
                lab=lab,
                after={"size": data.file_size, "content_type": data.content_type},
                target=1,
            )
            return {
                "upload_id": str(row.id),
                "upload_url": url,
                "method": "PUT",
                "headers": {
                    "Content-Type": data.content_type,
                    "Content-Length": str(data.file_size),
                },
                "expires_at": row.expires_at.isoformat(),
                "target_etag": match,
                "lock_version": row.lock_version,
            }

    async def owned_upload(self, actor, identifier, *, lock=False):
        _, grants = await self.authz.current(actor, lock=True)
        if not grants.labs_for("attachment:create"):
            raise denied()
        row = await self.repo.get(AttachmentUpload, identifier, lock=lock)
        if (
            row is None
            or row.requested_by != actor.user_id
            or row.laboratory_id not in grants.labs_for("attachment:create")
        ):
            raise missing()
        expected = f"staged/{row.laboratory_id}/{row.requested_by}/{row.id.hex}"
        if row.storage_key != expected:
            raise AppError(
                409, "UPLOAD_OWNERSHIP_INVALID", "Server upload ownership is inconsistent"
            )
        return row

    @staticmethod
    def pending(row):
        if row.upload_status != "PENDING":
            raise AppError(409, "UPLOAD_STATE_CONFLICT", "Upload is no longer pending")
        if row.expires_at <= datetime.now(UTC):
            raise AppError(410, "UPLOAD_EXPIRED", "Upload expired; request a new upload")

    async def failed(self, actor, identifier, code):
        async with self.session.begin():
            row = await self.repo.get(AttachmentUpload, identifier, lock=True)
            if row and row.requested_by == actor.user_id and row.upload_status == "PENDING":
                row.upload_status = "EXPIRED" if code == "UPLOAD_EXPIRED" else "FAILED"
                row.lock_version += 1
                self.audit.record(
                    "attachment.finalization_failed",
                    actor.user_id,
                    "attachment_uploads",
                    row.id,
                    lab=row.laboratory_id,
                    after={"failure_code": code},
                    target=row.lock_version,
                )

    async def complete(self, actor, identifier, match):
        try:
            async with self.session.begin():
                upload = await self.owned_upload(actor, identifier)
                self.pending(upload)
                target = EvidenceTarget(
                    entity_type=upload.target_type,
                    entity_id=upload.target_id,
                    purpose=upload.purpose,
                )
                await self.target(actor, target, "attachment:create", match)
                key, size, mime, digest, lab = (
                    upload.storage_key,
                    upload.expected_size,
                    upload.expected_content_type,
                    upload.expected_sha256,
                    upload.laboratory_id,
                )
            await self.storage.ready()
            obj = await self.storage.read(key)
            verify_content(obj, size, mime, digest)
            published_key = f"evidence/{lab}/{identifier}/{uuid4().hex}"
            version = await self.storage.publish(published_key, obj)
            async with self.session.begin():
                row, parent, lab = await self.target(actor, target, "attachment:create", match)
                upload = await self.owned_upload(actor, identifier, lock=True)
                self.pending(upload)
                attachment = Attachment(
                    id=uuid4(),
                    laboratory_id=lab,
                    attachment_type="EVIDENCE",
                    file_name=upload.expected_file_name,
                    content_type=mime,
                    file_size=size,
                    storage_provider=self.storage.provider,
                    storage_key=published_key,
                    object_version=version,
                    sha256=digest,
                    uploaded_by=actor.user_id,
                    metadata_json={"schema_version": 1},
                )
                self.repo.add(attachment)
                await self.repo.flush()
                link = AttachmentLink(
                    id=uuid4(),
                    attachment_id=attachment.id,
                    entity_type=target.entity_type,
                    entity_id=target.entity_id,
                    purpose=target.purpose,
                    linked_by=actor.user_id,
                )
                self.repo.add(link)
                upload.upload_status = "COMPLETED"
                upload.completed_attachment_id = attachment.id
                upload.lock_version += 1
                self.changed_target(actor, row, parent, lab)
                await self.repo.flush()
                result = attachment_view(attachment)
                self.audit.record(
                    "attachment.finalized",
                    actor.user_id,
                    "attachments",
                    attachment.id,
                    lab=lab,
                    after=result | {"upload_id": str(upload.id), "link_id": str(link.id)},
                    target=1,
                )
                return result | {"link_id": str(link.id), "target_etag": etag(row.lock_version)}
        except AppError as error:
            if error.code not in (
                "PERMISSION_DENIED",
                "RESOURCE_NOT_FOUND",
                "AUTHENTICATION_REQUIRED",
            ):
                await self.failed(actor, identifier, error.code)
            raise

    async def authorized_attachment(self, actor, identifier, permission, lock=False):
        _, grants = await self.authz.current(actor, lock=lock)
        labs = grants.labs_for(permission)
        if not labs:
            raise denied()
        row = await self.repo.get(Attachment, identifier)
        if row is None or row.laboratory_id not in labs:
            raise missing()
        if lock:
            lab = await self.repo.lab(row.laboratory_id, lock=True)
            if lab is None or not lab.is_active:
                raise AppError(409, "LABORATORY_INACTIVE", "Active laboratory required")
            row = await self.repo.get(Attachment, identifier, lock=True)
        if row.archived_at:
            raise AppError(409, "ATTACHMENT_ARCHIVED", "Attachment is archived")
        return row

    async def link(self, actor, identifier, data, match):
        async with self.session.begin():
            row, parent, lab = await self.target(actor, data, "attachment:create", match)
            attachment = await self.authorized_attachment(
                actor, identifier, "attachment:create", True
            )
            if attachment.laboratory_id != lab:
                raise AppError(
                    409, "ATTACHMENT_LAB_MISMATCH", "Evidence and target laboratories differ"
                )
            existing = await self.repo.link(identifier, data)
            if existing:
                raise AppError(
                    409,
                    "EVIDENCE_LINK_EXISTS",
                    "Evidence link already exists, including archived history",
                )
            link = AttachmentLink(
                id=uuid4(),
                attachment_id=identifier,
                entity_type=data.entity_type,
                entity_id=data.entity_id,
                purpose=data.purpose,
                linked_by=actor.user_id,
            )
            self.repo.add(link)
            attachment.lock_version += 1
            self.changed_target(actor, row, parent, lab)
            await self.repo.flush()
            self.audit.record(
                "attachment.linked",
                actor.user_id,
                "attachment_links",
                link.id,
                lab=lab,
                after={"attachment_id": str(identifier), "target_id": str(row.id)},
                target=1,
            )
            return {
                "id": str(link.id),
                "lock_version": link.lock_version,
                "target_etag": etag(row.lock_version),
                "attachment_etag": etag(attachment.lock_version),
            }

    async def unlink(self, actor, identifier, link_id, match, reason):
        async with self.session.begin():
            await self.authorized_attachment(actor, identifier, "attachment:delete")
            link = await self.repo.get(AttachmentLink, link_id)
            if link is None or link.attachment_id != identifier:
                raise missing()
            target = EvidenceTarget(
                entity_type=link.entity_type, entity_id=link.entity_id, purpose=link.purpose
            )
            row, parent, lab = await self.target(actor, target, "attachment:delete", match)
            attachment = await self.authorized_attachment(
                actor, identifier, "attachment:delete", True
            )
            link = await self.repo.get(AttachmentLink, link_id, lock=True)
            if link.unlinked_at:
                raise AppError(409, "EVIDENCE_LINK_REMOVED", "Link already removed")
            link.unlinked_at = datetime.now(UTC)
            link.lock_version += 1
            attachment.lock_version += 1
            self.changed_target(actor, row, parent, lab)
            self.audit.record(
                "attachment.unlinked",
                actor.user_id,
                "attachment_links",
                link.id,
                lab=lab,
                reason=reason,
                source=link.lock_version - 1,
                target=link.lock_version,
            )
            return {
                "target_etag": etag(row.lock_version),
                "attachment_etag": etag(attachment.lock_version),
            }

    async def archive(self, actor, identifier, match, reason):
        async with self.session.begin():
            attachment = await self.authorized_attachment(
                actor, identifier, "attachment:delete", True
            )
            require_match(match, etag(attachment.lock_version))
            if await self.repo.active_links(identifier):
                raise AppError(
                    409,
                    "PROTECTED_EVIDENCE",
                    "Unlink editable evidence before archiving; protected links cannot be removed",
                )
            attachment.archived_at = datetime.now(UTC)
            attachment.lock_version += 1
            self.audit.record(
                "attachment.archived",
                actor.user_id,
                "attachments",
                identifier,
                lab=attachment.laboratory_id,
                reason=reason,
                source=attachment.lock_version - 1,
                target=attachment.lock_version,
            )

    async def download(self, actor, identifier):
        async with self.session.begin():
            attachment = await self.authorized_attachment(actor, identifier, "attachment:read")
            if attachment.storage_provider != self.storage.provider:
                raise AppError(
                    503, "STORAGE_PROVIDER_MISMATCH", "Original storage provider required"
                )
            key, version = attachment.storage_key, attachment.object_version
            result = attachment_view(attachment)
        await self.storage.ready()
        url = await self.storage.presign_download(key, version, self.seconds)
        async with self.session.begin():
            attachment = await self.authorized_attachment(actor, identifier, "attachment:read")
            self.audit.record(
                "attachment.download_authorized",
                actor.user_id,
                "attachments",
                identifier,
                lab=attachment.laboratory_id,
                after={"sha256": attachment.sha256},
            )
        return result | {"download_url": url, "expires_in": self.seconds}
