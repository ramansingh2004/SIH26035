"""Phase 13 non-numeric, rules-driven checklist service."""

from datetime import UTC, datetime
from uuid import uuid4

from app.compliance.aggregation import (
    AggregationChild,
    AggregationInput,
    SessionComplianceAggregator,
)
from app.compliance.checklist import (
    ChecklistAssessment,
    ChecklistEngine,
    ChecklistRuleInput,
)
from app.compliance.domain import Applicability, ApplicabilityDecision, InstrumentSnapshot
from app.core.concurrency import etag, require_match
from app.core.errors import AppError, denied, missing
from app.models import ChecklistRule
from app.models.checklist import ChecklistResponse
from app.models.testing import TestSession
from app.repositories.checklist import PREAPPROVAL_WORKFLOWS, ChecklistRepository
from app.schemas.checklist import (
    ChecklistResponsePatch,
    ChecklistResponseView,
    ChecklistRowView,
    ChecklistSummary,
)
from app.services.audit import AuditService
from app.services.authorization import AuthorizationService

EDITABLE_WORKFLOWS = {"EXAMINATION"}


def checklist_rule_input(rule) -> ChecklistRuleInput:
    return ChecklistRuleInput(
        rule_key=rule.requirement_key,
        group_code=rule.group_code,
        validation_status=rule.validation_status,
        applicability_expression=rule.applicability_expression,
        evidence_required=rule.evidence_required,
    )


def response_view(response, rule):
    base = ChecklistResponseView.model_validate(response).model_dump(mode="json")
    return ChecklistRowView(
        **base,
        group_code=rule.group_code,
        requirement_key=rule.requirement_key,
        clause_reference=rule.clause_reference,
        display_text=rule.display_text,
        evidence_required=rule.evidence_required,
        validation_status=rule.validation_status,
        sort_order=rule.sort_order,
    ).model_dump(mode="json")


def assessment_for(response, rule, evidence_count=0):
    status = Applicability(response.applicability_status)
    unresolved = (rule.requirement_key,) if status == Applicability.REQUIRES_REVIEW else ()
    decision = ApplicabilityDecision(
        applicability=status,
        reason=response.applicability_reason,
        unresolved_rule_ids=unresolved,
    )
    return ChecklistAssessment(
        rule_key=rule.requirement_key,
        decision=decision,
        validation_status=rule.validation_status,
        evidence_required=rule.evidence_required,
        response_result=response.response_result,
        evidence_count=evidence_count,
    )


