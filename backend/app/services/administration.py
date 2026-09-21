import asyncio
from datetime import UTC, datetime
from uuid import uuid4

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.concurrency import etag, require_match
from app.core.errors import AppError, denied, missing
from app.core.permissions import GLOBAL_ADMIN, LAB_PERMISSIONS
from app.core.security import hash_password
from app.models import Laboratory, User, UserRoleAssignment
from app.repositories.identity import IdentityRepository
from app.schemas.identity import AssignmentView, LaboratoryView, UserView
from app.services.audit import AuditService, RequestContext
from app.services.authorization import AuthorizationService, Principal


def view(schema, row):
    return schema.model_validate(row).model_dump(mode="json")


def paged(schema, rows, total, page, size):
    return {
        "items": [view(schema, row) for row in rows],
        "total": total,
        "page": page,
        "page_size": size,
    }


class AdministrationService:
    def __init__(self, session: AsyncSession, context: RequestContext):
        self.session = session
        self.repo = IdentityRepository(session)
        self.authz = AuthorizationService(self.repo)
        self.audit = AuditService(self.repo, context)

    async def laboratories(self, actor: Principal, page, size):
        async with self.session.begin():
            _, grants = await self.authz.current(actor)
            labs = (
                None
                if "laboratory:read" in grants.global_permissions
                else grants.labs_for("laboratory:read")
            )
            if labs == set():
                raise denied()
            rows, total = await self.repo.laboratories(labs, page, size)
            return paged(LaboratoryView, rows, total, page, size)

    async def laboratory(self, actor, lab_id):
        async with self.session.begin():
            _, grants = await self.authz.current(actor)
            grants.require("laboratory:read", lab_id, administrative=True)
            row = await self.repo.lab(lab_id)
            if row is None:
                raise missing()
            return view(LaboratoryView, row)

    async def create_lab(self, actor, data):
        async with self.session.begin():
            _, grants = await self.authz.current(actor, lock=True)
            grants.require("laboratory:create")
            row = Laboratory(id=uuid4(), created_by=actor.user_id, **data.model_dump())
            self.repo.add(row)
            await self.repo.flush()
            result = view(LaboratoryView, row)
            self.audit.record(
                "laboratory.created",
                actor.user_id,
                "laboratories",
                row.id,
                lab=row.id,
                after=result,
                target=1,
            )
            return result

    async def update_lab(self, actor, lab_id, data, match):
        async with self.session.begin():
            _, grants = await self.authz.current(actor, lock=True)
            grants.require("laboratory:update", lab_id, administrative=True)
            row = await self.repo.lab(lab_id, lock=True)
            if row is None:
                raise missing()
            require_match(match, etag(row.lock_version))
            before = view(LaboratoryView, row)
            for name, value in data.model_dump(exclude_unset=True).items():
                setattr(row, name, value)
            row.lock_version += 1
            await self.repo.flush()
            result = view(LaboratoryView, row)
            self.audit.record(
                "laboratory.updated",
                actor.user_id,
                "laboratories",
                row.id,
                lab=row.id,
                before=before,
                after=result,
                source=row.lock_version - 1,
                target=row.lock_version,
            )
            return result

    async def users(self, actor, page, size, **filters):
        async with self.session.begin():
            _, grants = await self.authz.current(actor)
            labs = (
                None if "user:read" in grants.global_permissions else grants.labs_for("user:read")
            )
            if labs == set() or (
                labs is not None
                and filters.get("laboratory_id")
                and filters["laboratory_id"] not in labs
            ):
                raise denied()
            rows, total = await self.repo.users(labs, page, size, **filters)
            return paged(UserView, rows, total, page, size)

    async def _grant(self, actor, target, grants, data):
        grants.require("user:manage_roles", data.laboratory_id, administrative=True)
        if data.laboratory_id is not None:
            lab = await self.repo.lab(data.laboratory_id, lock=True)
            if lab is None or not lab.is_active:
                raise AppError(409, "LABORATORY_INACTIVE", "An active laboratory is required")
        role = await self.repo.role(data.role_code)
        if role is None:
            raise AppError(409, "SEED_REQUIRED", "Seed the permission catalog first")
        assignment = UserRoleAssignment(
            id=uuid4(),
            user_id=target.id,
            role_id=role.id,
            scope_type=data.scope_type,
            laboratory_id=data.laboratory_id,
            assigned_by=actor.user_id,
        )
        self.repo.add(assignment)
        await self.repo.flush()
        result = view(AssignmentView, assignment)
        self.audit.record(
            "role.assigned",
            actor.user_id,
            "user_role_assignments",
            assignment.id,
            lab=data.laboratory_id,
            after=result,
            target=1,
        )
        return result

    async def create_user(self, actor, data):
        async with self.session.begin():
            _, grants = await self.authz.current(actor, lock=True)
            scope = data.initial_assignment.laboratory_id if data.initial_assignment else None
            grants.require("user:create", scope, administrative=True)
            row = User(
                id=uuid4(),
                email=str(data.email),
                full_name=data.full_name,
                created_by=actor.user_id,
                password_hash=await asyncio.to_thread(
                    hash_password, data.password.get_secret_value()
                ),
            )
            self.repo.add(row)
            await self.repo.flush()
            if data.initial_assignment:
                await self._grant(actor, row, grants, data.initial_assignment)
            result = view(UserView, row)
            self.audit.record(
                "user.created", actor.user_id, "users", row.id, lab=scope, after=result, target=1
            )
            return result

    async def update_user(self, actor, target_id, data, match):
        async with self.session.begin():
            await self.repo.lock_users(actor.user_id, target_id)
            _, grants = await self.authz.current(actor)
            await self.authz.require_user_scope(grants, target_id, "user:update", mutation=True)
            if data.is_active is False:
                await self.authz.require_user_scope(
                    grants, target_id, "user:deactivate", mutation=True
                )
            user = await self.repo.user(target_id, lock=True)
            if user is None:
                raise missing()
            require_match(match, etag(user.lock_version))
            before = view(UserView, user)
            for key, value in data.model_dump(exclude_unset=True).items():
                setattr(user, key, value)
            user.lock_version += 1
            if not user.is_active:
                await self.repo.revoke(user.id, datetime.now(UTC), "USER_DISABLED")
            await self.repo.flush()
            result = view(UserView, user)
            self.audit.record(
                "user.updated",
                actor.user_id,
                "users",
                user.id,
                before=before,
                after=result,
                source=user.lock_version - 1,
                target=user.lock_version,
            )
            return result

    async def reset_password(self, actor, target_id, password, match):
        async with self.session.begin():
            await self.repo.lock_users(actor.user_id, target_id)
            _, grants = await self.authz.current(actor)
            await self.authz.require_user_scope(grants, target_id, "user:update", mutation=True)
            user = await self.repo.user(target_id, lock=True)
            if user is None:
                raise missing()
            require_match(match, etag(user.lock_version))
            user.password_hash = await asyncio.to_thread(hash_password, password)
            user.lock_version += 1
            await self.repo.revoke(user.id, datetime.now(UTC), "PASSWORD_RESET")
            self.audit.record(
                "auth.password_reset",
                actor.user_id,
                "users",
                user.id,
                source=user.lock_version - 1,
                target=user.lock_version,
            )

    async def roles(self, actor, page, size):
        async with self.session.begin():
            _, grants = await self.authz.current(actor)
            if "role:read" not in grants.global_permissions and not grants.labs_for("role:read"):
                raise denied()
            grouped = {}
            for role, permission in await self.repo.roles():
                grouped.setdefault(
                    role.code,
                    {
                        "id": str(role.id),
                        "code": role.code,
                        "name": role.name,
                        "global_permissions": [],
                        "laboratory_permissions": [],
                    },
                )
                if role.code == "ADMIN" and permission in GLOBAL_ADMIN:
                    grouped[role.code]["global_permissions"].append(permission)
                if permission in LAB_PERMISSIONS:
                    grouped[role.code]["laboratory_permissions"].append(permission)
            items = list(grouped.values())
            return {
                "items": items[(page - 1) * size : page * size],
                "page": page,
                "page_size": size,
                "total": len(items),
            }

    async def assignments(self, actor, target, page, size):
        async with self.session.begin():
            _, grants = await self.authz.current(actor)
            await self.authz.require_user_scope(grants, target, "user:read")
            labs = (
                None if "user:read" in grants.global_permissions else grants.labs_for("user:read")
            )
            rows = await self.repo.assignments(target, labs)
            return paged(
                AssignmentView, rows[(page - 1) * size : page * size], len(rows), page, size
            )

    async def grant(self, actor, target_id, data, match):
        async with self.session.begin():
            await self.repo.lock_users(actor.user_id, target_id)
            _, grants = await self.authz.current(actor)
            # Global administrators may attach an existing user to any lab; local administrators
            # may only manage users already visible in their scope.
            await self.authz.require_user_scope(grants, target_id, "user:manage_roles")
            target = await self.repo.user(target_id, lock=True)
            if target is None:
                raise missing()
            require_match(match, etag(target.lock_version))
            result = await self._grant(actor, target, grants, data)
            target.lock_version += 1
            return result

    async def revoke_assignment(self, actor, target_id, assignment_id, match, reason):
        async with self.session.begin():
            await self.repo.lock_users(actor.user_id, target_id)
            _, grants = await self.authz.current(actor)
            target = await self.repo.user(target_id, lock=True)
            row = await self.repo.assignment(assignment_id)
            if row is None or target is None or row.user_id != target_id:
                raise missing()
            grants.require("user:manage_roles", row.laboratory_id, administrative=True)
            require_match(match, etag(row.lock_version))
            if row.revoked_at:
                raise AppError(409, "ASSIGNMENT_REVOKED", "Assignment already revoked")
            row.revoked_at, row.revoked_by, row.revocation_reason = (
                datetime.now(UTC),
                actor.user_id,
                reason,
            )
            row.lock_version += 1
            target.lock_version += 1
            self.audit.record(
                "role.revoked",
                actor.user_id,
                "user_role_assignments",
                row.id,
                lab=row.laboratory_id,
                reason=reason,
                source=row.lock_version - 1,
                target=row.lock_version,
            )

    async def audits(self, actor, page, size, **filters):
        async with self.session.begin():
            _, grants = await self.authz.current(actor)
            labs = (
                None if "audit:read" in grants.global_permissions else grants.labs_for("audit:read")
            )
            if labs == set() or (
                labs is not None
                and filters.get("laboratory_id")
                and filters["laboratory_id"] not in labs
            ):
                raise denied()
            rows, total = await self.repo.audit_page(labs, page, size, **filters)
            items = [{c.name: getattr(row, c.name) for c in row.__table__.columns} for row in rows]
            return {"items": items, "page": page, "page_size": size, "total": total}
