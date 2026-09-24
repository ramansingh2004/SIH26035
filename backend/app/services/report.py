"""Phase 16 report preview, generation, issue and revision workflow."""

import asyncio
import hashlib
from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

from app.compliance.canonical import content_hash
from app.core.concurrency import etag, require_match
from app.core.errors import AppError, denied, missing
from app.models.foundations import Attachment
from app.models.report import (
    Report,
    ReportFile,
    ReportGeneration,
    ReportPreview,
)
from app.reporting.context import (
    TEMPLATE_VERSION,
    issuance_manifest,
    official_context,
    preview_context,
    renderer_manifest,
    report_hash,
)
from app.reporting.renderers import DOCX_MIME, PDF_MIME, render_pair
from app.repositories.report import ReportRepository
from app.schemas.report import (
    ReportFileView,
    ReportGenerationResponse,
    ReportGenerationView,
    ReportPreviewView,
    ReportView,
)
from app.services.approval_snapshot import ApprovalSnapshotBuilder
from app.services.audit import AuditService
from app.services.authorization import AuthorizationService
from app.services.idempotency import IdempotencyService
from app.storage.objects import StoredObject, verify_content

FORMAT_MIME = {
    "pdf": PDF_MIME,
    "docx": DOCX_MIME,
}
DETERMINED_OUTCOMES = {"COMPLIANT", "NONCOMPLIANT"}


def preview_view(row):
    return ReportPreviewView.model_validate(row).model_dump(mode="json")


def report_view(row):
    return ReportView.model_validate(row).model_dump(mode="json")


def generation_view(row):
    return ReportGenerationView.model_validate(row).model_dump(mode="json")


def file_view(row):
    return ReportFileView.model_validate(row).model_dump(mode="json")


def generation_response(report, generation, files):
    return ReportGenerationResponse(
        report=ReportView.model_validate(report),
        generation=ReportGenerationView.model_validate(generation),
        files=[ReportFileView.model_validate(row) for row in files],
    ).model_dump(mode="json")


