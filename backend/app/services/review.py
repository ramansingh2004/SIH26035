"""Phase 15 technical review and bounded correction workflow."""

from datetime import UTC, datetime
from uuid import uuid4

from app.compliance.canonical import content_hash
from app.compliance.demo import is_demo_ruleset
from app.compliance.ruleset import RuleSet
from app.core.concurrency import etag, require_match
from app.core.errors import AppError, denied, missing
from app.models.review import ApprovalAction, CorrectionRequest, SessionApprovalSnapshot
from app.models.testing import TestRunResult, TestSession
from app.repositories.review import ReviewRepository
from app.schemas.review import (
    ApprovalActionView,
    CorrectionRequestView,
)
from app.schemas.testing import SessionView
from app.services.approval_snapshot import ApprovalSnapshotBuilder
from app.services.audit import AuditService
from app.services.authorization import AuthorizationService
from app.services.idempotency import IdempotencyService
from app.services.review_scope import validate_requested_scope

DETERMINED_OUTCOMES = {"COMPLIANT", "NONCOMPLIANT"}


def session_view(row):
    return SessionView.model_validate(row).model_dump(mode="json")


def approval_view(row):
    return ApprovalActionView.model_validate(row).model_dump(mode="json")


def correction_view(row):
    return CorrectionRequestView.model_validate(row).model_dump(mode="json")


def submission_blockers(
    session,
    *,
    sections,
    requirements,
    runs,
    results,
    open_corrections=(),
):
    blockers = []

    if session.evaluation_status != "COMPLETE":
        blockers.append(f"SESSION_EVALUATION:{session.evaluation_status}")
    if session.compliance_outcome not in DETERMINED_OUTCOMES:
        blockers.append(f"SESSION_OUTCOME:{session.compliance_outcome}")

    if len(sections) != 17 or {row.section_number for row in sections} != set(range(1, 18)):
        blockers.append("SESSION_SECTIONS:INCOMPLETE_CATALOG")

    for section in sections:
        key = f"SECTION_{section.section_number}"
        if section.applicability_status == "REQUIRES_REVIEW":
            blockers.append(f"{key}:APPLICABILITY_REVIEW_REQUIRED")
            continue
        if section.applicability_status == "REQUIRED":
            if section.evaluation_status != "COMPLETE":
                blockers.append(f"{key}:EVALUATION_{section.evaluation_status}")
            elif section.compliance_outcome not in DETERMINED_OUTCOMES:
                blockers.append(f"{key}:OUTCOME_{section.compliance_outcome}")
        elif section.applicability_status == "NOT_APPLICABLE":
            if (
                section.evaluation_status != "COMPLETE"
                or section.compliance_outcome != "NOT_APPLICABLE"
            ):
                blockers.append(f"{key}:INVALID_NOT_APPLICABLE_STATE")

    groups = {
        row.slot_snapshot.get("parent_test_code")
        for row in requirements
        if row.slot_snapshot.get("parent_test_code")
    }
    required_leaf_count = 0
    for requirement in requirements:
        if requirement.applicability_status == "REQUIRES_REVIEW":
            blockers.append(f"{requirement.requirement_key}:APPLICABILITY_REVIEW_REQUIRED")
            continue
        required = requirement.applicability_status == "REQUIRED" or (
            requirement.applicability_status == "OPTIONAL" and requirement.is_elected
        )
        if not required:
            continue
        if requirement.slot_snapshot.get("test_code") in groups:
            continue
        if requirement.slot_snapshot.get("section_number", 0) > 15:
            continue

        required_leaf_count += 1
        run = runs.get(requirement.selected_run_id)
        if run is None:
            blockers.append(f"{requirement.requirement_key}:SELECTED_RUN_REQUIRED")
            continue
        if run.evaluation_status != "COMPLETE":
            blockers.append(f"{requirement.requirement_key}:RUN_{run.evaluation_status}")
            continue
        if run.compliance_outcome not in DETERMINED_OUTCOMES:
            blockers.append(f"{requirement.requirement_key}:RUN_OUTCOME_{run.compliance_outcome}")
            continue
        if run.completed_at is None:
            blockers.append(f"{requirement.requirement_key}:RUN_NOT_COMPLETED")
            continue
        result = results.get(run.current_result_id)
        if (
            result is None
            or result.test_run_id != run.id
            or result.source_input_revision != run.input_revision
            or result.evaluation_status != "COMPLETE"
            or result.compliance_outcome not in DETERMINED_OUTCOMES
        ):
            blockers.append(f"{requirement.requirement_key}:CURRENT_RESULT_REQUIRED")

    dedicated_required = sum(
        section.section_number in {16, 17} and section.applicability_status == "REQUIRED"
        for section in sections
    )
    if required_leaf_count + dedicated_required == 0:
        blockers.append("SESSION:NO_REQUIRED_ASSESSMENT")

    if open_corrections:
        blockers.append("SESSION:OPEN_CORRECTION_REQUEST")

    return sorted(set(blockers))


