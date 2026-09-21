from uuid import uuid4

from sqlalchemy import select, text
from sqlalchemy.dialects.postgresql import insert

from app.core.permissions import ROLE_PERMISSIONS
from app.models import Permission, Role, RolePermission, User, UserRoleAssignment


class ProvisioningRepository:
    def __init__(self, session):
        self.session = session

    async def lock(self):
        await self.session.execute(text("SELECT pg_advisory_xact_lock(26035001)"))

    async def seed(self):
        changed = 0
        for code in sorted(set().union(*ROLE_PERMISSIONS.values())):
            result = await self.session.scalar(
                insert(Permission)
                .values(id=uuid4(), code=code, description=code.replace(":", " / "))
                .on_conflict_do_nothing(index_elements=["code"])
                .returning(Permission.id)
            )
            changed += result is not None
        for code, permissions in ROLE_PERMISSIONS.items():
            inserted = await self.session.scalar(
                insert(Role)
                .values(id=uuid4(), code=code, name=code.replace("_", " ").title())
                .on_conflict_do_nothing(index_elements=["code"])
                .returning(Role.id)
            )
            changed += inserted is not None
            role = await self.session.scalar(select(Role).where(Role.code == code))
            for permission in (
                await self.session.scalars(
                    select(Permission).where(Permission.code.in_(permissions))
                )
            ).all():
                result = await self.session.scalar(
                    insert(RolePermission)
                    .values(role_id=role.id, permission_id=permission.id)
                    .on_conflict_do_nothing()
                    .returning(RolePermission.role_id)
                )
                changed += result is not None
        return changed

    async def has_admin(self):
        return await self.session.scalar(
            select(UserRoleAssignment.id)
            .join(Role, Role.id == UserRoleAssignment.role_id)
            .where(
                Role.code == "ADMIN",
                UserRoleAssignment.scope_type == "GLOBAL",
                UserRoleAssignment.revoked_at.is_(None),
            )
            .limit(1)
        )

    async def create_admin(self, email, name, password_hash):
        user = User(id=uuid4(), email=email, full_name=name, password_hash=password_hash)
        self.session.add(user)
        await self.session.flush()
        role = await self.session.scalar(select(Role).where(Role.code == "ADMIN"))
        self.session.add(
            UserRoleAssignment(
                id=uuid4(),
                user_id=user.id,
                role_id=role.id,
                scope_type="GLOBAL",
                laboratory_id=None,
                assigned_by=user.id,
            )
        )
        return user
