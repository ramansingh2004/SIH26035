"""Bounded Phase 15 correction scope and review invalidation helpers."""

from uuid import uuid4

from sqlalchemy import select

from app.core.errors import AppError
from app.models.review import ApprovalAction, CorrectionRequest

ALLOWED_CORRECTION_FIELDS = {
    "test_sessions": {
        "application_number",
        "notes",
        "evidence",
    },
    "session_test_requirements": {
        "selected_run_id",
    },
    "test_runs": {
        "procedure_context",
        "observations",
        "environment",
        "equipment",
        "evidence",
        "retest",
        "start",
        "evaluate",
        "complete",
    },
    "test_observations": {
        "sequence_no",
        "observation_type",
        "payload_schema_version",
        "payload",
        "evidence",
        "__delete__",
    },
    "environment_readings": {
        "measured_at",
        "temperature_c",
        "relative_humidity_percent",
        "barometric_pressure_hpa",
        "phase",
        "notes",
        "evidence",
        "__delete__",
    },
    "test_run_equipment": {
        "equipment",
        "evidence",
        "__delete__",
    },
    "construction_examinations": {
        "overall_notes",
    },
    "construction_items": {
        "value_schema_version",
        "value_json",
        "examination_state",
        "conformance_result",
        "remarks",
        "evidence",
    },
    "checklist_responses": {
        "response_result",
        "remarks",
        "evidence",
    },
}


async def open_corrections(repo, session_id):
    return list(
        (
            await repo.session.scalars(
                select(CorrectionRequest)
                .where(
                    CorrectionRequest.test_session_id == session_id,
                    CorrectionRequest.correction_status == "OPEN",
                )
                .order_by(
                    CorrectionRequest.requested_at,
                    CorrectionRequest.id,
                )
            )
        ).all()
    )


async def validate_requested_scope(repo, session, requested_scope):
    for target in requested_scope.targets:
        allowed = ALLOWED_CORRECTION_FIELDS.get(target.entity_type)
        if allowed is None:
            raise AppError(
                422,
                "INVALID_CORRECTION_TARGET",
                "Unsupported correction target type",
                {"entity_type": target.entity_type},
            )
        unknown = sorted(set(target.field_paths) - allowed)
        if unknown:
            raise AppError(
                422,
                "INVALID_CORRECTION_FIELD",
                "Correction scope contains unsupported field paths",
                {
                    "entity_type": target.entity_type,
                    "field_paths": unknown,
                },
            )
        owner = await repo.target_session_id(
            target.entity_type,
            target.entity_id,
        )
        if owner != session.id:
            raise AppError(
                404,
                "RESOURCE_NOT_FOUND",
                "Correction target is not part of this session",
            )


def _candidate_matches(target, candidate):
    entity_type, entity_id, fields = candidate
    if target.get("entity_type") != entity_type:
        return False
    if str(target.get("entity_id")) != str(entity_id):
        return False
    permitted = set(target.get("field_paths") or ())
    return set(fields) <= permitted


async def enforce_correction_scope(
    repo,
    session,
    *,
    entity_type,
    entity_id,
    field_paths,
    alternatives=(),
):
    requests = await open_corrections(repo, session.id)
    if not requests:
        return

    if len(requests) != 1:
        raise AppError(
            409,
            "CORRECTION_STATE_CONFLICT",
            "Exactly one open correction request must govern edits",
        )
    request = requests[0]
    if request.target_workflow_status != session.workflow_status:
        raise AppError(
            409,
            "CORRECTION_STATE_CONFLICT",
            "Session workflow does not match the open correction request",
        )

    candidates = [
        (entity_type, entity_id, tuple(field_paths)),
        *alternatives,
    ]
    targets = request.requested_scope_json.get("targets") or []
    if any(_candidate_matches(target, candidate) for target in targets for candidate in candidates):
        return

    raise AppError(
        409,
        "CORRECTION_SCOPE_VIOLATION",
        "Mutation is outside the reviewer-authorized correction scope",
        {
            "entity_type": entity_type,
            "entity_id": str(entity_id),
            "field_paths": sorted(set(field_paths)),
            "correction_request_id": str(request.id),
        },
    )


async def invalidate_technical_approvals(
    repo,
    actor,
    session,
    *,
    reason,
    scope,
    audit=None,
):
    actions = list(
        (
            await repo.session.scalars(
                select(ApprovalAction)
                .where(ApprovalAction.test_session_id == session.id)
                .order_by(
                    ApprovalAction.created_at,
                    ApprovalAction.id,
                )
            )
        ).all()
    )
    invalidated = {
        action.referenced_action_id
        for action in actions
        if action.stage == "TECHNICAL_REVIEW"
        and action.decision == "INVALIDATED"
        and action.referenced_action_id is not None
    }
    approvals = [
        action
        for action in actions
        if action.stage == "TECHNICAL_REVIEW"
        and action.decision == "APPROVED"
        and action.id not in invalidated
        and action.regulatory_revision < session.regulatory_revision
    ]
    created = []
    for approval in approvals:
        action = ApprovalAction(
            id=uuid4(),
            test_session_id=session.id,
            stage="TECHNICAL_REVIEW",
            decision="INVALIDATED",
            actor_id=actor.user_id,
            regulatory_revision=session.regulatory_revision,
            scope_json={
                "schema_version": 1,
                "changed_scope": scope,
            },
            referenced_action_id=approval.id,
            reason=reason,
        )
        repo.add(action)
        created.append(action)
        if audit is not None:
            audit.record(
                "review.invalidated",
                actor.user_id,
                "approval_actions",
                action.id,
                lab=session.laboratory_id,
                source=approval.regulatory_revision,
                target=session.regulatory_revision,
                reason=reason,
                after={
                    "referenced_action_id": str(approval.id),
                    "changed_scope": scope,
                },
            )
    return created
