"""Password and token primitives; token material is never logged."""

import hashlib
import hmac
import secrets
from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

import jwt
from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError

from app.core.config import Settings
from app.core.errors import AppError

hasher = PasswordHasher()
DUMMY_HASH = hasher.hash(secrets.token_urlsafe(32))


def hash_password(password: str) -> str:
    return hasher.hash(password)


def verify_password(encoded: str, password: str) -> bool:
    try:
        return hasher.verify(encoded, password)
    except (VerificationError, InvalidHashError):
        return False


def digest(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def csrf_token(refresh: str, settings: Settings) -> str:
    return hmac.new(
        settings.signing_key().encode(), ("csrf:" + refresh).encode(), hashlib.sha256
    ).hexdigest()


def access_token(user_id: UUID, family_id: UUID, settings: Settings) -> str:
    now = datetime.now(UTC)
    return jwt.encode(
        {
            "sub": str(user_id),
            "fid": str(family_id),
            "jti": str(uuid4()),
            "iat": now,
            "exp": now + timedelta(seconds=settings.access_token_seconds),
            "iss": settings.jwt_issuer,
            "aud": settings.jwt_audience,
        },
        settings.signing_key(),
        algorithm="HS256",
    )


def decode_access(token: str, settings: Settings) -> tuple[UUID, UUID]:
    try:
        claims = jwt.decode(
            token,
            settings.signing_key(),
            algorithms=["HS256"],
            issuer=settings.jwt_issuer,
            audience=settings.jwt_audience,
            options={"require": ["sub", "fid", "jti", "iat", "exp", "iss", "aud"]},
        )
        return UUID(claims["sub"]), UUID(claims["fid"])
    except (jwt.InvalidTokenError, ValueError, TypeError, KeyError):
        raise AppError(401, "AUTHENTICATION_REQUIRED", "Invalid or expired access token") from None
