"""Phase 2 master lifecycle; no evaluations, workflow or regulatory decisions."""

from uuid import uuid4

from pydantic import ValidationError

from app.core.concurrency import etag, require_match
from app.core.errors import AppError, denied, missing
from app.core.master_data import decimal_text, exact_intervals
from app.models.master_data import Instrument, InstrumentComponent, InstrumentRange, Manufacturer
from app.repositories.identity import IdentityRepository
from app.repositories.master_data import MasterRepository
from app.schemas.master_data import (
    ComponentData,
    ComponentView,
    InstrumentData,
    InstrumentView,
    ManufacturerData,
    ManufacturerView,
    RangeData,
    RangeView,
)
from app.services.administration import paged, view
from app.services.audit import AuditService
from app.services.authorization import AuthorizationService


def invalid(message, details=None):
    return AppError(422, "INVALID_INSTRUMENT_CONFIGURATION", message, details)


def checked(schema, values):
    try:
        return schema.model_validate(values)
    except ValidationError as error:
        raise invalid(
            "Invalid master-data configuration",
            {"fields": [{"location": list(e["loc"]), "type": e["type"]} for e in error.errors()]},
        ) from None


def stored_values(data):
    values = data.model_dump()
    for key in ("address", "metadata_json", "technical_specifications"):
        if key in values:
            values[key] = getattr(data, key).model_dump(mode="json")
    return values


def n_value(data):
    try:
        return exact_intervals(data.max_capacity_g, data.verification_interval_e_g)
    except ValueError as error:
        raise invalid(str(error), {"issue": "EXACT_RATIO_UNREPRESENTABLE"}) from None


def validate_ranges(data, ranges):
    seen = set()
    for item in ranges:
        if item.range_no in seen:
            raise invalid("Duplicate range number")
        seen.add(item.range_no)
        if item.max_capacity_g > data.max_capacity_g:
            raise invalid("Range Max exceeds the instrument's declared Max")
        n_value(item)


class MasterService:
    def __init__(self, session, context):
        self.session = session
        self.repo = MasterRepository(session)
        self.identity = IdentityRepository(session)
        self.authz = AuthorizationService(self.identity)
        self.audit = AuditService(self.identity, context)

    async def _grants(self, actor, *, mutation=False):
        _, grants = await self.authz.current(actor, lock=mutation)
        return grants

    async def _lab(self, lab_id):
        lab = await self.identity.lab(lab_id, lock=True)
        if lab is None or not lab.is_active:
            raise AppError(409, "LABORATORY_INACTIVE", "An active laboratory is required")

    async def _root(self, actor, identifier, permission, *, mutation=False):
        grants = await self._grants(actor, mutation=mutation)
        labs = grants.labs_for(permission)
        if not labs:
            raise denied()
        row = await self.repo.root(self.model, identifier, labs)
        if row is None:
            raise missing()
        if mutation:
            await self._lab(row.laboratory_id)
            row = await self.repo.root(self.model, identifier, labs, lock=True)
        return row

    def _active(self, row):
        active = row.is_active if self.model is Manufacturer else row.instrument_status == "ACTIVE"
        if not active:
            raise AppError(409, "MASTER_ARCHIVED", "Archived master data is read-only")

    def _audit(self, actor, row, action, before, after, reason=None):
        self.audit.record(
            f"{self.kind}.{action}",
            actor.user_id,
            row.__tablename__,
            row.id,
            lab=row.laboratory_id,
            before=before,
            after=after,
            source=before["lock_version"] if before else None,
            target=row.lock_version,
            reason=reason,
        )

    async def listing(self, actor, page, size, **filters):
        async with self.session.begin():
            grants = await self._grants(actor)
            labs = grants.labs_for(f"{self.kind}:read")
            if not labs or (filters.get("laboratory_id") and filters["laboratory_id"] not in labs):
                raise denied()
            rows, total = await self.repo.listing(self.model, labs, page, size, filters)
            return paged(self.output, rows, total, page, size)

    async def detail(self, actor, identifier):
        async with self.session.begin():
            row = await self._root(actor, identifier, f"{self.kind}:read")
            return view(self.output, row)

    async def archive(self, actor, identifier, match, reason):
        async with self.session.begin():
            row = await self._root(actor, identifier, f"{self.kind}:archive", mutation=True)
            require_match(match, etag(row.lock_version))
            self._active(row)
            before = view(self.output, row)
            if self.model is Manufacturer:
                row.is_active = False
            else:
                row.instrument_status = "ARCHIVED"
            row.lock_version += 1
            await self.repo.flush()
            after = view(self.output, row)
            self._audit(actor, row, "archived", before, after, reason)
            return after


