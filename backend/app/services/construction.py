"""Phase 12 non-numeric construction-examination service.

No OIML construction requirement is invented here. Requirements come only
from Section 16 RuleDefinition rows of kind ``construction_item_v1`` that are
pinned to the session ruleset.
"""

from dataclasses import dataclass
from datetime import UTC, datetime
from uuid import uuid4

from pydantic import ValidationError

from app.compliance.aggregation import (
    AggregationChild,
    AggregationInput,
    SessionComplianceAggregator,
)
from app.core.concurrency import etag, require_match
from app.core.errors import AppError, denied, missing
from app.models import RuleDefinition
from app.models.construction import ConstructionExamination, ConstructionItem
from app.models.testing import TestSession
from app.repositories.construction import (
    PREAPPROVAL_WORKFLOWS,
    ConstructionRepository,
)
from app.schemas.construction import (
    ConstructionAssessment,
    ConstructionExaminationPatch,
    ConstructionExaminationView,
    ConstructionItemPatch,
    ConstructionItemView,
    ConstructionRulePolicy,
)
from app.schemas.testing import SessionView
from app.services.audit import AuditService
from app.services.authorization import AuthorizationService

EDITABLE_WORKFLOWS = {"EXAMINATION"}


@dataclass(frozen=True)
class ConstructionEntry:
    item: object
    rule: object
    policy: ConstructionRulePolicy
    evidence_count: int = 0


def construction_policy(rule) -> ConstructionRulePolicy:
    """Parse one strict policy from a stored versioned RuleDefinition."""

    if rule.rule_type != "construction_item_v1":
        raise ValueError("Not a construction_item_v1 rule")
    parameters = rule.configuration.get("parameters", [])
    values = [
        parameter.get("value") for parameter in parameters if parameter.get("name") == "POLICY_JSON"
    ]
    if len(values) != 1 or not isinstance(values[0], str):
        raise ValueError("Construction rule requires exactly one POLICY_JSON")
    try:
        return ConstructionRulePolicy.model_validate_json(values[0])
    except ValidationError as exc:
        raise ValueError("Invalid construction POLICY_JSON") from exc


def _has_required_values(item, policy):
    for key in policy.required_value_keys:
        if key not in item.value_json:
            return False
        value = item.value_json[key]
        if value is None or value == "":
            return False
        if isinstance(value, (list, dict)) and not value:
            return False
    return True


