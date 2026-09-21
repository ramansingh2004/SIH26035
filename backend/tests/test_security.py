from datetime import UTC, datetime, timedelta
from uuid import uuid4

import jwt
import pytest
from pydantic import ValidationError

from app.core.concurrency import etag, require_match
from app.core.config import Settings
from app.core.errors import AppError
from app.core.security import access_token, decode_access, hash_password, verify_password
from app.schemas.identity import AssignmentCreate
from app.services.authorization import Grants


def test_password_hashing():
    encoded = hash_password("A synthetic test password")
    assert encoded.startswith("$argon2id$")
    assert verify_password(encoded, "A synthetic test password")
    assert not verify_password(encoded, "wrong")
    assert not verify_password("invalid hash", "anything")


def test_access_claims_and_expiry():
    settings = Settings(_env_file=None, jwt_secret="test-key-012345678901234567890123456789")
    user, family = uuid4(), uuid4()
    token = access_token(user, family, settings)
    assert decode_access(token, settings) == (user, family)
    claims = jwt.decode(
        token, settings.signing_key(), algorithms=["HS256"], audience=settings.jwt_audience
    )
    claims["exp"] = datetime.now(UTC) - timedelta(seconds=1)
    for bad in [jwt.encode(claims, settings.signing_key(), algorithm="HS256"), token + "x"]:
        with pytest.raises(AppError) as exc:
            decode_access(bad, settings)
        assert exc.value.status == 401
    assert "roles" not in claims and "permissions" not in claims


@pytest.mark.parametrize("supplied,status", [(None, 428), ('"2"', 412), ("*", 412), ('W/"1"', 412)])
def test_etag_requires_exact_current_version(supplied, status):
    with pytest.raises(AppError) as exc:
        require_match(supplied, etag(1))
    assert exc.value.status == status


def test_global_admin_is_not_regulatory_authority():
    grants = Grants({"user:read", "laboratory:read"}, {}, {"ADMIN"}, {})
    with pytest.raises(AppError):
        grants.require("observation:read", uuid4())
    with pytest.raises(AppError):
        grants.require("approval:finalize", uuid4())
    grants.require("user:read")


@pytest.mark.parametrize(
    "data",
    [
        {"role_code": "ADMIN", "scope_type": "GLOBAL", "laboratory_id": str(uuid4())},
        {"role_code": "VIEWER", "scope_type": "GLOBAL"},
        {"role_code": "VIEWER", "scope_type": "LABORATORY"},
    ],
)
def test_assignment_schema_rejects_invalid_scopes(data):
    with pytest.raises(ValidationError):
        AssignmentCreate.model_validate(data)


def test_production_cannot_disable_secure_cookies():
    with pytest.raises(ValidationError):
        Settings(_env_file=None, environment="production", cookie_secure=False)


def test_weak_signing_key_rejected():
    with pytest.raises(ValidationError):
        Settings(_env_file=None, jwt_secret="short")
