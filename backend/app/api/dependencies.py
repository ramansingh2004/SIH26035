"""HTTP dependencies and request-local service wiring."""

import hmac
from typing import Annotated
from uuid import uuid4

from fastapi import Depends, Header, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import AppError
from app.core.security import csrf_token
from app.services.administration import AdministrationService
from app.services.audit import RequestContext
from app.services.auth import AuthService
from app.services.authorization import Principal

bearer = HTTPBearer(auto_error=False)
REFRESH_COOKIE = "sih_refresh"
CSRF_COOKIE = "sih_csrf"


async def database(request: Request):
    factory = request.app.state.session_factory
    if factory is None or request.app.state.settings.jwt_secret is None:
        raise AppError(503, "SERVICE_NOT_CONFIGURED", "Configure database and JWT_SECRET")
    async with factory() as session:
        yield session


def context(request: Request) -> RequestContext:
    return RequestContext(
        request_id=getattr(request.state, "request_id", str(uuid4())),
        ip=request.client.host if request.client else None,
        user_agent=(request.headers.get("user-agent") or "")[:500] or None,
    )


def auth_service(
    request: Request, session: Annotated[AsyncSession, Depends(database)]
) -> AuthService:
    return AuthService(session, request.app.state.settings, context(request))


def admin_service(
    request: Request, session: Annotated[AsyncSession, Depends(database)]
) -> AdministrationService:
    return AdministrationService(session, context(request))


async def principal(
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer)],
    service: Annotated[AuthService, Depends(auth_service)],
) -> Principal:
    if credentials is None:
        raise AppError(401, "AUTHENTICATION_REQUIRED", "Bearer token required")
    return await service.authenticate(credentials.credentials)


def origin_check(request: Request):
    if request.headers.get("origin") not in request.app.state.settings.allowed_origins:
        raise AppError(403, "ORIGIN_DENIED", "Trusted Origin header required")


def csrf_check(request: Request, x_csrf_token: Annotated[str | None, Header()] = None):
    origin_check(request)
    refresh = request.cookies.get(REFRESH_COOKIE)
    cookie = request.cookies.get(CSRF_COOKIE)
    if not refresh or not cookie or not x_csrf_token:
        raise AppError(403, "CSRF_FAILED", "Refresh cookie and CSRF header required")
    expected = csrf_token(refresh, request.app.state.settings)
    if not hmac.compare_digest(cookie, expected) or not hmac.compare_digest(x_csrf_token, expected):
        raise AppError(403, "CSRF_FAILED", "Invalid CSRF token")


def logout_csrf(request: Request, x_csrf_token: Annotated[str | None, Header()] = None):
    origin_check(request)
    if request.cookies.get(REFRESH_COOKIE):
        csrf_check(request, x_csrf_token)


Auth = Annotated[AuthService, Depends(auth_service)]
Admin = Annotated[AdministrationService, Depends(admin_service)]
Actor = Annotated[Principal, Depends(principal)]
Match = Annotated[str | None, Header(alias="If-Match")]