def summarize_construction(
    entries,
    *,
    malformed_rule_ids=(),
    completion_requested=False,
):
    """Return deterministic dossier readiness/outcome without numeric rules."""

    entries = tuple(entries)
    malformed = tuple(sorted(str(value) for value in malformed_rule_ids))
    if not entries and not malformed:
        return {
            "schema_version": 1,
            "evaluation_status": "REVIEW_REQUIRED",
            "compliance_outcome": "UNDETERMINED",
            "catalog_total": 0,
            "required_total": 0,
            "examined": 0,
            "passed": 0,
            "failed": 0,
            "not_applicable": 0,
            "not_examined": 0,
            "review_required": 0,
            "missing_item_keys": [],
            "blockers": ["REG-15:NO_SECTION16_CONSTRUCTION_CATALOG"],
        }

    blockers = [f"{identifier}:INVALID_CONSTRUCTION_POLICY" for identifier in malformed]
    missing = []
    required_total = 0
    examined = 0
    passed = 0
    failed = 0
    not_applicable = 0
    not_examined = 0
    review_required = 0
    known_failure = False

    for entry in entries:
        item = entry.item
        rule = entry.rule
        policy = entry.policy

        if rule.validation_status != "VERIFIED":
            blockers.append(f"{rule.rule_key}:TODO_REGULATORY_VALIDATION")

        if item.examination_state == "REVIEW_REQUIRED":
            review_required += 1
            blockers.append(f"{item.item_key}:EXAMINER_REVIEW_REQUIRED")
        elif item.examination_state == "NOT_EXAMINED":
            not_examined += 1
        else:
            examined += 1

        if item.conformance_result == "PASS":
            passed += 1
        elif item.conformance_result == "FAIL":
            failed += 1
            if policy.required:
                known_failure = True
        elif item.conformance_result == "NOT_APPLICABLE":
            not_applicable += 1

        if not policy.required:
            continue

        required_total += 1
        incomplete = (
            item.examination_state != "EXAMINED"
            or item.conformance_result == "UNDETERMINED"
            or not _has_required_values(item, policy)
            or (policy.evidence_required and entry.evidence_count < 1)
            or (item.conformance_result == "NOT_APPLICABLE" and not policy.allow_not_applicable)
        )
        if incomplete:
            missing.append(item.item_key)

    if entries and required_total == 0:
        blockers.append("REG-15:NO_REQUIRED_SECTION16_ITEMS")

    outcome = "NONCOMPLIANT" if known_failure else "UNDETERMINED"

    if blockers:
        status = "REVIEW_REQUIRED"
        outcome = "UNDETERMINED"
    elif missing:
        any_progress = any(
            entry.item.examination_state != "NOT_EXAMINED"
            or bool(entry.item.value_json)
            or entry.evidence_count > 0
            for entry in entries
        )
        status = (
            "INCOMPLETE"
            if completion_requested
            else "IN_PROGRESS"
            if any_progress
            else "NOT_STARTED"
        )
    elif completion_requested:
        status = "COMPLETE"
        outcome = "NONCOMPLIANT" if known_failure else "COMPLIANT"
    else:
        status = "IN_PROGRESS"

    return {
        "schema_version": 1,
        "evaluation_status": status,
        "compliance_outcome": outcome,
        "catalog_total": len(entries) + len(malformed),
        "required_total": required_total,
        "examined": examined,
        "passed": passed,
        "failed": failed,
        "not_applicable": not_applicable,
        "not_examined": not_examined,
        "review_required": review_required,
        "missing_item_keys": sorted(set(missing)),
        "blockers": sorted(set(blockers)),
    }


def examination_view(row):
    return ConstructionExaminationView.model_validate(row).model_dump(mode="json")


def item_view(row):
    return ConstructionItemView.model_validate(row).model_dump(mode="json")


