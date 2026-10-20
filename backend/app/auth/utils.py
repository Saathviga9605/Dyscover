"""Authentication utilities: password hashing, access tokens, refresh tokens."""

from __future__ import annotations

import hashlib
import secrets
from datetime import timedelta, timezone
from typing import Any
from uuid import UUID, uuid4

import bcrypt
import jwt

from app.core.config import get_settings
from app.core.time import utcnow

ALGORITHM = "HS256"
BCRYPT_ROUNDS = 12
# bcrypt only uses the first 72 bytes; longer passwords are rejected at validation.
BCRYPT_MAX_BYTES = 72

# Verified against when the account does not exist so that login timing does not
# reveal whether an email is registered.
_DUMMY_HASH = bcrypt.hashpw(b"dyscover-timing-equalizer", bcrypt.gensalt(rounds=BCRYPT_ROUNDS))


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt(rounds=BCRYPT_ROUNDS)).decode("utf-8")


def verify_password(password: str, hashed: str | None) -> bool:
    try:
        candidate = password.encode("utf-8")
        if not hashed:
            bcrypt.checkpw(candidate, _DUMMY_HASH)
            return False
        return bcrypt.checkpw(candidate, hashed.encode("utf-8"))
    except (ValueError, TypeError):
        return False


def create_access_token(user_id: UUID, role: str, token_version: int, expires_delta: timedelta | None = None) -> str:
    settings = get_settings()
    now = utcnow().replace(tzinfo=timezone.utc)
    expire = now + (expires_delta or timedelta(minutes=settings.access_token_minutes))
    claims: dict[str, Any] = {
        "sub": str(user_id),
        "role": role,
        "ver": token_version,
        "type": "access",
        "iat": now,
        "exp": expire,
        "jti": uuid4().hex,
    }
    return jwt.encode(claims, settings.secret_key, algorithm=ALGORITHM)


def decode_access_token(token: str) -> dict[str, Any] | None:
    """Return validated claims, or None for any invalid, expired or non-access token."""
    try:
        claims = jwt.decode(
            token,
            get_settings().secret_key,
            algorithms=[ALGORITHM],  # explicit allow-list: rejects "none" and algorithm confusion
            options={"require": ["exp", "iat", "sub"]},
        )
    except jwt.InvalidTokenError:
        return None
    if claims.get("type") != "access" or not isinstance(claims.get("ver"), int):
        return None
    return claims


def new_refresh_token() -> str:
    return secrets.token_urlsafe(48)


def hash_refresh_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def generate_secure_token(length: int = 32) -> str:
    return secrets.token_urlsafe(length)
