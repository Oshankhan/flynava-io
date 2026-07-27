"""Shared FastAPI dependencies: DB, current user, RBAC gate."""
from __future__ import annotations

import jwt
from fastapi import Depends, Header, HTTPException, status
from pymongo.database import Database

from ..core import rbac
from ..core.security import decode_token
from ..db import get_db

__all__ = ["get_db", "get_current_user", "require_module", "require_role",
          "has_aggregate_access", "require_any_module"]


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
    """Dependency factory: 403 unless the user's role AND department both
    grant access to module (see rbac.has_module_access)."""

    def dep(user: dict = Depends(get_current_user)) -> dict:
        if not rbac.has_module_access(user, module):
            raise HTTPException(status.HTTP_403_FORBIDDEN, f"no access to {module}")
        return user

    return dep


def require_role(*roles: str):
    def dep(user: dict = Depends(get_current_user)) -> dict:
        if user["role"] not in roles:
            raise HTTPException(status.HTTP_403_FORBIDDEN, "insufficient role")
        return user

    return dep


def has_aggregate_access(user: dict, module: str) -> bool:
    """Like `rbac.has_module_access`, but a bare "own" level — self-only
    visibility, e.g. an employee's own HR record or own task list — doesn't
    qualify for company-wide aggregate screens (Indicator Of Success,
    Financial Forecaster). Also requires each role's access to clear the
    department gate (see rbac.role_module_allowed) — a manager outside a
    department no longer sees that department's aggregate screens just by
    role. Unioned across every role a multi-role user holds."""
    dept = user.get("department")
    return any(
        rbac.access_level(r, module) not in (rbac.NONE, "own")
        and rbac.role_module_allowed(dept, r, module)
        for r in rbac.user_roles(user)
    )


def require_any_module(*modules: str):
    """403 unless the caller has non-"own" access to at least one of
    `modules`, unioned across every role they hold."""

    def dep(user: dict = Depends(get_current_user)) -> dict:
        if not any(has_aggregate_access(user, m) for m in modules):
            raise HTTPException(status.HTTP_403_FORBIDDEN,
                                f"no access to {' or '.join(modules)}")
        return user

    return dep