class ConstructionService:
    def __init__(self, session, request_context):
        self.session = session
        self.repo = ConstructionRepository(session)
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
                "Construction mutation requires EXAMINATION workflow",
            )

    async def _entries(self, session, examination, *, lock=False):
        rules = await self.repo.construction_rules(session.rule_set_id)
        rule_by_id = {rule.id: rule for rule in rules}
        items = await self.repo.items(examination.id, lock=lock)
        counts = await self.repo.evidence_counts([item.id for item in items])
        entries = []
        malformed = []
        for item in items:
            rule = rule_by_id.get(item.requirement_rule_id)
            if rule is None:
                malformed.append(item.requirement_rule_id)
                continue
            try:
                policy = construction_policy(rule)
            except ValueError:
                malformed.append(rule.id)
                continue
            entries.append(
                ConstructionEntry(
                    item=item,
                    rule=rule,
                    policy=policy,
                    evidence_count=counts.get(item.id, 0),
                )
            )
        return entries, malformed

    async def _refresh(
        self,
        session,
        examination,
        *,
        completion_requested=False,
    ):
        entries, malformed = await self._entries(
            session,
            examination,
            lock=False,
        )
        summary = summarize_construction(
            entries,
            malformed_rule_ids=malformed,
            completion_requested=completion_requested,
        )
        examination.summary_json = summary
        examination.evaluation_status = summary["evaluation_status"]
        examination.compliance_outcome = summary["compliance_outcome"]
        await self._aggregate(session, examination)
        return summary

    async def _aggregate(self, session, examination):
        sections = await self.repo.sections(session.id)
        section16 = next(
            (section for section in sections if section.section_number == 16),
            None,
        )
        if section16 is not None:
            section16.evaluation_status = examination.evaluation_status
            section16.compliance_outcome = examination.compliance_outcome
            section16.summary_json = examination.summary_json
            section16.lock_version += 1

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

    async def _initialize_locked(self, session):
        examination = await self.repo.examination(
            session.id,
            lock=True,
        )
        created = False
        if examination is None:
            examination = ConstructionExamination(
                id=uuid4(),
                test_session_id=session.id,
                summary_json={},
            )
            self.repo.add(examination)
            await self.repo.flush()
            created = True

        existing = {
            item.item_key: item
            for item in await self.repo.items(
                examination.id,
                lock=True,
            )
        }
        malformed = []
        added = 0

        for rule in await self.repo.construction_rules(session.rule_set_id):
            try:
                policy = construction_policy(rule)
            except ValueError:
                malformed.append(rule.id)
                continue

            current = existing.get(policy.item_key)
            if current is not None:
                if (
                    current.requirement_rule_id != rule.id
                    or current.category != policy.category
                    or current.sort_order != policy.sort_order
                    or current.description_snapshot != rule.description
                ):
                    raise AppError(
                        409,
                        "CONSTRUCTION_SNAPSHOT_CONFLICT",
                        "Existing construction requirement snapshot differs from the pinned rule",
                    )
                continue

            item = ConstructionItem(
                id=uuid4(),
                construction_examination_id=examination.id,
                requirement_rule_id=rule.id,
                category=policy.category,
                item_key=policy.item_key,
                description_snapshot=rule.description,
                value_json={},
                examination_state="NOT_EXAMINED",
                conformance_result="UNDETERMINED",
                sort_order=policy.sort_order,
            )
            self.repo.add(item)
            existing[item.item_key] = item
            added += 1

        await self.repo.flush()
        summary = await self._refresh(session, examination)
        if malformed:
            blockers = set(summary["blockers"])
            blockers.update(f"{identifier}:INVALID_CONSTRUCTION_POLICY" for identifier in malformed)
            summary["blockers"] = sorted(blockers)
            summary["evaluation_status"] = "REVIEW_REQUIRED"
            summary["compliance_outcome"] = "UNDETERMINED"
            summary["catalog_total"] += len(malformed)
            examination.summary_json = summary
            examination.evaluation_status = "REVIEW_REQUIRED"
            examination.compliance_outcome = "UNDETERMINED"
            await self._aggregate(session, examination)

        if added and not created:
            examination.lock_version += 1
        await self.repo.flush()
        return examination, added, created

    async def start_examination(self, actor, identifier, match):
        async with self.session.begin():
            session = await self.scoped_session(
                actor,
                identifier,
                "construction:update",
                mutation=True,
            )
            require_match(match, etag(session.lock_version))
            if session.workflow_status != "TESTING":
                raise AppError(
                    409,
                    "INVALID_TRANSITION",
                    "Start examination requires TESTING workflow",
                )
            before = SessionView.model_validate(session).model_dump(mode="json")
            session.workflow_status = "EXAMINATION"
            session.regulatory_revision += 1
            session.lock_version += 1
            examination, _, _ = await self._initialize_locked(session)
            await self._aggregate(session, examination)

            from app.services.checklist import ChecklistService

            checklist = ChecklistService(self.session, self.audit.context)
            await checklist.initialize_locked(actor, session)
            await self.repo.flush()
            self.audit.record(
                "session.start-examination",
                actor.user_id,
                "test_sessions",
                session.id,
                lab=session.laboratory_id,
                before=before,
                after=SessionView.model_validate(session).model_dump(mode="json"),
                source=before["lock_version"],
                target=session.lock_version,
            )
            return SessionView.model_validate(session).model_dump(mode="json")

    async def initialize(self, actor, identifier):
        async with self.session.begin():
            session = await self.scoped_session(
                actor,
                identifier,
                "construction:update",
                mutation=True,
            )
            if session.workflow_status not in PREAPPROVAL_WORKFLOWS:
                raise AppError(
                    409,
                    "WORKFLOW_LOCKED",
                    "Construction dossier cannot be initialized after preapproval",
                )
            examination, added, created = await self._initialize_locked(session)
            if created or added:
                self.audit.record(
                    "construction.initialized",
                    actor.user_id,
                    "construction_examinations",
                    examination.id,
                    lab=session.laboratory_id,
                    after={
                        "test_session_id": str(session.id),
                        "items_added": added,
                    },
                    target=examination.lock_version,
                )
            return examination_view(examination)

    async def initialize_existing(self, actor):
        async with self.session.begin():
            _, grants = await self.authz.current(actor, lock=True)
            labs = grants.labs_for("construction:update")
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
                examination, _, _ = await self._initialize_locked(session)
                results.append(examination_view(examination))
            return results

    async def detail(self, actor, identifier, *, items=False):
        async with self.session.begin():
            session = await self.scoped_session(
                actor,
                identifier,
                "construction:read",
            )
            examination = await self.repo.examination(session.id)
            if examination is None:
                raise missing()
            if items:
                return [item_view(item) for item in await self.repo.items(examination.id)]
            return examination_view(examination)

    async def patch_examination(
        self,
        actor,
        identifier,
        match,
        data: ConstructionExaminationPatch,
    ):
        async with self.session.begin():
            session = await self.scoped_session(
                actor,
                identifier,
                "construction:update",
                mutation=True,
            )
            self.mutable(session)
            examination = await self.repo.examination(
                session.id,
                lock=True,
            )
            if examination is None:
                raise missing()
            require_match(match, etag(examination.lock_version))
            before = examination_view(examination)

            examination.overall_notes = data.overall_notes
            examination.examined_by = None
            examination.examined_at = None
            examination.lock_version += 1
            session.regulatory_revision += 1
            session.lock_version += 1
            await self._refresh(session, examination)
            await self.repo.flush()

            self.audit.record(
                "construction.updated",
                actor.user_id,
                "construction_examinations",
                examination.id,
                lab=session.laboratory_id,
                before=before,
                after=examination_view(examination),
                source=before["lock_version"],
                target=examination.lock_version,
            )
            return examination_view(examination)

    async def patch_item(
        self,
        actor,
        identifier,
        item_id,
        match,
        data: ConstructionItemPatch,
    ):
        async with self.session.begin():
            session = await self.scoped_session(
                actor,
                identifier,
                "construction:update",
                mutation=True,
            )
            self.mutable(session)
            examination = await self.repo.examination(
                session.id,
                lock=True,
            )
            if examination is None:
                raise missing()
            item = await self.repo.get(
                ConstructionItem,
                item_id,
                lock=True,
            )
            if item is None or item.construction_examination_id != examination.id:
                raise missing()
            require_match(match, etag(item.lock_version))

            rule = await self.repo.get(
                RuleDefinition,
                item.requirement_rule_id,
            )
            if rule is None:
                raise AppError(
                    409,
                    "CONSTRUCTION_RULE_MISSING",
                    "Pinned construction rule is unavailable",
                )
            try:
                policy = construction_policy(rule)
            except ValueError:
                raise AppError(
                    409,
                    "CONSTRUCTION_RULE_INVALID",
                    "Pinned construction rule configuration is invalid",
                ) from None

            merged = {
                "value_schema_version": item.value_schema_version,
                "value_json": item.value_json,
                "examination_state": item.examination_state,
                "conformance_result": item.conformance_result,
                "remarks": item.remarks,
            }
            merged.update(data.model_dump(exclude_unset=True))
            assessment = ConstructionAssessment.model_validate(merged)
            if (
                assessment.conformance_result == "NOT_APPLICABLE"
                and not policy.allow_not_applicable
            ):
                raise AppError(
                    422,
                    "CONSTRUCTION_NA_NOT_PERMITTED",
                    "Pinned verified policy does not permit NOT_APPLICABLE for this item",
                )

            before = item_view(item)
            item.value_schema_version = assessment.value_schema_version
            item.value_json = assessment.value_json
            item.examination_state = assessment.examination_state
            item.conformance_result = assessment.conformance_result
            item.remarks = assessment.remarks
            item.lock_version += 1
            examination.examined_by = None
            examination.examined_at = None
            examination.lock_version += 1
            session.regulatory_revision += 1
            session.lock_version += 1
            await self._refresh(session, examination)
            await self.repo.flush()

            self.audit.record(
                "construction.item_updated",
                actor.user_id,
                "construction_items",
                item.id,
                lab=session.laboratory_id,
                before=before,
                after=item_view(item),
                source=before["lock_version"],
                target=item.lock_version,
            )
            return item_view(item)

    async def complete(self, actor, identifier, match):
        async with self.session.begin():
            session = await self.scoped_session(
                actor,
                identifier,
                "construction:complete",
                mutation=True,
            )
            self.mutable(session)
            examination = await self.repo.examination(
                session.id,
                lock=True,
            )
            if examination is None:
                raise missing()
            require_match(match, etag(examination.lock_version))

            summary = await self._refresh(
                session,
                examination,
                completion_requested=True,
            )
            if summary["evaluation_status"] == "REVIEW_REQUIRED":
                raise AppError(
                    409,
                    "CONSTRUCTION_REVIEW_REQUIRED",
                    "Section 16 requirements are not fully verified",
                    {"blockers": summary["blockers"]},
                )
            if summary["evaluation_status"] != "COMPLETE":
                raise AppError(
                    422,
                    "CONSTRUCTION_INCOMPLETE",
                    "Required construction examination data is incomplete",
                    {"missing_item_keys": summary["missing_item_keys"]},
                )

            before = examination_view(examination)
            examination.examined_by = actor.user_id
            examination.examined_at = datetime.now(UTC)
            examination.lock_version += 1
            session.regulatory_revision += 1
            session.lock_version += 1
            await self.repo.flush()

            self.audit.record(
                "construction.completed",
                actor.user_id,
                "construction_examinations",
                examination.id,
                lab=session.laboratory_id,
                before=before,
                after=examination_view(examination),
                source=before["lock_version"],
                target=examination.lock_version,
            )
            return examination_view(examination)

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
        item = await self.repo.get(
            ConstructionItem,
            target.entity_id,
        )
        if item is None:
            raise missing()
        examination = await self.repo.get(
            ConstructionExamination,
            item.construction_examination_id,
        )
        if examination is None:
            raise missing()
        session = await self.repo.get(
            TestSession,
            examination.test_session_id,
        )
        if session is None or session.laboratory_id not in labs:
            raise missing()
        self.mutable(session)

        session = await self.repo.get(
            TestSession,
            session.id,
            lock=True,
        )
        await self.repo.get(
            ConstructionExamination,
            examination.id,
            lock=True,
        )
        item = await self.repo.get(
            ConstructionItem,
            item.id,
            lock=True,
        )
        require_match(match, etag(item.lock_version))
        return item, session, session.laboratory_id

    async def evidence_changed(self, actor, item, session):
        examination = await self.repo.get(
            ConstructionExamination,
            item.construction_examination_id,
            lock=True,
        )
        item = await self.repo.get(
            ConstructionItem,
            item.id,
            lock=True,
        )
        before = item.lock_version
        item.lock_version += 1
        examination.examined_by = None
        examination.examined_at = None
        examination.lock_version += 1
        session.regulatory_revision += 1
        session.lock_version += 1
        await self._refresh(session, examination)
        await self.repo.flush()
        self.audit.record(
            "construction.evidence_changed",
            actor.user_id,
            "construction_items",
            item.id,
            lab=session.laboratory_id,
            source=before,
            target=item.lock_version,
            after={"lock_version": item.lock_version},
        )
