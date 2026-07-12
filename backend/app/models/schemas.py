"""Pydantic request/response schemas."""
from __future__ import annotations

from pydantic import BaseModel, EmailStr, Field


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class RefreshRequest(BaseModel):
    refresh_token: str


class UserOut(BaseModel):
    user_id: str
    name: str
    email: EmailStr
    role: str
    roles: list[str] = []
    department: str | None = None
    status: str = "active"
    # Org hierarchy (L4 CEO → L3 dept head → L2 team lead → L1 executive)
    level: int = 1
    designation: str | None = None
    team_id: str | None = None
    reports_to: str | None = None


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    user: UserOut


class MeResponse(BaseModel):
    user: UserOut
    modules: dict[str, str] = Field(default_factory=dict)


class ApiResponse(BaseModel):
    """Standard envelope (PRD API-005)."""
    status: str = "ok"
    message: str = ""
    data: object | None = None
    request_id: str | None = None