class ChecklistService:
    def __init__(self, session, request_context):
        self.session = session
        self.repo = ChecklistRepository(session)
        self.authz = AuthorizationService(self.repo)
        self.audit = AuditService(self.repo, request_context)

    async def scoped_session(
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
            row = await self.repo.get(TestSession, identifier, lock=True)
        return row

    @staticmethod
    def mutable(session):
        if session.workflow_status not in EDITABLE_WORKFLOWS:
            raise AppError(
                409,
                "WORKFLOW_LOCKED",
                "Checklist mutation requires EXAMINATION workflow",
            )

    async def _initialize_locked(self, session):
        instrument = InstrumentSnapshot.model_validate(session.instrument_snapshot)
        rules = await self.repo.checklist_rules(session.rule_set_id)
        existing = {
            response.checklist_rule_id: response
            for response in await self.repo.responses(session.id, lock=True)
        }
        added = 0

        for rule in rules:
            if rule.id in existing:
                continue
            decision = ChecklistEngine.applicability(
                instrument,
                checklist_rule_input(rule),
            )
            applicability = getattr(
                decision.applicability,
                "value",
                decision.applicability,
            )
            response = ChecklistResponse(
                id=uuid4(),
                test_session_id=session.id,
                checklist_rule_id=rule.id,
                applicability_status=applicability,
                applicability_reason=decision.reason,
                response_result=(
                    "NOT_APPLICABLE" if applicability == "NOT_APPLICABLE" else "NOT_EXAMINED"
                ),
                remarks=None,
                examined_by=None,
                examined_at=None,
            )
            self.repo.add(response)
            existing[rule.id] = response
            added += 1

        await self.repo.flush()
        summary = await self._refresh(session)
        return summary, added

    async def _assessments(self, session):
        rules = await self.repo.checklist_rules(session.rule_set_id)
        rule_by_id = {rule.id: rule for rule in rules}
        responses = await self.repo.responses(session.id)
        counts = await self.repo.evidence_counts([row.id for row in responses])

        assessments = []
        missing_rule_ids = []
        response_rule_ids = set()

        for response in responses:
            response_rule_ids.add(response.checklist_rule_id)
            rule = rule_by_id.get(response.checklist_rule_id)
            if rule is None:
                missing_rule_ids.append(str(response.checklist_rule_id))
                continue
            assessments.append(
                assessment_for(
                    response,
                    rule,
                    counts.get(response.id, 0),
                )
            )

        missing_responses = [
            rule.requirement_key for rule in rules if rule.id not in response_rule_ids
        ]
        return assessments, missing_rule_ids, missing_responses

    async def _summary(self, session, *, completion_requested=False):
        assessments, missing_rules, missing_responses = await self._assessments(session)
        summary = ChecklistEngine.summarize(
            assessments,
            completion_requested=completion_requested,
        )
        blockers = set(summary["blockers"])
        blockers.update(f"{identifier}:CHECKLIST_RULE_MISSING" for identifier in missing_rules)
        blockers.update(f"{key}:CHECKLIST_RESPONSE_MISSING" for key in missing_responses)
        if blockers:
            summary["blockers"] = sorted(blockers)
            summary["evaluation_status"] = "REVIEW_REQUIRED"
            summary["compliance_outcome"] = "UNDETERMINED"
        return summary

    async def _aggregate(self, session, summary):
        sections = await self.repo.sections(session.id)
        section17 = next(
            (section for section in sections if section.section_number == 17),
            None,
        )
        if section17 is not None:
            section17.evaluation_status = summary["evaluation_status"]
            section17.compliance_outcome = summary["compliance_outcome"]
            section17.summary_json = summary
            section17.lock_version += 1

        children = []
        for section in sections:
            if section.applicability_status == "REQUIRES_REVIEW" and not section.summary_json:
                continue
            children.append(
                AggregationChild(
                    semantic_key=section.code,
                    applicability=section.applicability_status,
                    evaluation_status=section.evaluation_status,
                    compliance_outcome=section.compliance_outcome,
                )
            )
        if children:
            result = SessionComplianceAggregator.aggregate(
                AggregationInput(children=tuple(children))
            )
            session.evaluation_status = result.evaluation_status
            session.compliance_outcome = result.compliance_outcome

    async def _refresh(self, session, *, completion_requested=False):
        summary = await self._summary(
            session,
            completion_requested=completion_requested,
        )
        await self._aggregate(session, summary)
        return summary

    async def initialize_locked(self, actor, session):
        summary, added = await self._initialize_locked(session)
        if added:
            self.audit.record(
                "checklist.initialized",
                actor.user_id,
                "test_sessions",
                session.id,
                lab=session.laboratory_id,
                after={"responses_added": added},
                target=session.lock_version,
            )
        return summary, added

    async def initialize(self, actor, identifier):
        async with self.session.begin():
            session = await self.scoped_session(
                actor,
                identifier,
                "checklist:update",
                mutation=True,
            )
            if session.workflow_status not in PREAPPROVAL_WORKFLOWS:
                raise AppError(
                    409,
                    "WORKFLOW_LOCKED",
                    "Checklist cannot be initialized after preapproval",
                )
            summary, added = await self.initialize_locked(actor, session)
            return {
                **ChecklistSummary.model_validate(
                    {**summary, "lock_version": session.lock_version}
                ).model_dump(mode="json"),
                "responses_added": added,
            }

    async def initialize_existing(self, actor):
        async with self.session.begin():
            _, grants = await self.authz.current(actor, lock=True)
            labs = grants.labs_for("checklist:update")
            if not labs:
                raise denied()
            sessions = await self.repo.preapproval_sessions(labs)
            results = []
            for session_row in sessions:
                session = await self.repo.get(
                    TestSession,
                    session_row.id,
                    lock=True,
                )
                summary, added = await self._initialize_locked(session)
                results.append(
                    {
                        "session_id": str(session.id),
                        "responses_added": added,
                        "summary": summary,
                    }
                )
            return results

    async def rows(
        self,
        actor,
        identifier,
        *,
        group=None,
        response_result=None,
    ):
        async with self.session.begin():
            session = await self.scoped_session(
                actor,
                identifier,
                "checklist:read",
            )
            rules = await self.repo.checklist_rules(session.rule_set_id)
            rule_by_id = {rule.id: rule for rule in rules}
            responses = await self.repo.responses(session.id)
            result = []
            for response in responses:
                rule = rule_by_id.get(response.checklist_rule_id)
                if rule is None:
                    continue
                if group is not None and rule.group_code != group:
                    continue
                if response_result is not None and response.response_result != response_result:
                    continue
                result.append(response_view(response, rule))
            result.sort(
                key=lambda item: (
                    item["sort_order"],
                    item["requirement_key"],
                    item["id"],
                )
            )
            return result

    async def summary(self, actor, identifier):
        async with self.session.begin():
            session = await self.scoped_session(
                actor,
                identifier,
                "checklist:read",
            )
            section = next(
                (
                    value
                    for value in await self.repo.sections(session.id)
                    if value.section_number == 17
                ),
                None,
            )
            completion_requested = bool(
                section is not None and section.evaluation_status == "COMPLETE"
            )
            summary = await self._summary(
                session,
                completion_requested=completion_requested,
            )
            return ChecklistSummary.model_validate(
                {**summary, "lock_version": session.lock_version}
            ).model_dump(mode="json")

    async def patch(
        self,
        actor,
        identifier,
        rule_id,
        match,
        data: ChecklistResponsePatch,
    ):
        async with self.session.begin():
            session = await self.scoped_session(
                actor,
                identifier,
                "checklist:update",
                mutation=True,
            )
            self.mutable(session)
            response = await self.repo.response(
                session.id,
                rule_id,
                lock=True,
            )
            if response is None:
                raise missing()
            require_match(match, etag(response.lock_version))
            rule = await self.repo.get(ChecklistRule, rule_id)
            if rule is None or rule.rule_set_id != session.rule_set_id:
                raise missing()

            if response.applicability_status != "REQUIRED":
                raise AppError(
                    409,
                    "CHECKLIST_ROW_NOT_EDITABLE",
                    "Only verified applicable checklist rows can be examined",
                )

            before = response_view(response, rule)
            changes = data.model_dump(exclude_unset=True)
            result = changes.get(
                "response_result",
                response.response_result,
            )
            if result == "NOT_APPLICABLE":
                raise AppError(
                    422,
                    "CHECKLIST_NA_NOT_PERMITTED",
                    "NOT_APPLICABLE requires a verified applicability decision",
                )

            if "remarks" in changes:
                response.remarks = changes["remarks"]
            if "response_result" in changes:
                response.response_result = result

            if response.response_result == "NOT_EXAMINED":
                response.examined_by = None
                response.examined_at = None
            else:
                response.examined_by = actor.user_id
                response.examined_at = datetime.now(UTC)

            response.lock_version += 1
            session.regulatory_revision += 1
            session.lock_version += 1
            await self._refresh(session)
            await self.repo.flush()

            self.audit.record(
                "checklist.response_updated",
                actor.user_id,
                "checklist_responses",
                response.id,
                lab=session.laboratory_id,
                before=before,
                after=response_view(response, rule),
                source=before["lock_version"],
                target=response.lock_version,
            )
            return response_view(response, rule)

    async def complete(self, actor, identifier, match):
        async with self.session.begin():
            session = await self.scoped_session(
                actor,
                identifier,
                "checklist:complete",
                mutation=True,
            )
            self.mutable(session)
            require_match(match, etag(session.lock_version))
            summary = await self._refresh(
                session,
                completion_requested=True,
            )
            if summary["evaluation_status"] == "REVIEW_REQUIRED":
                raise AppError(
                    409,
                    "CHECKLIST_REVIEW_REQUIRED",
                    "Section 17 requirements are not fully verified",
                    {"blockers": summary["blockers"]},
                )
            if summary["evaluation_status"] != "COMPLETE":
                raise AppError(
                    422,
                    "CHECKLIST_INCOMPLETE",
                    "Required checklist rows are incomplete",
                    {"missing_rule_keys": summary["missing_rule_keys"]},
                )

            session.regulatory_revision += 1
            session.lock_version += 1
            await self.repo.flush()
            self.audit.record(
                "checklist.completed",
                actor.user_id,
                "test_sessions",
                session.id,
                lab=session.laboratory_id,
                after=summary,
                target=session.lock_version,
            )
            return ChecklistSummary.model_validate(
                {**summary, "lock_version": session.lock_version}
            ).model_dump(mode="json")

    async def evidence_target(
        self,
        actor,
        target,
        permission,
        match,
    ):
        _, grants = await self.authz.current(actor, lock=True)
        labs = grants.labs_for(permission)
        if not labs:
            raise denied()

        response = await self.repo.get(
            ChecklistResponse,
            target.entity_id,
        )
        if response is None:
            raise missing()
        session = await self.repo.get(
            TestSession,
            response.test_session_id,
        )
        if session is None or session.laboratory_id not in labs:
            raise missing()
        self.mutable(session)

        session = await self.repo.get(
            TestSession,
            session.id,
            lock=True,
        )
        response = await self.repo.get(
            ChecklistResponse,
            response.id,
            lock=True,
        )
        if response.applicability_status != "REQUIRED":
            raise AppError(
                409,
                "CHECKLIST_ROW_NOT_EDITABLE",
                "Evidence can only be linked to applicable checklist rows",
            )
        require_match(match, etag(response.lock_version))
        return response, session, session.laboratory_id

    async def evidence_changed(self, actor, response, session):
        response = await self.repo.get(
            ChecklistResponse,
            response.id,
            lock=True,
        )
        before = response.lock_version
        response.lock_version += 1
        session.regulatory_revision += 1
        session.lock_version += 1
        await self._refresh(session)
        await self.repo.flush()
        self.audit.record(
            "checklist.evidence_changed",
            actor.user_id,
            "checklist_responses",
            response.id,
            lab=session.laboratory_id,
            source=before,
            target=response.lock_version,
            after={"lock_version": response.lock_version},
        )
