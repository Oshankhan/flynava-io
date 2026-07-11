"""Auth endpoints: login, refresh, me."""
from __future__ import annotations

import jwt
from fastapi import APIRouter, Depends, HTTPException, status
from pymongo.database import Database

from ...core import audit
from ...core.rbac import accessible_modules, user_level
from ...core.security import (
    create_access_token,
    create_refresh_token,
    decode_token,
    verify_password,
)
from ...models.schemas import (
    LoginRequest,
    MeResponse,
    RefreshRequest,
    TokenResponse,
    UserOut,
)
from ..deps import get_current_user, get_db

router = APIRouter(tags=["auth"])


def _user_out(user: dict) -> UserOut:
    return UserOut(
        user_id=user["user_id"], name=user["name"], email=user["email"],
        role=user["role"], department=user.get("department"),
        status=user.get("status", "active"),
        level=user_level(user), designation=user.get("designation"),
        team_id=user.get("team_id"), reports_to=user.get("reports_to"),
    )


@router.post("/auth/login", response_model=TokenResponse)
def login(body: LoginRequest, db: Database = Depends(get_db)) -> TokenResponse:
    user = db.users.find_one({"email": body.email.lower()})
    if not user or not verify_password(body.password, user.get("password_hash", "")):
        audit.record(db, actor_id=None, action="login_failed",
                     meta={"email": body.email})
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "invalid credentials")
    if user.get("status") != "active":
        raise HTTPException(status.HTTP_403_FORBIDDEN, "account inactive")
    audit.record(db, actor_id=user["user_id"], action="login")
    return TokenResponse(
        access_token=create_access_token(user["user_id"], user["role"]),
        refresh_token=create_refresh_token(user["user_id"]),
        user=_user_out(user),
    )


@router.post("/auth/refresh", response_model=TokenResponse)
def refresh(body: RefreshRequest, db: Database = Depends(get_db)) -> TokenResponse:
    try:
        payload = decode_token(body.refresh_token)
    except jwt.PyJWTError:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "invalid refresh token")
    if payload.get("type") != "refresh":
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "wrong token type")
    user = db.users.find_one({"user_id": payload["sub"]})
    if not user or user.get("status") != "active":
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "user not found or inactive")
    return TokenResponse(
        access_token=create_access_token(user["user_id"], user["role"]),
        refresh_token=create_refresh_token(user["user_id"]),
        user=_user_out(user),
    )


@router.get("/auth/me", response_model=MeResponse)
def me(user: dict = Depends(get_current_user)) -> MeResponse:
    return MeResponse(user=_user_out(user), modules=accessible_modules(user["role"]))