class ReviewService:
    @staticmethod
    def reject_demo_official(session):
        if is_demo_ruleset(RuleSet.model_validate(session.ruleset_snapshot)):
            raise AppError(
                409,
                "SYNTHETIC_DEMO_OFFICIAL_FORBIDDEN",
                "Synthetic SIH demo sessions cannot enter regulatory review or approval",
            )

    def __init__(self, session, context):
        self.session = session
        self.repo = ReviewRepository(session)
        self.authz = AuthorizationService(self.repo)
        self.audit = AuditService(self.repo, context)
        self.idempotency = IdempotencyService(session)

    async def scoped(
        self,
        actor,
        identifier,
        permission,
        *,
        mutation=False,
    ):
        _, grants = await self.authz.current(actor, lock=mutation)
        labs = grants.labs_for(permission)
        if not labs:
            raise denied()
        row = await self.repo.get(TestSession, identifier)
        if row is None or row.laboratory_id not in labs:
            raise missing()
        if mutation:
            lab = await self.repo.lab(row.laboratory_id, lock=True)
            if lab is None or not lab.is_active:
                raise AppError(
                    409,
                    "LABORATORY_INACTIVE",
                    "Active laboratory required",
                )
            row = await self.repo.get(
                TestSession,
                identifier,
                lock=True,
            )
        return row

    async def readiness(self, session):
        sections = await self.repo.sections(session.id)
        requirements = await self.repo.requirements(session.id)
        run_rows = await self.repo.runs(session.id)
        runs = {row.id: row for row in run_rows}
        results = {}
        for run in run_rows:
            if run.current_result_id is None:
                continue
            result = await self.repo.get(
                TestRunResult,
                run.current_result_id,
            )
            if result is not None:
                results[result.id] = result
        corrections = await self.repo.open_corrections(session.id)
        return submission_blockers(
            session,
            sections=sections,
            requirements=requirements,
            runs=runs,
            results=results,
            open_corrections=corrections,
        )

    async def submit(self, actor, identifier, match):
        async with self.session.begin():
            session = await self.scoped(
                actor,
                identifier,
                "review:submit",
                mutation=True,
            )
            require_match(match, etag(session.lock_version))
            self.reject_demo_official(session)
            if session.workflow_status not in {"TESTING", "EXAMINATION"}:
                raise AppError(
                    409,
                    "INVALID_TRANSITION",
                    "Only TESTING or EXAMINATION can be submitted for review",
                )

            blockers = await self.readiness(session)
            if blockers:
                raise AppError(
                    409,
                    "SESSION_NOT_READY_FOR_REVIEW",
                    "Session does not satisfy technical review submission gates",
                    {"blockers": blockers},
                )

            before = session_view(session)
            action = ApprovalAction(
                id=uuid4(),
                test_session_id=session.id,
                stage="TECHNICAL_REVIEW",
                decision="SUBMITTED",
                actor_id=actor.user_id,
                regulatory_revision=session.regulatory_revision,
                scope_json={
                    "schema_version": 1,
                    "scope": "FULL_SESSION",
                    "regulatory_revision": session.regulatory_revision,
                },
            )
            self.repo.add(action)
            session.workflow_status = "UNDER_REVIEW"
            session.submitted_at = datetime.now(UTC)
            session.lock_version += 1
            await self.repo.flush()

            self.audit.record(
                "review.submitted",
                actor.user_id,
                "test_sessions",
                session.id,
                lab=session.laboratory_id,
                before=before,
                after=session_view(session),
                source=before["lock_version"],
                target=session.lock_version,
            )
            return session_view(session)

    async def history(self, actor, identifier):
        async with self.session.begin():
            session = await self.scoped(
                actor,
                identifier,
                "approval:read",
            )
            return [approval_view(row) for row in await self.repo.approval_actions(session.id)]

    async def _independent_reviewer(self, actor, session):
        authors = await self.repo.observation_authors(session.id)
        if actor.user_id in authors:
            raise AppError(
                409,
                "REVIEW_INDEPENDENCE_REQUIRED",
                "Technical reviewer must differ from every raw-observation author",
                {
                    "reviewer_id": str(actor.user_id),
                    "observation_author_count": len(authors),
                },
            )
        return authors

    async def technical_review(
        self,
        actor,
        identifier,
        match,
        data,
    ):
        async with self.session.begin():
            session = await self.scoped(
                actor,
                identifier,
                "review:perform",
                mutation=True,
            )
            require_match(match, etag(session.lock_version))
            self.reject_demo_official(session)
            if session.workflow_status != "UNDER_REVIEW":
                raise AppError(
                    409,
                    "INVALID_TRANSITION",
                    "Technical review requires UNDER_REVIEW workflow",
                )
            if data.reviewed_regulatory_revision != session.regulatory_revision:
                raise AppError(
                    409,
                    "REVIEW_REVISION_MISMATCH",
                    "Technical review must reference the current regulatory revision",
                )

            submission = await self.repo.current_submission(
                session.id,
                session.regulatory_revision,
            )
            if submission is None:
                raise AppError(
                    409,
                    "REVIEW_SUBMISSION_REQUIRED",
                    "Current regulatory revision has not been submitted",
                )

            await self._independent_reviewer(actor, session)

            if data.decision == "APPROVED":
                blockers = await self.readiness(session)
                if blockers:
                    raise AppError(
                        409,
                        "SESSION_NOT_READY_FOR_REVIEW",
                        "Technical approval requires a complete current record",
                        {"blockers": blockers},
                    )
                if await self.repo.current_technical_approval(
                    session.id,
                    session.regulatory_revision,
                ):
                    raise AppError(
                        409,
                        "REVIEW_ALREADY_APPROVED",
                        "Current regulatory revision already has technical approval",
                    )

            action = ApprovalAction(
                id=uuid4(),
                test_session_id=session.id,
                stage="TECHNICAL_REVIEW",
                decision=data.decision,
                actor_id=actor.user_id,
                regulatory_revision=session.regulatory_revision,
                scope_json={
                    "schema_version": 1,
                    "scope": "FULL_SESSION",
                    "reviewed_regulatory_revision": (data.reviewed_regulatory_revision),
                },
                referenced_action_id=submission.id,
                comment=data.comment,
                reason=data.comment if data.decision == "REJECTED" else None,
            )
            self.repo.add(action)
            if data.decision == "REJECTED":
                session.workflow_status = "REJECTED"
            session.lock_version += 1
            await self.repo.flush()

            self.audit.record(
                "review." + data.decision.lower(),
                actor.user_id,
                "approval_actions",
                action.id,
                lab=session.laboratory_id,
                after=approval_view(action),
                source=session.regulatory_revision,
                target=session.regulatory_revision,
                reason=data.comment,
            )
            return approval_view(action)

    async def return_for_correction(
        self,
        actor,
        identifier,
        match,
        data,
    ):
        async with self.session.begin():
            session = await self.scoped(
                actor,
                identifier,
                "review:return_correction",
                mutation=True,
            )
            require_match(match, etag(session.lock_version))
            if session.workflow_status != "UNDER_REVIEW":
                raise AppError(
                    409,
                    "INVALID_TRANSITION",
                    "Correction return requires UNDER_REVIEW workflow",
                )
            if await self.repo.open_corrections(session.id):
                raise AppError(
                    409,
                    "CORRECTION_ALREADY_OPEN",
                    "Resolve the existing correction request first",
                )

            submission = await self.repo.current_submission(
                session.id,
                session.regulatory_revision,
            )
            if submission is None:
                raise AppError(
                    409,
                    "REVIEW_SUBMISSION_REQUIRED",
                    "Current regulatory revision has not been submitted",
                )

            await self._independent_reviewer(actor, session)
            await validate_requested_scope(
                self.repo,
                session,
                data.requested_scope,
            )

            approval = await self.repo.current_technical_approval(
                session.id,
                session.regulatory_revision,
            )
            reference = approval or submission
            action = ApprovalAction(
                id=uuid4(),
                test_session_id=session.id,
                stage="TECHNICAL_REVIEW",
                decision="RETURNED_FOR_CORRECTION",
                actor_id=actor.user_id,
                regulatory_revision=session.regulatory_revision,
                scope_json={
                    "schema_version": 1,
                    "requested_scope": data.requested_scope.model_dump(mode="json"),
                },
                referenced_action_id=reference.id,
                reason=data.reason,
            )
            self.repo.add(action)
            await self.repo.flush()

            correction = CorrectionRequest(
                id=uuid4(),
                test_session_id=session.id,
                approval_action_id=action.id,
                target_workflow_status=data.target_workflow_status,
                requested_scope_json=data.requested_scope.model_dump(mode="json"),
                reason=data.reason,
                requested_by=actor.user_id,
            )
            self.repo.add(correction)
            session.workflow_status = data.target_workflow_status
            session.lock_version += 1
            await self.repo.flush()

            self.audit.record(
                "review.returned_for_correction",
                actor.user_id,
                "correction_requests",
                correction.id,
                lab=session.laboratory_id,
                after=correction_view(correction),
                source=session.regulatory_revision,
                target=session.regulatory_revision,
                reason=data.reason,
            )
            return correction_view(correction)

    async def reopen(self, actor, identifier, match):
        async with self.session.begin():
            session = await self.scoped(
                actor,
                identifier,
                "session:reopen",
                mutation=True,
            )
            require_match(match, etag(session.lock_version))
            if session.workflow_status not in {"TESTING", "EXAMINATION"}:
                raise AppError(
                    409,
                    "INVALID_TRANSITION",
                    "Reopen requires a returned TESTING/EXAMINATION session",
                )
            requests = await self.repo.open_corrections(
                session.id,
                lock=True,
            )
            if len(requests) != 1 or requests[0].target_workflow_status != session.workflow_status:
                raise AppError(
                    409,
                    "OPEN_CORRECTION_REQUIRED",
                    "Reopen only acknowledges the existing bounded correction request",
                )
            session.lock_version += 1
            await self.repo.flush()
            self.audit.record(
                "session.correction_reopened",
                actor.user_id,
                "test_sessions",
                session.id,
                lab=session.laboratory_id,
                after={
                    "correction_request_id": str(requests[0].id),
                    "workflow_status": session.workflow_status,
                },
                target=session.lock_version,
                reason=requests[0].reason,
            )
            return session_view(session)

    async def corrections(self, actor, identifier):
        async with self.session.begin():
            session = await self.scoped(
                actor,
                identifier,
                "session:read",
            )
            return [correction_view(row) for row in await self.repo.corrections(session.id)]

    async def resolve_correction(
        self,
        actor,
        identifier,
        request_id,
        match,
        data,
    ):
        async with self.session.begin():
            session = await self.scoped(
                actor,
                identifier,
                "session:update",
                mutation=True,
            )
            correction = await self.repo.get(
                CorrectionRequest,
                request_id,
                lock=True,
            )
            if correction is None or correction.test_session_id != session.id:
                raise missing()
            require_match(match, etag(correction.lock_version))
            if correction.correction_status != "OPEN":
                raise AppError(
                    409,
                    "CORRECTION_ALREADY_CLOSED",
                    "Correction request is no longer open",
                )
            if session.workflow_status != correction.target_workflow_status:
                raise AppError(
                    409,
                    "CORRECTION_STATE_CONFLICT",
                    "Session workflow does not match correction target",
                )
            action = await self.repo.get(
                ApprovalAction,
                correction.approval_action_id,
            )
            if action is None or session.regulatory_revision <= action.regulatory_revision:
                raise AppError(
                    409,
                    "CORRECTION_CHANGE_REQUIRED",
                    "A regulatory change within the approved scope is required before resolution",
                )

            correction.correction_status = "RESOLVED"
            correction.resolved_at = datetime.now(UTC)
            correction.lock_version += 1
            session.lock_version += 1
            await self.repo.flush()
            await self.session.refresh(correction)
            after = correction_view(correction)
            self.audit.record(
                "correction.resolved",
                actor.user_id,
                "correction_requests",
                correction.id,
                lab=session.laboratory_id,
                after=after,
                target=correction.lock_version,
                reason=data.resolution_note,
            )
            return after

    async def _independent_approver(self, actor, session):
        authors = await self.repo.observation_authors(session.id)
        if actor.user_id == session.started_by or actor.user_id in authors:
            raise AppError(
                409,
                "APPROVAL_INDEPENDENCE_REQUIRED",
                "Final approving officer must differ "
                "from the session starter and every raw-observation author",
                {
                    "approver_id": str(actor.user_id),
                    "session_started_by": str(session.started_by),
                    "observation_author_count": len(authors),
                },
            )

    async def _approval_reservation(
        self,
        actor,
        identifier,
        key,
    ):
        async with self.session.begin():
            session = await self.scoped(
                actor,
                identifier,
                "approval:finalize",
            )
            laboratory_id = session.laboratory_id

        if not key:
            raise AppError(
                428,
                "IDEMPOTENCY_KEY_REQUIRED",
                "Idempotency-Key required",
            )

        async def authorize():
            await self.scoped(
                actor,
                identifier,
                "approval:finalize",
            )

        reservation = await self.idempotency.reserve(
            actor.user_id,
            str(laboratory_id),
            "session.final_approval",
            key,
            {
                "session_id": str(identifier),
                "decision": "APPROVED",
            },
            authorize,
        )
        return laboratory_id, reservation

    async def approve(
        self,
        actor,
        identifier,
        match,
        key,
    ):
        laboratory_id, reservation = await self._approval_reservation(
            actor,
            identifier,
            key,
        )
        if reservation.replay:
            return reservation.response_body

        async with self.session.begin():
            session = await self.scoped(
                actor,
                identifier,
                "approval:finalize",
                mutation=True,
            )
            require_match(match, etag(session.lock_version))
            self.reject_demo_official(session)
            if session.workflow_status != "UNDER_REVIEW":
                raise AppError(
                    409,
                    "INVALID_TRANSITION",
                    "Final approval requires UNDER_REVIEW workflow",
                )

            blockers = await self.readiness(session)
            if blockers:
                raise AppError(
                    409,
                    "SESSION_NOT_READY_FOR_APPROVAL",
                    "Final approval requires a complete current regulatory record",
                    {"blockers": blockers},
                )

            technical = await self.repo.current_technical_approval(
                session.id,
                session.regulatory_revision,
            )
            if technical is None:
                raise AppError(
                    409,
                    "SESSION_NOT_READY_FOR_APPROVAL",
                    "Current regulatory revision has no valid technical approval",
                )

            await self._independent_approver(actor, session)

            action = ApprovalAction(
                id=uuid4(),
                test_session_id=session.id,
                stage="FINAL_APPROVAL",
                decision="APPROVED",
                actor_id=actor.user_id,
                regulatory_revision=session.regulatory_revision,
                scope_json={
                    "schema_version": 1,
                    "scope": "FULL_SESSION",
                    "technical_approval_action_id": str(technical.id),
                    "compliance_outcome": session.compliance_outcome,
                },
            )
            self.repo.add(action)

            approved_at = datetime.now(UTC)
            before = session_view(session)
            session.workflow_status = "APPROVED"
            session.approved_at = approved_at
            session.completed_at = approved_at
            session.lock_version += 1
            await self.repo.flush()
            await self.session.refresh(action)
            await self.session.refresh(session)

            snapshot_json = await ApprovalSnapshotBuilder(
                self.session,
            ).build(session)
            snapshot = SessionApprovalSnapshot(
                id=uuid4(),
                test_session_id=session.id,
                approval_action_id=action.id,
                regulatory_revision=session.regulatory_revision,
                snapshot_schema_version=1,
                snapshot_json=snapshot_json,
                snapshot_hash=content_hash(snapshot_json),
                captured_by=actor.user_id,
            )
            self.repo.add(snapshot)
            await self.repo.flush()

            after = session_view(session)
            self.audit.record(
                "approval.finalized",
                actor.user_id,
                "session_approval_snapshots",
                snapshot.id,
                lab=session.laboratory_id,
                before=before,
                after={
                    "session": after,
                    "approval_action_id": str(action.id),
                    "technical_approval_action_id": str(technical.id),
                    "snapshot_hash": snapshot.snapshot_hash,
                },
                source=session.regulatory_revision,
                target=session.regulatory_revision,
            )
            await self.idempotency.complete(
                reservation.id,
                actor.user_id,
                str(laboratory_id),
                200,
                after,
                {
                    "session_id": str(session.id),
                    "approval_action_id": str(action.id),
                    "approval_snapshot_id": str(snapshot.id),
                },
            )
            return after

    async def reject_final(
        self,
        actor,
        identifier,
        match,
        data,
    ):
        async with self.session.begin():
            session = await self.scoped(
                actor,
                identifier,
                "approval:finalize",
                mutation=True,
            )
            require_match(match, etag(session.lock_version))
            if session.workflow_status != "UNDER_REVIEW":
                raise AppError(
                    409,
                    "INVALID_TRANSITION",
                    "Officer rejection requires UNDER_REVIEW workflow",
                )

            await self._independent_approver(actor, session)
            technical = await self.repo.current_technical_approval(
                session.id,
                session.regulatory_revision,
            )

            action = ApprovalAction(
                id=uuid4(),
                test_session_id=session.id,
                stage="FINAL_APPROVAL",
                decision="REJECTED",
                actor_id=actor.user_id,
                regulatory_revision=session.regulatory_revision,
                scope_json={
                    "schema_version": 1,
                    "scope": "FULL_SESSION",
                    "technical_approval_action_id": (
                        str(technical.id) if technical is not None else None
                    ),
                },
                reason=data.reason,
            )
            self.repo.add(action)

            before = session_view(session)
            session.workflow_status = "REJECTED"
            session.completed_at = datetime.now(UTC)
            session.lock_version += 1
            await self.repo.flush()
            await self.session.refresh(action)
            await self.session.refresh(session)

            after = session_view(session)
            self.audit.record(
                "approval.rejected",
                actor.user_id,
                "approval_actions",
                action.id,
                lab=session.laboratory_id,
                before=before,
                after={
                    "session": after,
                    "approval_action": approval_view(action),
                },
                source=session.regulatory_revision,
                target=session.regulatory_revision,
                reason=data.reason,
            )
            return after
