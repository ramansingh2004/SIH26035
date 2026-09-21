"""HTTP composition root; no SQL queries or business rules."""

import json
from contextlib import asynccontextmanager
from uuid import uuid4

from fastapi import FastAPI
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy.exc import IntegrityError
from starlette.exceptions import HTTPException

from app.api.health import router as health_router
from app.api.v1.administration import router as administration_router
from app.api.v1.auth import router as auth_router
from app.core.config import Settings, get_settings
from app.core.errors import AppError
from app.db.session import create_database_engine, create_session_factory


def reject_duplicate_keys(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("Duplicate JSON field")
        result[key] = value
    return result


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings if settings is not None else get_settings()

    @asynccontextmanager
    async def lifespan(application):
        yield
        if application.state.engine is not None:
            await application.state.engine.dispose()

    application = FastAPI(
        title=settings.app_name,
        version="0.2.0",
        lifespan=lifespan,
        docs_url=None,
        redoc_url=None,
        openapi_url=None,
    )
    application.state.settings = settings
    application.state.engine = create_database_engine(settings) if settings.database_url else None
    application.state.session_factory = (
        create_session_factory(application.state.engine) if application.state.engine else None
    )
    application.include_router(health_router)
    application.include_router(auth_router, prefix="/api/v1")
    application.include_router(administration_router, prefix="/api/v1")
    application.add_middleware(
        CORSMiddleware,
        allow_origins=settings.allowed_origins,
        allow_credentials=True,
        allow_methods=["GET", "POST", "PATCH", "DELETE"],
        allow_headers=[
            "Authorization",
            "Content-Type",
            "X-CSRF-Token",
            "If-Match",
            "Idempotency-Key",
        ],
        expose_headers=["ETag", "X-Request-ID"],
    )

    def error_response(request, status, code, message, details=None):
        return JSONResponse(
            status_code=status,
            content={
                "error": {
                    "code": code,
                    "message": message,
                    "details": details or {},
                    "request_id": getattr(request.state, "request_id", str(uuid4())),
                }
            },
        )

    @application.middleware("http")
    async def request_boundary(request, call_next):
        request.state.request_id = str(uuid4())
        if request.headers.get("content-type", "").split(";")[0] == "application/json":
            try:
                body = await request.body()
                if len(body) > 65536:
                    return error_response(
                        request, 413, "BODY_TOO_LARGE", "Request body exceeds 64 KiB"
                    )
                if body:
                    json.loads(
                        body,
                        object_pairs_hook=reject_duplicate_keys,
                        parse_constant=lambda value: (_ for _ in ()).throw(
                            ValueError("Nonfinite JSON")
                        ),
                    )
            except (ValueError, UnicodeDecodeError):
                return error_response(
                    request, 422, "INVALID_INPUT", "Invalid or duplicate JSON fields"
                )
        response = await call_next(request)
        response.headers["X-Request-ID"] = request.state.request_id
        response.headers["Cache-Control"] = "no-store"
        return response

    @application.exception_handler(AppError)
    async def application_error(request, error):
        return error_response(request, error.status, error.code, error.message, error.details)

    @application.exception_handler(RequestValidationError)
    async def validation_error(request, error):
        # Pydantic's raw error includes submitted passwords. Never echo input/ctx.
        details = {
            "fields": [{"location": list(e["loc"]), "type": e["type"]} for e in error.errors()]
        }
        return error_response(request, 422, "INVALID_INPUT", "Request validation failed", details)

    @application.exception_handler(IntegrityError)
    async def integrity_error(request, error):
        return error_response(request, 409, "DATA_CONFLICT", "Uniqueness or relationship conflict")

    @application.exception_handler(HTTPException)
    async def http_error(request, error):
        return error_response(
            request,
            error.status_code,
            "RESOURCE_NOT_FOUND" if error.status_code == 404 else "HTTP_ERROR",
            "Request could not be completed",
        )

    return application


app = create_app()
