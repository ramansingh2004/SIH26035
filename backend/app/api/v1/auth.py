from uuid import UUID

from fastapi import APIRouter, Depends, Query, Request, Response

from app.api.dependencies import (
    CSRF_COOKIE,
    REFRESH_COOKIE,
    Actor,
    Auth,
    Match,
    csrf_check,
    logout_csrf,
    origin_check,
)
from app.core.concurrency import etag
from app.core.security import csrf_token
from app.schemas.identity import Login, PasswordChange, TokenView
from app.services.auth import Tokens

router = APIRouter(prefix="/auth", tags=["Authentication"])


def set_tokens(response: Response, request: Request, tokens: Tokens) -> TokenView:
    settings = request.app.state.settings
    response.set_cookie(
        REFRESH_COOKIE,
        tokens.refresh,
        max_age=tokens.refresh_max_age,
        path="/api/v1/auth",
        secure=settings.cookie_secure,
        httponly=True,
        samesite="strict",
    )
    response.set_cookie(
        CSRF_COOKIE,
        csrf_token(tokens.refresh, settings),
        max_age=tokens.refresh_max_age,
        path="/",
        secure=settings.cookie_secure,
        httponly=False,
        samesite="strict",
    )
    response.headers["Cache-Control"] = "no-store"
    return TokenView(access_token=tokens.access, expires_in=tokens.expires_in)


def clear_tokens(response: Response, request: Request):
    secure = request.app.state.settings.cookie_secure
    response.delete_cookie(
        REFRESH_COOKIE, path="/api/v1/auth", secure=secure, httponly=True, samesite="strict"
    )
    response.delete_cookie(CSRF_COOKIE, path="/", secure=secure, samesite="strict")


@router.post("/login", response_model=TokenView, dependencies=[Depends(origin_check)])
async def login(data: Login, request: Request, response: Response, service: Auth):
    return set_tokens(
        response, request, await service.login(str(data.email), data.password.get_secret_value())
    )


@router.post("/refresh", response_model=TokenView, dependencies=[Depends(csrf_check)])
async def refresh(request: Request, response: Response, service: Auth):
    return set_tokens(response, request, await service.refresh(request.cookies.get(REFRESH_COOKIE)))


@router.post("/logout", status_code=204, dependencies=[Depends(logout_csrf)])
async def logout(request: Request, response: Response, service: Auth):
    await service.logout(request.cookies.get(REFRESH_COOKIE))
    clear_tokens(response, request)


@router.post("/logout-all", status_code=204, dependencies=[Depends(csrf_check)])
async def logout_all(request: Request, response: Response, service: Auth, actor: Actor):
    await service.logout_all(actor)
    clear_tokens(response, request)


@router.get("/me")
async def me(response: Response, service: Auth, actor: Actor):
    result = await service.me(actor)
    response.headers["ETag"] = etag(result["lock_version"])
    return result


@router.get("/sessions")
async def sessions(
    service: Auth,
    actor: Actor,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
):
    return await service.sessions(actor, page, page_size)


@router.delete("/sessions/{family_id}", status_code=204)
async def revoke_session(family_id: UUID, service: Auth, actor: Actor, if_match: Match = None):
    await service.revoke_family(actor, family_id, if_match)


@router.post("/password", status_code=204, dependencies=[Depends(csrf_check)])
async def password(
    data: PasswordChange,
    request: Request,
    response: Response,
    service: Auth,
    actor: Actor,
    if_match: Match = None,
):
    await service.password(
        actor,
        data.current_password.get_secret_value(),
        data.new_password.get_secret_value(),
        if_match,
    )
    clear_tokens(response, request)
