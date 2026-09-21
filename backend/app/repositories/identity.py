from datetime import datetime
from uuid import UUID

from sqlalchemy import exists, func, or_, select, text, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import (
    AuditEvent,
    Laboratory,
    Permission,
    RefreshSession,
    Role,
    RolePermission,
    User,
    UserRoleAssignment,
)


class IdentityRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def lock_users(self, *user_ids: UUID):
        # Stable ordering prevents two administrators editing each other from deadlocking.
        await self.session.scalars(
            select(User).where(User.id.in_(set(user_ids))).order_by(User.id).with_for_update()
        )

    async def user(self, user_id: UUID, *, lock: bool = False) -> User | None:
        stmt = select(User).where(User.id == user_id).execution_options(populate_existing=True)
        return await self.session.scalar(stmt.with_for_update() if lock else stmt)

    async def user_by_email(self, email: str) -> User | None:
        return await self.session.scalar(select(User).where(User.email == email).with_for_update())

    async def role(self, code: str) -> Role | None:
        return await self.session.scalar(select(Role).where(Role.code == code))

    async def lab(self, lab_id: UUID, *, lock: bool = False) -> Laboratory | None:
        stmt = (
            select(Laboratory)
            .where(Laboratory.id == lab_id)
            .execution_options(populate_existing=True)
        )
        return await self.session.scalar(stmt.with_for_update() if lock else stmt)

    async def grants(self, user_id: UUID):
        stmt = (
            select(UserRoleAssignment, Role.code, Permission.code)
            .join(Role, Role.id == UserRoleAssignment.role_id)
            .join(RolePermission, RolePermission.role_id == Role.id)
            .join(Permission, Permission.id == RolePermission.permission_id)
            .outerjoin(Laboratory, Laboratory.id == UserRoleAssignment.laboratory_id)
            .where(
                UserRoleAssignment.user_id == user_id,
                UserRoleAssignment.revoked_at.is_(None),
                or_(UserRoleAssignment.scope_type == "GLOBAL", Laboratory.is_active.is_(True)),
            )
        )
        return (await self.session.execute(stmt)).all()

    async def assignments(self, user_id: UUID, labs: set[UUID] | None = None):
        stmt = select(UserRoleAssignment).where(UserRoleAssignment.user_id == user_id)
        if labs is not None:
            stmt = stmt.where(UserRoleAssignment.laboratory_id.in_(labs))
        return list(
            (
                await self.session.scalars(
                    stmt.order_by(UserRoleAssignment.assigned_at, UserRoleAssignment.id)
                )
            ).all()
        )

    async def assignment(self, assignment_id: UUID):
        return await self.session.scalar(
            select(UserRoleAssignment)
            .where(UserRoleAssignment.id == assignment_id)
            .with_for_update()
        )

    async def refresh_by_digest(self, digest: str, *, lock=False):
        stmt = (
            select(RefreshSession)
            .where(RefreshSession.token_digest == digest)
            .execution_options(populate_existing=True)
        )
        return await self.session.scalar(stmt.with_for_update() if lock else stmt)

    async def family(self, user_id: UUID, family_id: UUID | None = None):
        stmt = select(RefreshSession).where(RefreshSession.user_id == user_id)
        if family_id is not None:
            stmt = stmt.where(RefreshSession.family_id == family_id)
        return list(
            (
                await self.session.scalars(
                    stmt.order_by(RefreshSession.created_at, RefreshSession.id).execution_options(
                        populate_existing=True
                    )
                )
            ).all()
        )

    async def family_active(self, user_id: UUID, family_id: UUID, now: datetime):
        stmt = select(
            exists().where(
                RefreshSession.user_id == user_id,
                RefreshSession.family_id == family_id,
                RefreshSession.revoked_at.is_(None),
                RefreshSession.consumed_at.is_(None),
                RefreshSession.expires_at > now,
                RefreshSession.family_expires_at > now,
            )
        )
        return await self.session.scalar(stmt)

    async def revoke(
        self, user_id: UUID, now: datetime, reason: str, family_id: UUID | None = None
    ):
        stmt = update(RefreshSession).where(
            RefreshSession.user_id == user_id, RefreshSession.revoked_at.is_(None)
        )
        if family_id is not None:
            stmt = stmt.where(RefreshSession.family_id == family_id)
        await self.session.execute(stmt.values(revoked_at=now, revocation_reason=reason))

    async def login_rate_lock(self, ip: str):
        await self.session.execute(
            text("SELECT pg_advisory_xact_lock(hashtext(:key))"), {"key": "login:" + ip}
        )

    async def login_attempts(self, ip: str, since: datetime):
        return await self.session.scalar(
            select(func.count())
            .select_from(AuditEvent)
            .where(
                AuditEvent.ip_address == ip,
                AuditEvent.created_at >= since,
                AuditEvent.action.in_(["auth.login_failed", "auth.login"]),
            )
        )

    async def page(self, stmt, page: int, size: int):
        count = await self.session.scalar(
            select(func.count()).select_from(stmt.order_by(None).subquery())
        )
        rows = list((await self.session.scalars(stmt.offset((page - 1) * size).limit(size))).all())
        return rows, count

    async def laboratories(self, labs: set[UUID] | None, page: int, size: int):
        stmt = select(Laboratory)
        if labs is not None:
            stmt = stmt.where(Laboratory.id.in_(labs))
        return await self.page(stmt.order_by(Laboratory.code, Laboratory.id), page, size)

    async def users(
        self, labs, page, size, laboratory_id=None, role=None, active=None, search=None
    ):
        stmt = select(User)
        if labs is not None or laboratory_id or role:
            sub = (
                select(UserRoleAssignment.user_id)
                .join(Role, Role.id == UserRoleAssignment.role_id)
                .where(UserRoleAssignment.revoked_at.is_(None))
            )
            if labs is not None:
                sub = sub.where(UserRoleAssignment.laboratory_id.in_(labs))
            if laboratory_id:
                sub = sub.where(UserRoleAssignment.laboratory_id == laboratory_id)
            if role:
                sub = sub.where(Role.code == role)
            stmt = stmt.where(User.id.in_(sub))
        if active is not None:
            stmt = stmt.where(User.is_active == active)
        if search:
            pattern = (
                "%" + search.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_") + "%"
            )
            stmt = stmt.where(
                or_(
                    User.full_name.ilike(pattern, escape="\\"),
                    User.email.ilike(pattern, escape="\\"),
                )
            )
        return await self.page(stmt.order_by(User.email, User.id), page, size)

    async def roles(self):
        return (
            await self.session.execute(
                select(Role, Permission.code)
                .join(RolePermission, RolePermission.role_id == Role.id)
                .join(Permission, Permission.id == RolePermission.permission_id)
                .order_by(Role.code, Permission.code)
            )
        ).all()

    async def audit_page(
        self,
        labs,
        page,
        size,
        laboratory_id=None,
        entity_type=None,
        entity_id=None,
        since=None,
        until=None,
    ):
        stmt = select(AuditEvent)
        if labs is not None:
            stmt = stmt.where(AuditEvent.laboratory_id.in_(labs))
        if laboratory_id:
            stmt = stmt.where(AuditEvent.laboratory_id == laboratory_id)
        if entity_type:
            stmt = stmt.where(AuditEvent.entity_type == entity_type)
        if entity_id:
            stmt = stmt.where(AuditEvent.entity_id == entity_id)
        if since:
            stmt = stmt.where(AuditEvent.created_at >= since)
        if until:
            stmt = stmt.where(AuditEvent.created_at <= until)
        return await self.page(
            stmt.order_by(AuditEvent.created_at.desc(), AuditEvent.id), page, size
        )

    def add(self, obj):
        self.session.add(obj)

    async def flush(self):
        await self.session.flush()
