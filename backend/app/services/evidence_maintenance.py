"""Phase 14 staged-evidence cleanup and retry hardening.

This service performs no regulatory interpretation.  It only cleans private
staged upload objects whose database lifecycle is terminal or expired.
Published evidence objects are never accepted as cleanup targets.
"""

from datetime import UTC, datetime

from app.core.errors import AppError
from app.models import AttachmentUpload
from app.repositories.foundations import FoundationRepository
from app.services.audit import AuditService


class EvidenceMaintenanceService:
    def __init__(self, session, storage, context):
        self.session = session
        self.storage = storage
        self.repo = FoundationRepository(session)
        self.audit = AuditService(self.repo, context)

    async def cleanup_once(self, *, limit: int = 100):
        if not 1 <= limit <= 1000:
            raise ValueError("Cleanup limit must be between 1 and 1000")

        await self.storage.ready()
        now = datetime.now(UTC)

        async with self.session.begin():
            rows = await self.repo.staged_cleanup_candidates(now, limit)
            candidates = []
            for row in rows:
                candidates.append(
                    {
                        "id": row.id,
                        "laboratory_id": row.laboratory_id,
                        "storage_key": row.storage_key,
                        "status": row.upload_status,
                    }
                )
                if row.upload_status == "PENDING":
                    before = row.lock_version
                    row.upload_status = "EXPIRED"
                    row.lock_version += 1
                    self.audit.record(
                        "attachment.upload_expired",
                        None,
                        "attachment_uploads",
                        row.id,
                        lab=row.laboratory_id,
                        source=before,
                        target=row.lock_version,
                        system=True,
                    )

        cleaned = 0
        failed = 0
        deleted_versions = 0

        for candidate in candidates:
            try:
                deleted = await self.storage.delete_staged(candidate["storage_key"])
            except AppError as error:
                failed += 1
                async with self.session.begin():
                    if not await self.repo.staged_cleanup_succeeded(candidate["id"]):
                        self.audit.record(
                            "attachment.staged_cleanup_failed",
                            None,
                            "attachment_uploads",
                            candidate["id"],
                            lab=candidate["laboratory_id"],
                            reason=error.code,
                            after={"upload_status": candidate["status"]},
                            system=True,
                        )
                continue

            async with self.session.begin():
                row = await self.repo.get(
                    AttachmentUpload,
                    candidate["id"],
                    lock=True,
                )
                if row is None:
                    continue
                if not await self.repo.staged_cleanup_succeeded(row.id):
                    self.audit.record(
                        "attachment.staged_deleted",
                        None,
                        "attachment_uploads",
                        row.id,
                        lab=row.laboratory_id,
                        after={
                            "upload_status": row.upload_status,
                            "deleted_versions": deleted,
                        },
                        system=True,
                    )
                    cleaned += 1
                    deleted_versions += deleted

        return {
            "scanned": len(candidates),
            "cleaned": cleaned,
            "failed": failed,
            "deleted_versions": deleted_versions,
        }
