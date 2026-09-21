import asyncio
import hashlib
import secrets
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.concurrency import etag, require_match
from app.core.config import Settings
from app.core.errors import AppError, missing
from app.core.security import (
    DUMMY_HASH,
    access_token,
    decode_access,
    digest,
    hash_password,
    verify_password,
)
from app.models import RefreshSession
from app.repositories.identity import IdentityRepository
from app.schemas.identity import UserView
from app.services.audit import AuditService, RequestContext
from app.services.authorization import AuthorizationService, Principal


@dataclass(frozen=True)
class Tokens:
    access: str
    refresh: str
    expires_in: int
    refresh_max_age: int


def family_etag(rows) -> str:
    content = "|".join(
        f"{r.id}:{r.consumed_at}:{r.revoked_at}:{r.replaced_by_session_id}" for r in rows
    )
    return etag(hashlib.sha256(content.encode()).hexdigest())


class AuthService:
    def __init__(self, session: AsyncSession, settings: Settings, context: RequestContext):
        self.session, self.settings, self.context = session, settings, context
        self.repo = IdentityRepository(session)
        self.audit = AuditService(self.repo, context)
        self.authorization = AuthorizationService(self.repo)

    async def _issue(self, user_id, now, previous=None):
        secret = secrets.token_urlsafe(48)
        family_expiry = (
            previous.family_expires_at
            if previous
            else now + timedelta(days=self.settings.refresh_family_days)
        )
        row = RefreshSession(
            id=uuid4(),
            user_id=user_id,
            family_id=previous.family_id if previous else uuid4(),
            token_digest=digest(secret),
            parent_session_id=previous.id if previous else None,
            created_at=now,
            expires_at=min(now + timedelta(days=self.settings.refresh_token_days), family_expiry),
            family_expires_at=family_expiry,
            client_ip=self.context.ip,
            user_agent=self.context.user_agent,
        )
        self.repo.add(row)
        await self.repo.flush()
        if previous:
            previous.consumed_at = now
            previous.replaced_by_session_id = row.id
        return Tokens(
            access_token(user_id, row.family_id, self.settings),
            secret,
            self.settings.access_token_seconds,
            max(1, int((row.expires_at - now).total_seconds())),
        ), row

    async def login(self, email: str, password: str) -> Tokens:
        failure = None
        result = None
        async with self.session.begin():
            now = datetime.now(UTC)
            ip = self.context.ip or "unknown"
            await self.repo.login_rate_lock(ip)
            attempts = await self.repo.login_attempts(
                ip, now - timedelta(seconds=self.settings.login_window_seconds)
            )
            if attempts >= self.settings.login_limit:
                self.audit.record("auth.login_limited", None, "auth")
                failure = AppError(429, "RATE_LIMITED", "Too many login attempts")
            else:
                user = await self.repo.user_by_email(email)
                valid = await asyncio.to_thread(
                    verify_password, user.password_hash if user else DUMMY_HASH, password
                )
                if user is None or not valid or not user.is_active:
                    self.audit.record("auth.login_failed", user.id if user else None, "auth")
                    failure = AppError(401, "INVALID_CREDENTIALS", "Invalid email or password")
                else:
                    result, row = await self._issue(user.id, now)
                    user.last_login_at = now
                    user.lock_version += 1
                    self.audit.record("auth.login", user.id, "auth_refresh_sessions", row.id)
        if failure:
            raise failure
        return result

    async def refresh(self, secret: str | None) -> Tokens:
        failure = None
        result = None
        async with self.session.begin():
            now = datetime.now(UTC)
            found = await self.repo.refresh_by_digest(digest(secret)) if secret else None
            user = await self.repo.user(found.user_id, lock=True) if found else None
            row = await self.repo.refresh_by_digest(digest(secret), lock=True) if found else None
            if row and row.consumed_at is not None:
                await self.repo.revoke(row.user_id, now, "TOKEN_REPLAY", row.family_id)
                self.audit.record(
                    "auth.refresh_replay", row.user_id, "auth_refresh_sessions", row.id
                )
                failure = AppError(
                    401, "REFRESH_REPLAY", "Refresh token reuse revoked this session family"
                )
            elif (
                row is None
                or user is None
                or not user.is_active
                or row.revoked_at is not None
                or row.expires_at <= now
                or row.family_expires_at <= now
            ):
                self.audit.record("auth.refresh_failed", user.id if user else None, "auth")
                failure = AppError(
                    401, "AUTHENTICATION_REQUIRED", "Invalid or expired refresh session"
                )
            else:
                result, replacement = await self._issue(user.id, now, row)
                self.audit.record("auth.refresh", user.id, "auth_refresh_sessions", replacement.id)
        # Failure audit/replay revocation must commit before returning an HTTP error.
        if failure:
            raise failure
        return result

    async def authenticate(self, token: str) -> Principal:
        user_id, family_id = decode_access(token, self.settings)
        principal = Principal(user_id, family_id)
        async with self.session.begin():
            await self.authorization.current(principal)
        return principal

    async def logout(self, secret: str | None):
        async with self.session.begin():
            row = await self.repo.refresh_by_digest(digest(secret)) if secret else None
            if row:
                await self.repo.user(row.user_id, lock=True)
                await self.repo.revoke(row.user_id, datetime.now(UTC), "LOGOUT", row.family_id)
                self.audit.record(
                    "auth.logout", row.user_id, "auth_refresh_sessions", row.family_id
                )

    async def logout_all(self, principal: Principal):
        async with self.session.begin():
            user, _ = await self.authorization.current(principal, lock=True)
            await self.repo.revoke(user.id, datetime.now(UTC), "LOGOUT_ALL")
            self.audit.record("auth.logout_all", user.id, "users", user.id)

    async def me(self, principal: Principal):
        async with self.session.begin():
            user, grants = await self.authorization.current(principal)
            return {
                **UserView.model_validate(user).model_dump(mode="json"),
                "global_roles": sorted(grants.global_roles),
                "global_permissions": sorted(grants.global_permissions),
                "laboratories": [
                    {
                        "laboratory_id": str(lab),
                        "roles": sorted(grants.laboratory_roles[lab]),
                        "permissions": sorted(permissions),
                    }
                    for lab, permissions in sorted(grants.laboratories.items())
                ],
            }

    async def sessions(self, principal: Principal, page: int, size: int):
        async with self.session.begin():
            await self.authorization.current(principal)
            families = {}
            for row in await self.repo.family(principal.user_id):
                families.setdefault(row.family_id, []).append(row)
            items = []
            now = datetime.now(UTC)
            for family_id, rows in families.items():
                latest = rows[-1]
                items.append(
                    {
                        "family_id": str(family_id),
                        "created_at": rows[0].created_at,
                        "expires_at": latest.expires_at,
                        "family_expires_at": latest.family_expires_at,
                        "is_active": latest.revoked_at is None
                        and latest.expires_at > now
                        and latest.consumed_at is None,
                        "client_ip": latest.client_ip,
                        "user_agent": latest.user_agent,
                        "etag": family_etag(rows),
                    }
                )
            return {
                "items": items[(page - 1) * size : page * size],
                "page": page,
                "page_size": size,
                "total": len(items),
            }

    async def revoke_family(self, principal: Principal, family_id: UUID, match: str | None):
        async with self.session.begin():
            await self.authorization.current(principal, lock=True)
            rows = await self.repo.family(principal.user_id, family_id)
            if not rows:
                raise missing()
            require_match(match, family_etag(rows))
            await self.repo.revoke(principal.user_id, datetime.now(UTC), "USER_REVOKED", family_id)
            self.audit.record(
                "auth.session_revoked", principal.user_id, "auth_refresh_sessions", family_id
            )

    async def password(
        self, principal: Principal, current: str, replacement: str, match: str | None
    ):
        failure = None
        async with self.session.begin():
            user, _ = await self.authorization.current(principal, lock=True)
            require_match(match, etag(user.lock_version))
            if not await asyncio.to_thread(verify_password, user.password_hash, current):
                self.audit.record("auth.password_failed", user.id, "users", user.id)
                failure = AppError(401, "INVALID_CREDENTIALS", "Incorrect current password")
            else:
                user.password_hash = await asyncio.to_thread(hash_password, replacement)
                user.lock_version += 1
                await self.repo.revoke(user.id, datetime.now(UTC), "PASSWORD_CHANGED")
                self.audit.record(
                    "auth.password_changed",
                    user.id,
                    "users",
                    user.id,
                    source=user.lock_version - 1,
                    target=user.lock_version,
                )
        if failure:
            raise failure
