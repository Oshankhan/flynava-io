"""Shared FastAPI dependencies: DB, current user, RBAC gate."""
from __future__ import annotations

import jwt
from fastapi import Depends, Header, HTTPException, status
from pymongo.database import Database

from ..core import rbac
from ..core.security import decode_token
from ..db import get_db

__all__ = ["get_db", "get_current_user", "require_module", "require_role"]


def get_current_user(
    authorization: str = Header(default=""),
    db: Database = Depends(get_db),
) -> dict:
    if not authorization.lower().startswith("bearer "):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "missing bearer token")
    token = authorization.split(" ", 1)[1].strip()
    try:
        payload = decode_token(token)
    except jwt.PyJWTError:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "invalid or expired token")
    if payload.get("type") != "access":
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "wrong token type")
    user = db.users.find_one({"user_id": payload["sub"]}, {"password_hash": 0})
    if not user or user.get("status") != "active":
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "user not found or inactive")
    return user


def require_module(module: str):
    """Dependency factory: 403 unless the user's role has any access to module."""

    def dep(user: dict = Depends(get_current_user)) -> dict:
        if not rbac.has_access(user["role"], module):
            raise HTTPException(status.HTTP_403_FORBIDDEN, f"no access to {module}")
        return user

    return dep


def require_role(*roles: str):
    def dep(user: dict = Depends(get_current_user)) -> dict:
        if user["role"] not in roles:
            raise HTTPException(status.HTTP_403_FORBIDDEN, "insufficient role")
        return user

    return dep
