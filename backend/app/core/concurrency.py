"""HTTP-independent optimistic version checks."""

from app.core.errors import AppError


def etag(version: int | str) -> str:
    return f'"{version}"'


def require_match(supplied: str | None, current: str) -> None:
    if supplied is None:
        raise AppError(428, "PRECONDITION_REQUIRED", "If-Match is required")
    if supplied != current:
        raise AppError(412, "VERSION_CONFLICT", "Resource has changed; reload it")