class ManufacturerService(MasterService):
    kind, model, output = "manufacturer", Manufacturer, ManufacturerView

    async def create(self, actor, data):
        async with self.session.begin():
            grants = await self._grants(actor, mutation=True)
            grants.require("manufacturer:create", data.laboratory_id)
            await self._lab(data.laboratory_id)
            row = Manufacturer(id=uuid4(), created_by=actor.user_id, **stored_values(data))
            self.repo.add(row)
            await self.repo.flush()
            result = view(self.output, row)
            self._audit(actor, row, "created", None, result)
            return result

    async def update(self, actor, identifier, data, match):
        async with self.session.begin():
            row = await self._root(actor, identifier, "manufacturer:update", mutation=True)
            require_match(match, etag(row.lock_version))
            self._active(row)
            before = view(self.output, row)
            changes = data.model_dump(exclude_unset=True)
            if not changes:
                raise invalid("Supply at least one changed field")
            current = {key: before[key] for key in ManufacturerData.model_fields}
            merged = checked(ManufacturerData, current | changes)
            for key, value in stored_values(merged).items():
                setattr(row, key, value)
            row.lock_version += 1
            await self.repo.flush()
            after = view(self.output, row)
            self._audit(actor, row, "updated", before, after)
            return after


class InstrumentService(MasterService):
    kind, model, output = "instrument", Instrument, InstrumentView
    children = {
        "ranges": (InstrumentRange, RangeData, RangeView, "instrument:manage_ranges"),
        "components": (
            InstrumentComponent,
            ComponentData,
            ComponentView,
            "instrument:manage_components",
        ),
    }

    async def _manufacturer(self, identifier, lab_id):
        row = await self.repo.root(Manufacturer, identifier, {lab_id}, lock=True)
        if row is None:
            raise missing()
        if not row.is_active:
            raise AppError(409, "MANUFACTURER_ARCHIVED", "Choose an active same-lab manufacturer")

    async def create(self, actor, data):
        async with self.session.begin():
            grants = await self._grants(actor, mutation=True)
            grants.require("instrument:create", data.laboratory_id)
            await self._lab(data.laboratory_id)
            await self._manufacturer(data.manufacturer_id, data.laboratory_id)
            row = Instrument(
                id=uuid4(),
                created_by=actor.user_id,
                verification_intervals_n=n_value(data),
                **stored_values(data),
            )
            self.repo.add(row)
            await self.repo.flush()
            result = view(self.output, row)
            self._audit(actor, row, "created", None, result)
            return result

    async def update(self, actor, identifier, data, match):
        async with self.session.begin():
            row = await self._root(actor, identifier, "instrument:update", mutation=True)
            require_match(match, etag(row.lock_version))
            self._active(row)
            before = view(self.output, row)
            changes = data.model_dump(exclude_unset=True)
            if not changes:
                raise invalid("Supply at least one changed field")
            current = {key: before[key] for key in InstrumentData.model_fields}
            merged = checked(InstrumentData, current | changes)
            if merged.manufacturer_id != row.manufacturer_id:
                await self._manufacturer(merged.manufacturer_id, row.laboratory_id)
            ranges = await self.repo.children(InstrumentRange, row.id)
            validate_ranges(merged, ranges)
            row.verification_intervals_n = n_value(merged)
            for key, value in stored_values(merged).items():
                setattr(row, key, value)
            row.lock_version += 1
            await self.repo.flush()
            after = view(self.output, row)
            self._audit(actor, row, "updated", before, after)
            return after

    async def configuration(self, actor, data):
        async with self.session.begin():
            grants = await self._grants(actor)
            grants.require("instrument:create", data.laboratory_id)
            await self._manufacturer(data.manufacturer_id, data.laboratory_id)
            errors = []
            number = None
            try:
                number = decimal_text(n_value(data))
                validate_ranges(data, data.ranges)
            except AppError as error:
                errors.append(
                    {"code": error.code, "message": error.message, "details": error.details}
                )
            warnings = []
            if data.min_capacity_g is None:
                warnings.append("Min is unknown; configuration cannot be considered complete")
            if not data.ranges:
                warnings.append("No ranges supplied; required range completeness is not assessed")
            unknown = [
                key
                for key in type(data.metadata_json).model_fields
                if getattr(data.metadata_json, key) is None
            ]
            if unknown:
                warnings.append(
                    "Unknown feature facts are preserved; applicability has not been assessed"
                )
            return {
                "structural_valid": not errors,
                "verification_intervals_n": number,
                "errors": errors,
                "warnings": warnings,
                "regulatory_validation_status": "TODO_REGULATORY_VALIDATION",
                "unresolved_rule_ids": ["REG-02"],
                "regulatory_validation_performed": False,
            }

    async def list_children(self, actor, identifier, kind, page, size, include_archived=False):
        async with self.session.begin():
            row = await self._root(actor, identifier, "instrument:read")
            model, _, schema, _ = self.children[kind]
            rows = await self.repo.children(model, row.id, include_archived=include_archived)
            return paged(
                schema, rows[(page - 1) * size : page * size], len(rows), page, size
            ), row.lock_version

    async def mutate_child(
        self, actor, identifier, kind, match, *, data=None, child_id=None, reason=None
    ):
        model, input_schema, output_schema, permission = self.children[kind]
        async with self.session.begin():
            parent = await self._root(actor, identifier, permission, mutation=True)
            parent_source_version = parent.lock_version
            before = None
            if child_id is None:
                require_match(match, etag(parent.lock_version))
                self._active(parent)
                merged = data
                row = model(
                    id=uuid4(),
                    instrument_id=parent.id,
                    created_by=actor.user_id,
                    **stored_values(merged),
                )
                self.repo.add(row)
                action = "created"
            else:
                row = await self.repo.child(model, child_id, parent.id, lock=True)
                if row is None:
                    raise missing()
                require_match(match, etag(row.lock_version))
                self._active(parent)
                if not row.is_active:
                    raise AppError(409, "MASTER_ARCHIVED", "Archived children are read-only")
                before = view(output_schema, row)
                action = "updated" if data is not None else "archived"
                if data is not None:
                    changes = data.model_dump(exclude_unset=True)
                    if not changes:
                        raise invalid("Supply at least one changed field")
                    current = {key: before[key] for key in input_schema.model_fields}
                    merged = checked(input_schema, current | changes)
                    for key, value in stored_values(merged).items():
                        setattr(row, key, value)
                else:
                    row.is_active = False
                row.lock_version += 1
            # Validate the entire remaining active range set under the instrument lock.
            # No regulatory count/transition rule is guessed for incomplete master configurations.
            if kind == "ranges":
                with self.session.no_autoflush:
                    ranges = await self.repo.children(InstrumentRange, parent.id)
                current = [r for r in ranges if r.id != row.id and r.is_active]
                if action != "archived":
                    current.append(row)
                validate_ranges(parent, current)
            parent.lock_version += 1
            await self.repo.flush()
            after = view(output_schema, row)
            self.audit.record(
                f"instrument.{kind}.{action}",
                actor.user_id,
                row.__tablename__,
                row.id,
                lab=parent.laboratory_id,
                before=(
                    {**before, "parent_lock_version": parent_source_version} if before else None
                ),
                after={**after, "parent_lock_version": parent.lock_version},
                source=before["lock_version"] if before else None,
                target=row.lock_version,
                reason=reason,
            )
            return after, parent.lock_version

    async def history(self, actor, identifier):
        async with self.session.begin():
            row = await self._root(actor, identifier, "instrument:read")
            return {
                "instrument_id": str(row.id),
                "availability": "NOT_IMPLEMENTED",
                "message": "Evaluation history is unavailable in Phase 2",
                "sessions": None,
                "revisions": None,
                "reports": None,
            }