class ReportService:
    def __init__(
        self,
        session,
        context,
        storage,
        *,
        download_seconds=300,
        preview_hours=24,
    ):
        self.session = session
        self.context = context
        self.storage = storage
        self.download_seconds = download_seconds
        self.preview_hours = preview_hours
        self.repo = ReportRepository(session)
        self.authz = AuthorizationService(self.repo)
        self.audit = AuditService(self.repo, context)
        self.idempotency = IdempotencyService(session)

    async def scoped_session(self, actor, identifier, permission, *, lock=False):
        _, grants = await self.authz.current(actor, lock=lock)
        labs = grants.labs_for(permission)
        if not labs:
            raise denied()

        row = await self.repo.test_session(identifier, lock=lock)
        if row is None or row.laboratory_id not in labs:
            raise missing()

        if lock:
            laboratory = await self.repo.lab(row.laboratory_id, lock=True)
            if laboratory is None or not laboratory.is_active:
                raise AppError(
                    409,
                    "LABORATORY_INACTIVE",
                    "Active laboratory required for reporting",
                )
            row = await self.repo.test_session(identifier, lock=True)
        return row

    async def scoped_preview(self, actor, identifier, permission, *, lock=False):
        _, grants = await self.authz.current(actor, lock=lock)
        labs = grants.labs_for(permission)
        if not labs:
            raise denied()

        preview = await self.repo.preview(identifier, lock=lock)
        if preview is None:
            raise missing()
        test_session = await self.repo.test_session(
            preview.test_session_id,
            lock=lock,
        )
        if test_session is None or test_session.laboratory_id not in labs:
            raise missing()
        return preview, test_session

    async def scoped_report(self, actor, identifier, permission, *, lock=False):
        _, grants = await self.authz.current(actor, lock=lock)
        labs = grants.labs_for(permission)
        if not labs:
            raise denied()

        report = await self.repo.report(identifier)
        if report is None:
            raise missing()
        test_session = await self.repo.test_session(
            report.test_session_id,
            lock=lock,
        )
        if test_session is None or test_session.laboratory_id not in labs:
            raise missing()
        if lock:
            laboratory = await self.repo.lab(
                test_session.laboratory_id,
                lock=True,
            )
            if laboratory is None or not laboratory.is_active:
                raise AppError(
                    409,
                    "LABORATORY_INACTIVE",
                    "Active laboratory required for reporting",
                )
            test_session = await self.repo.test_session(
                report.test_session_id,
                lock=True,
            )
            report = await self.repo.report(identifier, lock=True)
        return report, test_session

    async def _validate_intended_issuer(self, user_id, laboratory_id):
        user = await self.repo.user(user_id)
        if user is None or not user.is_active:
            raise AppError(
                422,
                "INVALID_INPUT",
                "Intended issuer must be an active user",
            )
        grants = await self.authz.for_user(user_id)
        if laboratory_id not in grants.labs_for("report:issue"):
            raise AppError(
                422,
                "INVALID_INPUT",
                "Intended issuer lacks report:issue in this laboratory",
            )

    async def _approved_snapshot(self, test_session):
        if (
            test_session.workflow_status != "APPROVED"
            or test_session.evaluation_status != "COMPLETE"
            or test_session.compliance_outcome not in DETERMINED_OUTCOMES
        ):
            raise AppError(
                409,
                "SESSION_NOT_READY_FOR_APPROVAL",
                "Official report generation requires an APPROVED complete session",
            )
        snapshot = await self.repo.approval_snapshot(test_session.id)
        if (
            snapshot is None
            or snapshot.regulatory_revision != test_session.regulatory_revision
            or snapshot.snapshot_hash != content_hash(snapshot.snapshot_json)
        ):
            raise AppError(
                409,
                "SESSION_NOT_READY_FOR_APPROVAL",
                "Current immutable approval snapshot is unavailable or invalid",
            )
        return snapshot

    @staticmethod
    def _reg17_issue_gate(snapshot):
        validation = snapshot.snapshot_json.get("ruleset_record", {}).get("validation_summary", {})
        if validation.get("SYNTHETIC_TEST_FIXTURE_ONLY") is True:
            return
        if validation.get("REG-17") == "VERIFIED":
            return
        raise AppError(
            409,
            "TODO_REGULATORY_VALIDATION",
            "REG-17 authority acceptance is required before official issue",
            {"regulatory_item": "REG-17"},
        )

    @staticmethod
    def _generation_context_integrity(report, generation, snapshot):
        if content_hash(generation.report_context_snapshot) != generation.context_hash:
            raise AppError(
                409,
                "REPORT_GENERATION_FAILED",
                "Persisted report context hash is invalid",
            )
        context = generation.report_context_snapshot
        control = context.get("document_control", {})
        if (
            context.get("document_kind") != "OFFICIAL_REPORT"
            or control.get("report_number") != report.report_number
            or control.get("revision_no") != report.revision_no
            or control.get("intended_issuer_id") != str(generation.intended_issuer_id)
            or control.get("planned_issue_date") != generation.planned_issue_date.isoformat()
            or control.get("source_regulatory_revision") != generation.source_regulatory_revision
            or generation.source_regulatory_revision != snapshot.regulatory_revision
            or context.get("regulatory_record") != snapshot.snapshot_json
        ):
            raise AppError(
                409,
                "ISSUE_METADATA_MISMATCH",
                "Generated report context no longer matches theapproved snapshotand issue metadata",
            )

    async def _mark_preview_failed(self, preview_id, actor_id, code):
        try:
            async with self.session.begin():
                row = await self.repo.preview(preview_id, lock=True)
                if row is None or row.preview_status != "GENERATING":
                    return
                test_session = await self.repo.test_session(row.test_session_id)
                row.preview_status = "FAILED"
                row.error_code = code
                await self.repo.flush()
                self.audit.record(
                    "report.preview_failed",
                    actor_id,
                    "report_previews",
                    row.id,
                    lab=(test_session.laboratory_id if test_session is not None else None),
                    after={
                        "preview_status": row.preview_status,
                        "error_code": row.error_code,
                    },
                    source=row.source_regulatory_revision,
                    target=row.source_regulatory_revision,
                )
        except Exception:
            return

    async def create_preview(self, actor, identifier, match):
        async with self.session.begin():
            test_session = await self.scoped_session(
                actor,
                identifier,
                "report:preview",
                lock=True,
            )
            require_match(match, etag(test_session.lock_version))

            regulatory_record = await ApprovalSnapshotBuilder(self.session).build(test_session)
            context = preview_context(
                regulatory_record,
                requested_by=str(actor.user_id),
                source_regulatory_revision=test_session.regulatory_revision,
            )
            digest = content_hash(context)
            row = ReportPreview(
                id=uuid4(),
                test_session_id=test_session.id,
                source_regulatory_revision=test_session.regulatory_revision,
                preview_context_snapshot=context,
                preview_status="GENERATING",
                requested_by=actor.user_id,
                expires_at=datetime.now(UTC) + timedelta(hours=self.preview_hours),
                context_hash=digest,
                file_attachment_ids={},
            )
            self.repo.add(row)
            await self.repo.flush()
            preview_id = row.id
            laboratory_id = test_session.laboratory_id
            self.audit.record(
                "report.preview_started",
                actor.user_id,
                "report_previews",
                row.id,
                lab=laboratory_id,
                after={
                    "test_session_id": str(test_session.id),
                    "source_regulatory_revision": test_session.regulatory_revision,
                    "context_hash": digest,
                    "expires_at": row.expires_at.isoformat(),
                },
                source=test_session.regulatory_revision,
                target=test_session.regulatory_revision,
            )

        try:
            rendered = await asyncio.to_thread(render_pair, context)
            await self.storage.ready()
            published = {}
            for file_format in ("pdf", "docx"):
                body, mime = rendered[file_format]
                file_hash = hashlib.sha256(body).hexdigest()
                key = f"previews/{laboratory_id}/{preview_id}/{uuid4().hex}"
                object_version = await self.storage.publish(
                    key,
                    StoredObject(
                        body=body,
                        content_type=mime,
                        version="generated",
                    ),
                )
                published[file_format] = {
                    "body": body,
                    "mime": mime,
                    "hash": file_hash,
                    "key": key,
                    "version": object_version,
                }

            async with self.session.begin():
                await self.scoped_preview(
                    actor,
                    preview_id,
                    "report:preview",
                )
                row = await self.repo.preview(preview_id, lock=True)
                if row is None or row.preview_status != "GENERATING":
                    raise AppError(
                        409,
                        "REPORT_GENERATION_FAILED",
                        "Preview state changed during rendering",
                    )

                ids = {}
                for file_format in ("pdf", "docx"):
                    item = published[file_format]
                    attachment = Attachment(
                        id=uuid4(),
                        laboratory_id=laboratory_id,
                        attachment_type="REPORT_PREVIEW",
                        file_name=f"UNOFFICIAL_PREVIEW_{preview_id}.{file_format}",
                        content_type=item["mime"],
                        file_size=len(item["body"]),
                        storage_provider=self.storage.provider,
                        storage_key=item["key"],
                        object_version=item["version"],
                        sha256=item["hash"],
                        uploaded_by=actor.user_id,
                        metadata_json={
                            "schema_version": 1,
                            "report_preview_id": str(preview_id),
                            "format": file_format.upper(),
                            "unofficial": True,
                        },
                    )
                    self.repo.add(attachment)
                    ids[file_format] = str(attachment.id)

                await self.repo.flush()
                row.file_attachment_ids = ids
                row.preview_status = "READY"
                await self.repo.flush()
                await self.session.refresh(row)

                result = preview_view(row)
                self.audit.record(
                    "report.preview_ready",
                    actor.user_id,
                    "report_previews",
                    row.id,
                    lab=laboratory_id,
                    after={
                        "preview_status": "READY",
                        "context_hash": row.context_hash,
                        "files": {
                            file_format: published[file_format]["hash"]
                            for file_format in ("pdf", "docx")
                        },
                    },
                    source=row.source_regulatory_revision,
                    target=row.source_regulatory_revision,
                )
                return result
        except Exception as exc:
            code = exc.code if isinstance(exc, AppError) else "REPORT_GENERATION_FAILED"
            await self._mark_preview_failed(preview_id, actor.user_id, code)
            async with self.session.begin():
                row = await self.repo.preview(preview_id)
                if row is None:
                    raise
                return preview_view(row)

    async def preview_detail(self, actor, identifier):
        async with self.session.begin():
            row, _ = await self.scoped_preview(
                actor,
                identifier,
                "report:read",
            )
            return preview_view(row)

    async def preview_download(self, actor, identifier, file_format):
        if file_format not in FORMAT_MIME:
            raise AppError(
                422,
                "INVALID_INPUT",
                "Preview format must be pdf or docx",
            )

        async with self.session.begin():
            row, test_session = await self.scoped_preview(
                actor,
                identifier,
                "report:read",
            )
            if row.preview_status != "READY":
                raise AppError(
                    409,
                    "REPORT_GENERATION_FAILED",
                    "Preview files are not READY",
                    {"preview_status": row.preview_status},
                )
            if row.expires_at <= datetime.now(UTC):
                raise AppError(
                    410,
                    "REPORT_PREVIEW_EXPIRED",
                    "Preview has expired",
                )
            raw_id = row.file_attachment_ids.get(file_format)
            if not isinstance(raw_id, str):
                raise AppError(
                    409,
                    "REPORT_GENERATION_FAILED",
                    "Preview file reference is incomplete",
                )
            try:
                attachment_id = UUID(raw_id)
            except ValueError:
                raise AppError(
                    409,
                    "REPORT_GENERATION_FAILED",
                    "Preview file reference is invalid",
                ) from None

            attachment = await self.repo.attachment(attachment_id)
            if (
                attachment is None
                or attachment.laboratory_id != test_session.laboratory_id
                or attachment.attachment_type != "REPORT_PREVIEW"
                or attachment.content_type != FORMAT_MIME[file_format]
                or attachment.archived_at is not None
            ):
                raise AppError(
                    409,
                    "REPORT_GENERATION_FAILED",
                    "Preview file integrity check failed",
                )
            if attachment.storage_provider != self.storage.provider:
                raise AppError(
                    503,
                    "STORAGE_PROVIDER_MISMATCH",
                    "Original storage provider required",
                )
            key = attachment.storage_key
            version = attachment.object_version
            metadata = {
                "preview_id": str(row.id),
                "format": file_format,
                "attachment_id": str(attachment.id),
                "sha256": attachment.sha256,
                "file_name": attachment.file_name,
            }

        await self.storage.ready()
        url = await self.storage.presign_download(
            key,
            version,
            self.download_seconds,
        )

        async with self.session.begin():
            row, test_session = await self.scoped_preview(
                actor,
                identifier,
                "report:read",
            )
            self.audit.record(
                "report.preview_download_authorized",
                actor.user_id,
                "report_previews",
                row.id,
                lab=test_session.laboratory_id,
                after={
                    "format": file_format,
                    "attachment_id": metadata["attachment_id"],
                    "sha256": metadata["sha256"],
                },
                source=row.source_regulatory_revision,
                target=row.source_regulatory_revision,
            )

        return metadata | {
            "download_url": url,
            "expires_in": self.download_seconds,
        }

    async def _generation_reservation(
        self,
        actor,
        scope_identifier,
        laboratory_id,
        operation,
        key,
        payload,
        authorize,
    ):
        if not key:
            raise AppError(
                428,
                "IDEMPOTENCY_KEY_REQUIRED",
                "Idempotency-Key required",
            )
        return await self.idempotency.reserve(
            actor.user_id,
            str(laboratory_id),
            operation,
            key,
            payload | {"scope_id": str(scope_identifier)},
            authorize,
        )

    async def _render_official_generation(
        self,
        actor,
        report_id,
        generation_id,
        laboratory_id,
        context,
        reservation,
    ):
        try:
            rendered = await asyncio.to_thread(render_pair, context)
            await self.storage.ready()
            published = {}
            for file_format in ("pdf", "docx"):
                body, mime = rendered[file_format]
                digest = hashlib.sha256(body).hexdigest()
                key = f"reports/{laboratory_id}/{generation_id}/{uuid4().hex}"
                version = await self.storage.publish(
                    key,
                    StoredObject(
                        body=body,
                        content_type=mime,
                        version="generated",
                    ),
                )
                published[file_format] = {
                    "body": body,
                    "mime": mime,
                    "hash": digest,
                    "key": key,
                    "version": version,
                }

            async with self.session.begin():
                report, test_session = await self.scoped_report(
                    actor,
                    report_id,
                    "report:generate",
                    lock=True,
                )
                generation = await self.repo.generation(
                    generation_id,
                    lock=True,
                )
                if (
                    generation is None
                    or generation.report_id != report.id
                    or generation.generation_status != "GENERATING"
                    or report.report_status != "UNISSUED"
                    or test_session.workflow_status != "APPROVED"
                ):
                    raise AppError(
                        409,
                        "REPORT_GENERATION_FAILED",
                        "Report generation state changed while rendering",
                    )

                if content_hash(generation.report_context_snapshot) != generation.context_hash:
                    raise AppError(
                        409,
                        "REPORT_GENERATION_FAILED",
                        "Persisted report context hash is invalid",
                    )

                files = []
                base_name = (
                    "R76_" + report.report_number.replace("-", "_") + f"_Rev{report.revision_no}"
                )
                for file_format in ("pdf", "docx"):
                    item = published[file_format]
                    attachment = Attachment(
                        id=uuid4(),
                        laboratory_id=laboratory_id,
                        attachment_type="REPORT",
                        file_name=f"{base_name}.{file_format}",
                        content_type=item["mime"],
                        file_size=len(item["body"]),
                        storage_provider=self.storage.provider,
                        storage_key=item["key"],
                        object_version=item["version"],
                        sha256=item["hash"],
                        uploaded_by=actor.user_id,
                        metadata_json={
                            "schema_version": 1,
                            "report_id": str(report.id),
                            "report_generation_id": str(generation.id),
                            "report_number": report.report_number,
                            "revision_no": report.revision_no,
                            "format": file_format.upper(),
                        },
                    )
                    self.repo.add(attachment)
                    await self.repo.flush()
                    report_file = ReportFile(
                        id=uuid4(),
                        report_generation_id=generation.id,
                        format=file_format.upper(),
                        attachment_id=attachment.id,
                        file_hash=item["hash"],
                    )
                    self.repo.add(report_file)
                    files.append(report_file)

                await self.repo.flush()
                hashes = {
                    file_format: published[file_format]["hash"] for file_format in ("pdf", "docx")
                }
                generation.report_hash = report_hash(
                    generation.context_hash,
                    hashes,
                )
                generation.generation_status = "READY"
                generation.completed_at = datetime.now(UTC)
                await self.repo.flush()
                await self.session.refresh(report)
                await self.session.refresh(generation)
                for row in files:
                    await self.session.refresh(row)

                body = generation_response(report, generation, files)
                self.audit.record(
                    "report.generation_ready",
                    actor.user_id,
                    "report_generations",
                    generation.id,
                    lab=laboratory_id,
                    after={
                        "report_id": str(report.id),
                        "attempt_no": generation.attempt_no,
                        "context_hash": generation.context_hash,
                        "report_hash": generation.report_hash,
                        "file_hashes": hashes,
                    },
                    source=generation.source_regulatory_revision,
                    target=generation.source_regulatory_revision,
                )
                await self.idempotency.complete(
                    reservation.id,
                    actor.user_id,
                    str(laboratory_id),
                    201,
                    body,
                    {
                        "report_id": str(report.id),
                        "generation_id": str(generation.id),
                    },
                )
                return body
        except Exception as exc:
            code = exc.code if isinstance(exc, AppError) else "REPORT_GENERATION_FAILED"
            async with self.session.begin():
                report = await self.repo.report(report_id)
                generation = await self.repo.generation(
                    generation_id,
                    lock=True,
                )
                files = await self.repo.files(generation_id) if generation is not None else []
                if generation is not None and generation.generation_status == "GENERATING":
                    generation.generation_status = "FAILED"
                    generation.error_code = code
                    generation.completed_at = datetime.now(UTC)
                    await self.repo.flush()
                if report is None or generation is None:
                    raise
                body = generation_response(report, generation, files)
                self.audit.record(
                    "report.generation_failed",
                    actor.user_id,
                    "report_generations",
                    generation.id,
                    lab=laboratory_id,
                    after={
                        "report_id": str(report.id),
                        "attempt_no": generation.attempt_no,
                        "error_code": generation.error_code,
                    },
                    source=generation.source_regulatory_revision,
                    target=generation.source_regulatory_revision,
                )
                await self.idempotency.complete(
                    reservation.id,
                    actor.user_id,
                    str(laboratory_id),
                    201,
                    body,
                    {
                        "report_id": str(report.id),
                        "generation_id": str(generation.id),
                    },
                )
                return body

    async def generate(self, actor, identifier, match, key, data):
        async with self.session.begin():
            test_session = await self.scoped_session(
                actor,
                identifier,
                "report:generate",
            )
            laboratory_id = test_session.laboratory_id

        async def authorize():
            await self.scoped_session(
                actor,
                identifier,
                "report:generate",
            )

        reservation = await self._generation_reservation(
            actor,
            identifier,
            laboratory_id,
            "report.generate",
            key,
            {
                "test_session_id": str(identifier),
                **data.model_dump(mode="json"),
            },
            authorize,
        )
        if reservation.replay:
            return reservation.response_body

        async with self.session.begin():
            test_session = await self.scoped_session(
                actor,
                identifier,
                "report:generate",
                lock=True,
            )
            require_match(match, etag(test_session.lock_version))
            if await self.repo.report_for_session(test_session.id):
                raise AppError(
                    409,
                    "REPORT_CHAIN_CONFLICT",
                    "This approved session revision already owns a report",
                )
            await self._validate_intended_issuer(
                data.intended_issuer_id,
                test_session.laboratory_id,
            )
            snapshot = await self._approved_snapshot(test_session)
            report_number = await self.repo.next_number(data.planned_issue_date.year)
            report_id = uuid4()
            report = Report(
                id=report_id,
                test_session_id=test_session.id,
                report_number=report_number,
                revision_no=1,
                root_report_id=report_id,
                supersedes_report_id=None,
                revision_reason=None,
                report_status="UNISSUED",
                created_by=actor.user_id,
            )
            context = official_context(
                snapshot.snapshot_json,
                report_number=report_number,
                revision_no=1,
                intended_issuer_id=str(data.intended_issuer_id),
                planned_issue_date=data.planned_issue_date.isoformat(),
                source_regulatory_revision=test_session.regulatory_revision,
            )
            generation = ReportGeneration(
                id=uuid4(),
                report_id=report.id,
                attempt_no=1,
                generation_status="GENERATING",
                report_context_snapshot=context,
                context_schema_version=1,
                context_hash=content_hash(context),
                source_regulatory_revision=test_session.regulatory_revision,
                intended_issuer_id=data.intended_issuer_id,
                planned_issue_date=data.planned_issue_date,
                template_version=TEMPLATE_VERSION,
                renderer_manifest=renderer_manifest(),
            )
            self.repo.add(report)
            self.repo.add(generation)
            await self.repo.flush()
            self.audit.record(
                "report.generation_started",
                actor.user_id,
                "report_generations",
                generation.id,
                lab=test_session.laboratory_id,
                after={
                    "report_id": str(report.id),
                    "report_number": report.report_number,
                    "revision_no": 1,
                    "attempt_no": 1,
                    "context_hash": generation.context_hash,
                },
                source=test_session.regulatory_revision,
                target=test_session.regulatory_revision,
            )

        return await self._render_official_generation(
            actor,
            report.id,
            generation.id,
            laboratory_id,
            context,
            reservation,
        )

    async def regenerate(self, actor, identifier, match, key, data):
        async with self.session.begin():
            report, test_session = await self.scoped_report(
                actor,
                identifier,
                "report:generate",
            )
            laboratory_id = test_session.laboratory_id

        async def authorize():
            await self.scoped_report(
                actor,
                identifier,
                "report:generate",
            )

        reservation = await self._generation_reservation(
            actor,
            identifier,
            laboratory_id,
            "report.regenerate",
            key,
            {
                "report_id": str(identifier),
                **data.model_dump(mode="json"),
            },
            authorize,
        )
        if reservation.replay:
            return reservation.response_body

        async with self.session.begin():
            report, test_session = await self.scoped_report(
                actor,
                identifier,
                "report:generate",
                lock=True,
            )
            require_match(match, etag(report.lock_version))
            if report.report_status != "UNISSUED":
                raise AppError(
                    409,
                    "REPORT_ALREADY_ISSUED",
                    "Issued or superseded reports cannot be regenerated",
                )
            await self._validate_intended_issuer(
                data.intended_issuer_id,
                test_session.laboratory_id,
            )
            snapshot = await self._approved_snapshot(test_session)
            attempt = await self.repo.next_attempt(report.id)
            context = official_context(
                snapshot.snapshot_json,
                report_number=report.report_number,
                revision_no=report.revision_no,
                intended_issuer_id=str(data.intended_issuer_id),
                planned_issue_date=data.planned_issue_date.isoformat(),
                source_regulatory_revision=test_session.regulatory_revision,
            )
            generation = ReportGeneration(
                id=uuid4(),
                report_id=report.id,
                attempt_no=attempt,
                generation_status="GENERATING",
                report_context_snapshot=context,
                context_schema_version=1,
                context_hash=content_hash(context),
                source_regulatory_revision=test_session.regulatory_revision,
                intended_issuer_id=data.intended_issuer_id,
                planned_issue_date=data.planned_issue_date,
                template_version=TEMPLATE_VERSION,
                renderer_manifest=renderer_manifest(),
            )
            self.repo.add(generation)
            report.lock_version += 1
            await self.repo.flush()
            self.audit.record(
                "report.regeneration_started",
                actor.user_id,
                "report_generations",
                generation.id,
                lab=test_session.laboratory_id,
                after={
                    "report_id": str(report.id),
                    "attempt_no": attempt,
                    "context_hash": generation.context_hash,
                },
                source=test_session.regulatory_revision,
                target=test_session.regulatory_revision,
            )

        return await self._render_official_generation(
            actor,
            report.id,
            generation.id,
            laboratory_id,
            context,
            reservation,
        )

    async def create_revision(
        self,
        actor,
        identifier,
        match,
        key,
        data,
    ):
        async with self.session.begin():
            predecessor, predecessor_session = await self.scoped_report(
                actor,
                identifier,
                "report:create_revision",
            )
            laboratory_id = predecessor_session.laboratory_id

        async def authorize():
            await self.scoped_report(
                actor,
                identifier,
                "report:create_revision",
            )

        reservation = await self._generation_reservation(
            actor,
            identifier,
            laboratory_id,
            "report.create_revision",
            key,
            {
                "predecessor_report_id": str(identifier),
                **data.model_dump(mode="json"),
            },
            authorize,
        )
        if reservation.replay:
            return reservation.response_body

        async with self.session.begin():
            predecessor, predecessor_session = await self.scoped_report(
                actor,
                identifier,
                "report:create_revision",
                lock=True,
            )
            require_match(match, etag(predecessor.lock_version))
            await self.repo.series_lock(predecessor.report_number)
            predecessor = await self.repo.report(
                predecessor.id,
                lock=True,
            )
            current = await self.repo.current_issued(predecessor.report_number)
            if (
                predecessor.report_status != "ISSUED"
                or current is None
                or current.id != predecessor.id
            ):
                raise AppError(
                    409,
                    "REPORT_CHAIN_CONFLICT",
                    "Report revision must start from the current issued report",
                )

            child = await self.scoped_session(
                actor,
                data.test_session_id,
                "report:create_revision",
                lock=True,
            )
            if (
                child.workflow_status != "APPROVED"
                or child.parent_session_id != predecessor_session.id
                or child.root_session_id != predecessor_session.root_session_id
                or child.laboratory_id != predecessor_session.laboratory_id
                or child.instrument_id != predecessor_session.instrument_id
            ):
                raise AppError(
                    409,
                    "REPORT_CHAIN_CONFLICT",
                    "Report revision requires the approved child session lineage",
                )
            if await self.repo.report_for_session(child.id):
                raise AppError(
                    409,
                    "REPORT_CHAIN_CONFLICT",
                    "Child session already owns a report",
                )

            existing = await self.repo.revisions(predecessor.report_number)
            next_revision = predecessor.revision_no + 1
            if any(row.revision_no == next_revision for row in existing):
                raise AppError(
                    409,
                    "REPORT_CHAIN_CONFLICT",
                    "A competing successor report already exists",
                )

            await self._validate_intended_issuer(
                data.intended_issuer_id,
                child.laboratory_id,
            )
            snapshot = await self._approved_snapshot(child)
            report = Report(
                id=uuid4(),
                test_session_id=child.id,
                report_number=predecessor.report_number,
                revision_no=next_revision,
                root_report_id=predecessor.root_report_id,
                supersedes_report_id=predecessor.id,
                revision_reason=data.revision_reason,
                report_status="UNISSUED",
                created_by=actor.user_id,
            )
            context = official_context(
                snapshot.snapshot_json,
                report_number=report.report_number,
                revision_no=report.revision_no,
                intended_issuer_id=str(data.intended_issuer_id),
                planned_issue_date=data.planned_issue_date.isoformat(),
                source_regulatory_revision=child.regulatory_revision,
            )
            generation = ReportGeneration(
                id=uuid4(),
                report_id=report.id,
                attempt_no=1,
                generation_status="GENERATING",
                report_context_snapshot=context,
                context_schema_version=1,
                context_hash=content_hash(context),
                source_regulatory_revision=child.regulatory_revision,
                intended_issuer_id=data.intended_issuer_id,
                planned_issue_date=data.planned_issue_date,
                template_version=TEMPLATE_VERSION,
                renderer_manifest=renderer_manifest(),
            )
            self.repo.add(report)
            self.repo.add(generation)
            await self.repo.flush()
            self.audit.record(
                "report.revision_generation_started",
                actor.user_id,
                "report_generations",
                generation.id,
                lab=child.laboratory_id,
                after={
                    "report_id": str(report.id),
                    "report_number": report.report_number,
                    "revision_no": report.revision_no,
                    "predecessor_report_id": str(predecessor.id),
                    "context_hash": generation.context_hash,
                },
                source=child.regulatory_revision,
                target=child.regulatory_revision,
                reason=data.revision_reason,
            )

        return await self._render_official_generation(
            actor,
            report.id,
            generation.id,
            laboratory_id,
            context,
            reservation,
        )

    async def _issue_reservation(
        self,
        actor,
        identifier,
        key,
        data,
    ):
        async with self.session.begin():
            report, test_session = await self.scoped_report(
                actor,
                identifier,
                "report:issue",
            )
            laboratory_id = test_session.laboratory_id

        if not key:
            raise AppError(
                428,
                "IDEMPOTENCY_KEY_REQUIRED",
                "Idempotency-Key required",
            )

        async def authorize():
            await self.scoped_report(
                actor,
                identifier,
                "report:issue",
            )

        reservation = await self.idempotency.reserve(
            actor.user_id,
            str(laboratory_id),
            "report.issue",
            key,
            {
                "report_id": str(identifier),
                **data.model_dump(mode="json"),
            },
            authorize,
        )
        return laboratory_id, reservation

    async def issue(self, actor, identifier, match, key, data):
        laboratory_id, reservation = await self._issue_reservation(
            actor,
            identifier,
            key,
            data,
        )
        if reservation.replay:
            return reservation.response_body

        async with self.session.begin():
            report, test_session = await self.scoped_report(
                actor,
                identifier,
                "report:issue",
            )
            generation = await self.repo.generation(data.generation_id)
            if (
                report.report_status != "UNISSUED"
                or generation is None
                or generation.report_id != report.id
                or generation.generation_status != "READY"
            ):
                raise AppError(
                    409,
                    "REPORT_GENERATION_FAILED",
                    "Issue requires a READY generation of this unissued report",
                )
            files = await self.repo.files(generation.id)
            if {row.format for row in files} != {"PDF", "DOCX"}:
                raise AppError(
                    409,
                    "REPORT_GENERATION_FAILED",
                    "Issue requires both PDF and DOCX",
                )

            file_records = []
            for row in files:
                attachment = await self.repo.attachment(row.attachment_id)
                if (
                    attachment is None
                    or attachment.laboratory_id != test_session.laboratory_id
                    or attachment.attachment_type != "REPORT"
                    or attachment.archived_at is not None
                    or attachment.storage_provider != self.storage.provider
                    or attachment.sha256 != row.file_hash
                ):
                    raise AppError(
                        409,
                        "REPORT_GENERATION_FAILED",
                        "Canonical report file identity is invalid",
                    )
                file_records.append((row, attachment))

        await self.storage.ready()
        for row, attachment in file_records:
            stored = await self.storage.read(
                attachment.storage_key,
                attachment.object_version,
            )
            verify_content(
                stored,
                attachment.file_size,
                attachment.content_type,
                attachment.sha256,
            )
            if hashlib.sha256(stored.body).hexdigest() != row.file_hash:
                raise AppError(
                    409,
                    "REPORT_GENERATION_FAILED",
                    "Canonical report bytes no longer match the stored hash",
                )

        async with self.session.begin():
            report, test_session = await self.scoped_report(
                actor,
                identifier,
                "report:issue",
                lock=True,
            )
            require_match(match, etag(report.lock_version))
            await self.repo.series_lock(report.report_number)
            report = await self.repo.report(report.id, lock=True)
            generation = await self.repo.generation(
                data.generation_id,
                lock=True,
            )
            if (
                report.report_status != "UNISSUED"
                or test_session.workflow_status != "APPROVED"
                or generation is None
                or generation.report_id != report.id
                or generation.generation_status != "READY"
            ):
                raise AppError(
                    409,
                    "REPORT_CHAIN_CONFLICT",
                    "Report or approved session changed before issue",
                )

            snapshot = await self._approved_snapshot(test_session)
            self._reg17_issue_gate(snapshot)
            self._generation_context_integrity(
                report,
                generation,
                snapshot,
            )

            if generation.intended_issuer_id != actor.user_id:
                raise AppError(
                    409,
                    "ISSUE_METADATA_MISMATCH",
                    "Authenticated issuer differs from the generated context",
                )
            today = datetime.now(UTC).date()
            if generation.planned_issue_date != today:
                raise AppError(
                    409,
                    "ISSUE_METADATA_MISMATCH",
                    "Planned issue date must equal the current UTC date",
                    {
                        "planned_issue_date": generation.planned_issue_date.isoformat(),
                        "current_utc_date": today.isoformat(),
                    },
                )

            files = await self.repo.files(generation.id)
            file_hashes = {row.format.lower(): row.file_hash for row in files}
            if set(file_hashes) != {"pdf", "docx"}:
                raise AppError(
                    409,
                    "REPORT_GENERATION_FAILED",
                    "Issue requires both canonical formats",
                )
            final_hash = report_hash(
                generation.context_hash,
                file_hashes,
            )
            if final_hash != generation.report_hash:
                raise AppError(
                    409,
                    "REPORT_GENERATION_FAILED",
                    "Generation integrity manifest does not match files",
                )

            predecessor = None
            if report.revision_no == 1:
                if data.expected_predecessor_id is not None:
                    raise AppError(
                        409,
                        "REPORT_CHAIN_CONFLICT",
                        "Initial report has no predecessor",
                    )
                if await self.repo.current_issued(report.report_number):
                    raise AppError(
                        409,
                        "REPORT_CHAIN_CONFLICT",
                        "Report number already has a current issued revision",
                    )
            else:
                if (
                    data.expected_predecessor_id is None
                    or data.expected_predecessor_id != report.supersedes_report_id
                ):
                    raise AppError(
                        409,
                        "REPORT_CHAIN_CONFLICT",
                        "Expected predecessor does not match this revision",
                    )
                predecessor = await self.repo.current_issued(report.report_number)
                if predecessor is None or predecessor.id != report.supersedes_report_id:
                    raise AppError(
                        409,
                        "REPORT_CHAIN_CONFLICT",
                        "Predecessor is no longer the current issued report",
                    )

            issued_at = datetime.now(UTC)
            manifest = issuance_manifest(
                report_id=str(report.id),
                report_number=report.report_number,
                revision_no=report.revision_no,
                generation_id=str(generation.id),
                context_digest=generation.context_hash,
                file_hashes=file_hashes,
                final_report_hash=final_hash,
                issued_by=str(actor.user_id),
                issued_at=issued_at.isoformat(),
                predecessor_id=(str(predecessor.id) if predecessor is not None else None),
            )

            if predecessor is not None:
                predecessor.report_status = "SUPERSEDED"
                predecessor.lock_version += 1
                await self.repo.flush()

            report.selected_generation_id = generation.id
            report.report_hash = final_hash
            report.issued_at = issued_at
            report.issued_by = actor.user_id
            report.issuance_manifest = manifest
            report.report_status = "ISSUED"
            report.lock_version += 1
            await self.repo.flush()

            test_session.workflow_status = "REPORT_ISSUED"
            test_session.lock_version += 1
            await self.repo.flush()
            await self.session.refresh(report)

            body = report_view(report)
            self.audit.record(
                "report.issued",
                actor.user_id,
                "reports",
                report.id,
                lab=laboratory_id,
                after={
                    "report_number": report.report_number,
                    "revision_no": report.revision_no,
                    "generation_id": str(generation.id),
                    "report_hash": report.report_hash,
                    "issued_at": report.issued_at.isoformat(),
                    "predecessor_id": (str(predecessor.id) if predecessor is not None else None),
                },
                source=generation.source_regulatory_revision,
                target=generation.source_regulatory_revision,
            )
            await self.idempotency.complete(
                reservation.id,
                actor.user_id,
                str(laboratory_id),
                200,
                body,
                {
                    "report_id": str(report.id),
                    "generation_id": str(generation.id),
                },
            )
            return body

    async def listing(self, actor, page, size, **filters):
        async with self.session.begin():
            _, grants = await self.authz.current(actor)
            labs = grants.labs_for("report:read")
            if not labs:
                raise denied()
            laboratory_id = filters.get("laboratory_id")
            if laboratory_id is not None and laboratory_id not in labs:
                raise denied()

            rows, total = await self.repo.search(
                labs,
                page,
                size,
                filters,
            )
            items = []
            for report, test_session, instrument, manufacturer in rows:
                items.append(
                    {
                        "id": report.id,
                        "test_session_id": report.test_session_id,
                        "laboratory_id": test_session.laboratory_id,
                        "instrument_id": test_session.instrument_id,
                        "manufacturer_id": instrument.manufacturer_id,
                        "manufacturer_name": manufacturer.name,
                        "instrument_model_name": instrument.model_name,
                        "instrument_serial_number": instrument.serial_number,
                        "application_number": test_session.application_number,
                        "workflow_status": test_session.workflow_status,
                        "evaluation_status": test_session.evaluation_status,
                        "compliance_outcome": test_session.compliance_outcome,
                        "report_number": report.report_number,
                        "revision_no": report.revision_no,
                        "root_report_id": report.root_report_id,
                        "supersedes_report_id": report.supersedes_report_id,
                        "revision_reason": report.revision_reason,
                        "report_status": report.report_status,
                        "issued_at": report.issued_at,
                        "report_hash": report.report_hash,
                        "created_at": report.created_at,
                        "is_current_issued": report.report_status == "ISSUED",
                        "is_superseded": report.report_status == "SUPERSEDED",
                    }
                )
            return {
                "items": items,
                "page": page,
                "page_size": size,
                "total": total,
            }

    async def detail(self, actor, identifier):
        async with self.session.begin():
            report, _ = await self.scoped_report(
                actor,
                identifier,
                "report:read",
            )
            return report_view(report)

    async def generations(self, actor, identifier):
        async with self.session.begin():
            report, _ = await self.scoped_report(
                actor,
                identifier,
                "report:read",
            )
            return [generation_view(row) for row in await self.repo.generations(report.id)]

    async def revisions(self, actor, identifier, page, size):
        async with self.session.begin():
            report, _ = await self.scoped_report(
                actor,
                identifier,
                "report:read",
            )
            rows, total = await self.repo.revisions_page(
                report.report_number,
                page,
                size,
            )
            return {
                "items": [report_view(row) for row in rows],
                "page": page,
                "page_size": size,
                "total": total,
            }

    async def _candidate_generation(self, report):
        if report.selected_generation_id is not None:
            generation = await self.repo.generation(report.selected_generation_id)
            if generation is not None:
                return generation
        rows = await self.repo.generations(report.id)
        ready = [row for row in rows if row.generation_status == "READY"]
        return ready[-1] if ready else None

    async def files(self, actor, identifier):
        async with self.session.begin():
            report, _ = await self.scoped_report(
                actor,
                identifier,
                "report:read",
            )
            generation = await self._candidate_generation(report)
            if generation is None:
                return []
            return [file_view(row) for row in await self.repo.files(generation.id)]

    async def download(self, actor, identifier, file_format):
        if file_format not in FORMAT_MIME:
            raise AppError(
                422,
                "INVALID_INPUT",
                "Report format must be pdf or docx",
            )
        async with self.session.begin():
            report, test_session = await self.scoped_report(
                actor,
                identifier,
                "report:read",
            )
            generation = await self._candidate_generation(report)
            if generation is None:
                raise AppError(
                    409,
                    "REPORT_GENERATION_FAILED",
                    "No READY report generation is available",
                )
            files = await self.repo.files(generation.id)
            target = next(
                (row for row in files if row.format == file_format.upper()),
                None,
            )
            if target is None:
                raise AppError(
                    409,
                    "REPORT_GENERATION_FAILED",
                    "Requested canonical report format is unavailable",
                )
            attachment = await self.repo.attachment(target.attachment_id)
            if (
                attachment is None
                or attachment.laboratory_id != test_session.laboratory_id
                or attachment.attachment_type != "REPORT"
                or attachment.archived_at is not None
                or attachment.storage_provider != self.storage.provider
                or attachment.sha256 != target.file_hash
            ):
                raise AppError(
                    409,
                    "REPORT_GENERATION_FAILED",
                    "Canonical report file integrity check failed",
                )
            key = attachment.storage_key
            version = attachment.object_version
            metadata = {
                "report_id": str(report.id),
                "generation_id": str(generation.id),
                "report_status": report.report_status,
                "format": file_format,
                "file_name": attachment.file_name,
                "attachment_id": str(attachment.id),
                "sha256": attachment.sha256,
            }

        await self.storage.ready()
        url = await self.storage.presign_download(
            key,
            version,
            self.download_seconds,
        )

        async with self.session.begin():
            report, test_session = await self.scoped_report(
                actor,
                identifier,
                "report:read",
            )
            self.audit.record(
                "report.download_authorized",
                actor.user_id,
                "reports",
                report.id,
                lab=test_session.laboratory_id,
                after={
                    "generation_id": metadata["generation_id"],
                    "format": file_format,
                    "attachment_id": metadata["attachment_id"],
                    "sha256": metadata["sha256"],
                    "report_status": metadata["report_status"],
                },
                source=report.revision_no,
                target=report.revision_no,
            )

        return metadata | {
            "download_url": url,
            "expires_in": self.download_seconds,
        }
