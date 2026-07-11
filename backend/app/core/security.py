"""Password hashing (bcrypt) and JWT tokens. Pure functions, no DB."""
from __future__ import annotations

import datetime as dt
from typing import Any

import bcrypt
import jwt

from ..config import settings


def hash_password(password: str, rounds: int | None = None) -> str:
    r = settings.bcrypt_rounds if rounds is None else rounds
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt(rounds=r)).decode()


def verify_password(password: str, hashed: str) -> bool:
    try:
        return bcrypt.checkpw(password.encode(), hashed.encode())
    except ValueError:
        return False


def _create_token(sub: str, token_type: str, ttl: dt.timedelta, extra: dict | None = None) -> str:
    now = dt.datetime.now(dt.timezone.utc)
    payload: dict[str, Any] = {
        "sub": sub,
        "type": token_type,
        "iat": now,
        "exp": now + ttl,
    }
    if extra:
        payload.update(extra)
    return jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_alg)


def create_access_token(user_id: str, role: str) -> str:
    return _create_token(
        user_id,
        "access",
        dt.timedelta(minutes=settings.access_token_ttl_min),
        {"role": role},
    )


def create_refresh_token(user_id: str) -> str:
    return _create_token(
        user_id, "refresh", dt.timedelta(days=settings.refresh_token_ttl_days)
    )


def decode_token(token: str) -> dict:
    """Decode and validate. Raises jwt.PyJWTError on invalid/expired."""
    return jwt.decode(token, settings.jwt_secret, algorithms=[settings.jwt_alg])
