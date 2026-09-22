"""Trusted artifact registration, inspection and lifecycle gates; no evaluators."""

from datetime import UTC, datetime
from uuid import uuid4

from app.compliance.ruleset import RuleSet, load_ruleset
from app.core.concurrency import etag, require_match
from app.core.errors import AppError, denied, missing
from app.models import ChecklistRule, RuleDefinition, RuleSetRecord, TestDefinitionRecord
from app.repositories.foundations import FoundationRepository
from app.services.audit import AuditService, RequestContext
from app.services.authorization import AuthorizationService


def serialize(row):
    # Only catalog/equipment-safe columns; never use this on credentials or object URLs.
    import json

    from pydantic_core import to_json

    return json.loads(
        to_json({column.name: getattr(row, column.name) for column in row.__table__.columns})
    )


def provenance(item):
    verification = item.verification
    return dict(
        validation_status=verification.status,
        source_identity=item.source.model_dump(mode="json"),
        source_digest=item.source.digest,
        verified_by=verification.verified_by,
        verified_at=verification.verified_at,
        verification_evidence=verification.evidence,
    )


class RulesetService:
    def __init__(self, session, context):
        self.session = session
        self.repo = FoundationRepository(session)
        self.authz = AuthorizationService(self.repo)
        self.audit = AuditService(self.repo, context)

    async def allowed(self, actor, permission, mutation=False):
        _, grants = await self.authz.current(actor, lock=mutation)
        if permission == "ruleset:read":
            if permission not in grants.global_permissions and not grants.labs_for(permission):
                raise denied()
        else:
            grants.require(permission)

    async def listing(self, actor, page=1, size=20):
        async with self.session.begin():
            await self.allowed(actor, "ruleset:read")
            rows, total = await self.repo.rulesets(page, size)
            return {
                "items": [serialize(row) for row in rows],
                "total": total,
                "page": page,
                "page_size": size,
            }

    async def detail(self, actor, identifier, kind=None):
        async with self.session.begin():
            await self.allowed(actor, "ruleset:read")
            row = await self.repo.get(RuleSetRecord, identifier)
            if row is None:
                raise missing()
            if kind:
                model = TestDefinitionRecord if kind == "tests" else ChecklistRule
                rows = await self.repo.catalog(model, identifier)
                return {"items": [serialize(r) for r in rows], "total": len(rows)}
            return serialize(row)

    async def insert_artifact(self, actor_id=None):
        ruleset = load_ruleset()  # Server allowlist only; no client paths/configuration.
        await self.repo.ruleset_lock()
        existing = await self.repo.ruleset_version(ruleset.metadata)
        if existing:
            if existing.configuration_hash != ruleset.configuration_hash:
                raise AppError(
                    409, "RULESET_VERSION_CONFLICT", "Artifact differs from registered version"
                )
            return existing
        m = ruleset.metadata
        snapshot = ruleset.snapshot()
        row = RuleSetRecord(
            id=uuid4(),
            standard_code=m.standard_code,
            standard_name=m.standard_name,
            standard_parts=snapshot["metadata"]["standard_parts"],
            edition=m.edition,
            version=m.version,
            configuration_hash=ruleset.configuration_hash,
            configuration_snapshot=snapshot,
            supported_test_codes=list(m.supported_test_codes),
            source_reference=m.source_reference,
            validation_summary={
                "schema_version": 1,
                "structurally_valid": True,
                "authoritative": False,
                "blockers": list(ruleset.activation_blockers()),
            },
            created_by=actor_id,
        )
        self.repo.add(row)
        await self.repo.flush()
        for rule in ruleset.rules:
            self.repo.add(
                RuleDefinition(
                    rule_set_id=row.id,
                    rule_key=rule.key,
                    section_no=rule.section,
                    clause_reference=rule.source.clause,
                    rule_type=rule.kind,
                    configuration=rule.model_dump(mode="json"),
                    description=rule.description,
                    **provenance(rule),
                )
            )
        ids = {test.code: uuid4() for test in ruleset.tests}
        for index, test in enumerate(
            sorted(ruleset.tests, key=lambda t: (t.parent is not None, t.section, t.code))
        ):
            self.repo.add(
                TestDefinitionRecord(
                    id=ids[test.code],
                    rule_set_id=row.id,
                    code=test.code,
                    section_number=test.section,
                    parent_definition_id=ids.get(test.parent),
                    name=test.name,
                    category="SUBTEST" if test.parent else "SECTION",
                    subtest_family=test.family,
                    sort_order=index,
                    supports_numeric_evaluation=test.implemented,
                    requires_manual_review=not test.implemented,
                    supported=test.code in m.supported_test_codes,
                    implemented=test.implemented,
                    applicability_metadata={"schema_version": 1, "status": test.applicability},
                    default_observation_schema_version="v1" if test.implemented else None,
                    default_procedure_schema_version="v1" if test.implemented else None,
                    description=(
                        "Deterministic evaluator declared; regulatory gate applies."
                        if test.implemented
                        else "Candidate catalog definition; evaluator not implemented."
                    ),
                    **provenance(test),
                )
            )
            await self.repo.flush()  # Parent rows precede same-ruleset FK children.
        for index, item in enumerate(ruleset.checklist):
            self.repo.add(
                ChecklistRule(
                    rule_set_id=row.id,
                    group_code=item.group,
                    requirement_key=item.key,
                    clause_reference=item.source.clause,
                    display_text=item.text,
                    applicability_expression={"schema_version": 1, "status": item.applicability},
                    evidence_required=item.evidence_required,
                    sort_order=index,
                    **provenance(item),
                )
            )
        await self.repo.flush()
        self.audit.record(
            "ruleset.registered",
            actor_id,
            "rule_sets",
            row.id,
            after={"version": m.version, "hash": row.configuration_hash},
            target=1,
            system=actor_id is None,
        )
        return row

    async def register(self, actor):
        async with self.session.begin():
            await self.allowed(actor, "ruleset:create", True)
            return serialize(await self.insert_artifact(actor.user_id))

    async def action(self, actor, identifier, action, match):
        async with self.session.begin():
            await self.allowed(actor, "ruleset:" + action, True)
            await self.repo.ruleset_lock()
            row = await self.repo.get(RuleSetRecord, identifier, lock=True)
            if row is None:
                raise missing()
            require_match(match, etag(row.lock_version))
            candidate = RuleSet.model_validate(row.configuration_snapshot)
            # Stored configuration must match the trusted versioned artifact, including provenance.
            trusted = load_ruleset()
            if (
                candidate.configuration_hash != row.configuration_hash
                or row.configuration_hash != trusted.configuration_hash
            ):
                raise AppError(
                    409, "RULESET_ARTIFACT_MISMATCH", "Registered artifact integrity failed"
                )
            blockers = candidate.activation_blockers()
            before = {"status": row.ruleset_status, "lock_version": row.lock_version}
            if action == "activate":
                if blockers:
                    raise AppError(
                        409,
                        "RULESET_NOT_VERIFIED",
                        "Regulatory dependencies are unverified or unsupported",
                        {"blockers": blockers},
                    )
                if row.ruleset_status != "DRAFT":
                    raise AppError(409, "RULESET_STATE_CONFLICT", "Only drafts can activate")
                row.ruleset_status = "ACTIVE"
                row.activated_at = datetime.now(UTC)
                row.activated_by = actor.user_id
            elif action == "retire":
                if row.ruleset_status != "ACTIVE":
                    raise AppError(409, "RULESET_STATE_CONFLICT", "Only active rulesets can retire")
                row.ruleset_status = "RETIRED"
            elif action == "validate":
                row.validation_summary = {
                    "schema_version": 1,
                    "structurally_valid": True,
                    "authoritative": not blockers,
                    "blockers": list(blockers),
                }
            row.lock_version += 1
            await self.repo.flush()
            self.audit.record(
                "ruleset." + action,
                actor.user_id,
                "rule_sets",
                row.id,
                before=before,
                after={"status": row.ruleset_status, "lock_version": row.lock_version},
                source=before["lock_version"],
                target=row.lock_version,
            )
            return serialize(row)


async def seed_phase3(session):
    async with session.begin():
        row = await RulesetService(session, RequestContext()).insert_artifact()
        return str(row.id)
