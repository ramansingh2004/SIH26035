"""Trusted artifact registration, inspection and lifecycle gates; no evaluators."""

from datetime import UTC, datetime
from uuid import uuid4

from app.compliance.demo import (
    DEMO_ARTIFACT,
    DEMO_VERSION,
    is_demo_ruleset,
    load_demo_ruleset,
)
from app.compliance.full_demo import (
    FULL_DEMO_ARTIFACT,
    FULL_DEMO_RUN_ARTIFACT,
    FULL_DEMO_RUN_VERSION,
    FULL_DEMO_VERSION,
    full_demo_runtime_schema_map,
    is_full_demo_run_ruleset,
    load_full_demo_ruleset,
    load_full_demo_run_ruleset,
)
from app.compliance.ruleset import RuleSet, load_ruleset
from app.compliance.stage7_activation import (
    VERIFIED_ARTIFACT,
    VERIFIED_VERSION,
    Stage7VerificationError,
    load_verified_ruleset,
)
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


def _load_stage7_verified():
    try:
        return load_verified_ruleset()
    except Stage7VerificationError as exc:
        raise AppError(
            409,
            "RULESET_NOT_VERIFIED",
            "Independent Stage 7 verification package is incomplete or invalid",
            {"blockers": list(exc.blockers)},
        ) from exc


def _trusted_artifact(artifact):
    if artifact == "oiml_r76_2006/candidate-v1":
        return load_ruleset(), None
    if artifact == DEMO_ARTIFACT:
        return load_demo_ruleset(), None
    if artifact == FULL_DEMO_ARTIFACT:
        return load_full_demo_ruleset(), None
    if artifact == FULL_DEMO_RUN_ARTIFACT:
        return load_full_demo_run_ruleset(), None
    if artifact == VERIFIED_ARTIFACT:
        return _load_stage7_verified()
    raise AppError(422, "INVALID_INPUT", "Unknown trusted ruleset artifact")


def _trusted_snapshot(candidate):
    if candidate.metadata.version == DEMO_VERSION and is_demo_ruleset(candidate):
        return load_demo_ruleset(), None
    if candidate.metadata.version == FULL_DEMO_VERSION and is_demo_ruleset(candidate):
        return load_full_demo_ruleset(), None
    if (
        candidate.metadata.version == FULL_DEMO_RUN_VERSION
        and is_demo_ruleset(candidate)
    ):
        return load_full_demo_run_ruleset(), None
    if candidate.metadata.version == VERIFIED_VERSION:
        return _load_stage7_verified()

    trusted = load_ruleset()
    if candidate.metadata.version != trusted.metadata.version:
        raise AppError(
            409,
            "RULESET_ARTIFACT_MISMATCH",
            "Registered artifact version is not a trusted server artifact",
        )
    return trusted, None


def _validation_summary(ruleset, stage7_manifest=None):
    blockers = list(ruleset.activation_blockers())
    summary = {
        "schema_version": 1,
        "structurally_valid": True,
        "authoritative": False,
        "synthetic_demo_only": is_demo_ruleset(ruleset),
        "blockers": (
            ["SYNTHETIC_DEMO_ONLY"]
            if is_demo_ruleset(ruleset)
            else blockers
        ),
    }
    if stage7_manifest is not None:
        summary["stage7_external_verification"] = "VERIFIED"
        summary["stage7_manifest_hash"] = stage7_manifest.manifest_hash
        summary.update(
            {
                item.register_id: item.status
                for item in stage7_manifest.register_signoffs
            }
        )
    return summary


def _runtime_schemas_for(ruleset, stage7_manifest):
    if stage7_manifest is not None:
        return stage7_manifest.runtime_schema_map()
    if is_full_demo_run_ruleset(ruleset):
        return full_demo_runtime_schema_map()
    return {}


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

    async def insert_artifact(
        self,
        actor_id=None,
        artifact="oiml_r76_2006/candidate-v1",
    ):
        ruleset, stage7_manifest = _trusted_artifact(artifact)
        # Server allowlist only; no client paths or arbitrary configuration.
        await self.repo.ruleset_lock()
        existing = await self.repo.ruleset_version(ruleset.metadata)
        if existing:
            if existing.configuration_hash != ruleset.configuration_hash:
                raise AppError(
                    409, "RULESET_VERSION_CONFLICT", "Artifact differs from registered version"
                )
            if stage7_manifest is not None and (
                (existing.validation_summary or {}).get("stage7_manifest_hash")
                != stage7_manifest.manifest_hash
            ):
                raise AppError(
                    409,
                    "RULESET_VERSION_CONFLICT",
                    "External verification manifest differs from registered version",
                )
            return existing
        m = ruleset.metadata
        snapshot = ruleset.snapshot()
        runtime_schemas = _runtime_schemas_for(
            ruleset,
            stage7_manifest,
        )
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
            validation_summary=_validation_summary(
                ruleset,
                stage7_manifest,
            ),
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
                    default_observation_schema_version=(
                        runtime_schemas[test.code].observation_schema_version
                        if test.code in runtime_schemas
                        else "v1"
                        if test.implemented
                        else None
                    ),
                    default_procedure_schema_version=(
                        runtime_schemas[test.code].procedure_schema_version
                        if test.code in runtime_schemas
                        else "v1"
                        if test.implemented
                        else None
                    ),
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
                    applicability_expression=(
                        {"schema_version": 1, "status": item.applicability}
                        if isinstance(item.applicability, str)
                        else item.applicability.model_dump(mode="json")
                    ),
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

    async def register(
        self,
        actor,
        artifact="oiml_r76_2006/candidate-v1",
    ):
        async with self.session.begin():
            await self.allowed(actor, "ruleset:create", True)
            return serialize(await self.insert_artifact(actor.user_id, artifact))

    async def action(self, actor, identifier, action, match):
        async with self.session.begin():
            await self.allowed(actor, "ruleset:" + action, True)
            await self.repo.ruleset_lock()
            row = await self.repo.get(RuleSetRecord, identifier, lock=True)
            if row is None:
                raise missing()
            require_match(match, etag(row.lock_version))
            candidate = RuleSet.model_validate(row.configuration_snapshot)
            # Stored configuration and Stage 7 sign-off package must still
            # match the fixed trusted server artifact before lifecycle actions.
            trusted, stage7_manifest = _trusted_snapshot(candidate)
            manifest_mismatch = (
                stage7_manifest is not None
                and (row.validation_summary or {}).get("stage7_manifest_hash")
                != stage7_manifest.manifest_hash
            )
            if (
                candidate.configuration_hash != row.configuration_hash
                or row.configuration_hash != trusted.configuration_hash
                or manifest_mismatch
            ):
                raise AppError(
                    409, "RULESET_ARTIFACT_MISMATCH", "Registered artifact integrity failed"
                )
            blockers = candidate.activation_blockers()
            before = {"status": row.ruleset_status, "lock_version": row.lock_version}
            if action == "activate":
                if is_demo_ruleset(candidate):
                    raise AppError(
                        409,
                        "SYNTHETIC_DEMO_ACTIVATION_FORBIDDEN",
                        "Synthetic SIH demo rulesets can never be activated",
                    )
                if stage7_manifest is not None and (
                    row.validation_summary or {}).get("authoritative") is not True:
                    raise AppError(
                        409,
                        "RULESET_NOT_VALIDATED",
                        "Verified Stage 7 artifact must pass validation before activation",
                    )
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
                summary = _validation_summary(candidate, stage7_manifest)
                summary["authoritative"] = (
                    not blockers and not is_demo_ruleset(candidate)
                )
                row.validation_summary = summary
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
