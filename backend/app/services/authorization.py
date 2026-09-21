from dataclasses import dataclass
from datetime import UTC, datetime
from uuid import UUID

from app.core.errors import AppError, denied
from app.core.permissions import GLOBAL_ADMIN, LAB_PERMISSIONS
from app.repositories.identity import IdentityRepository


@dataclass(frozen=True)
class Principal:
    user_id: UUID
    family_id: UUID


@dataclass
class Grants:
    global_permissions: set[str]
    laboratories: dict[UUID, set[str]]
    global_roles: set[str]
    laboratory_roles: dict[UUID, set[str]]

    def labs_for(self, permission: str) -> set[UUID]:
        return {lab for lab, permissions in self.laboratories.items() if permission in permissions}

    def require(self, permission: str, lab: UUID | None = None, *, administrative=False):
        allowed = permission in (
            self.global_permissions if lab is None else self.laboratories.get(lab, set())
        )
        if lab is not None and administrative and permission in GLOBAL_ADMIN:
            allowed |= permission in self.global_permissions
        if not allowed:
            raise denied()


class AuthorizationService:
    def __init__(self, repo: IdentityRepository):
        self.repo = repo

    async def current(self, principal: Principal, *, lock=False):
        user = await self.repo.user(principal.user_id, lock=lock)
        if (
            user is None
            or not user.is_active
            or not await self.repo.family_active(user.id, principal.family_id, datetime.now(UTC))
        ):
            raise AppError(401, "AUTHENTICATION_REQUIRED", "Inactive user or revoked session")
        grants = await self.for_user(user.id)
        return user, grants

    async def for_user(self, user_id: UUID) -> Grants:
        result = Grants(set(), {}, set(), {})
        for assignment, role, permission in await self.repo.grants(user_id):
            if assignment.scope_type == "GLOBAL":
                result.global_roles.add(role)
                if permission in GLOBAL_ADMIN:
                    result.global_permissions.add(permission)
            else:
                result.laboratory_roles.setdefault(assignment.laboratory_id, set()).add(role)
                if permission in LAB_PERMISSIONS:
                    result.laboratories.setdefault(assignment.laboratory_id, set()).add(permission)
        return result

    async def require_user_scope(
        self, grants: Grants, target: UUID, permission: str, *, mutation=False
    ):
        if permission in grants.global_permissions:
            return
        labs = grants.labs_for(permission)
        assignments = [a for a in await self.repo.assignments(target) if a.revoked_at is None]
        if not assignments or not any(a.laboratory_id in labs for a in assignments):
            raise denied()
        # Account profile/password/activity is global: a local admin must control ALL its scopes.
        if mutation and any(
            a.scope_type == "GLOBAL" or a.laboratory_id not in labs for a in assignments
        ):
            raise denied()
