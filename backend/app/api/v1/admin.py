"""Admin panel — user management, KPI/config management, logs
(PRD scope: 'Admin panel for user management, integration configuration, and
system settings' + NFR-012, NOT-005, SEC-008). Super-admin only."""
from __future__ import annotations

import datetime as dt
import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, EmailStr
from pymongo.database import Database

from ...core import audit
from ...core.rbac import ROLES
from ...core.security import hash_password
from ..deps import get_db, require_role

router = APIRouter(tags=["admin"], dependencies=[Depends(require_role("super_admin"))])


class KpiDefIn(BaseModel):
    kpi_id: str
    name: str
    module: str
    formula: str = "static"
    unit: str = ""
    target: float | None = None
    direction: str = "higher"


class UserCreate(BaseModel):
    name: str
    email: EmailStr
    role: str
    password: str
    department: str | None = None


class UserUpdate(BaseModel):
    role: str | None = None
    status: str | None = None  # active | inactive


@router.post("/admin/users")
def create_user(body: UserCreate, db: Database = Depends(get_db)) -> dict:
    if body.role not in ROLES:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, f"role must be one of {ROLES}")
    if db.users.find_one({"email": body.email.lower()}):
        raise HTTPException(status.HTTP_409_CONFLICT, "email already exists")
    user = {
        "user_id": f"u_{uuid.uuid4().hex[:8]}",
        "name": body.name, "email": body.email.lower(), "role": body.role,
        "department": body.department, "status": "active",
        "password_hash": hash_password(body.password),
        "created_at": dt.datetime.now(dt.timezone.utc),
    }
    db.users.insert_one(user)
    audit.record(db, actor_id="admin", action="user_created",
                 entity_type="user", entity_id=user["user_id"],
                 meta={"role": body.role})
    return {k: v for k, v in user.items() if k not in {"_id", "password_hash"}}


@router.patch("/admin/users/{user_id}")
def update_user(user_id: str, body: UserUpdate,
                db: Database = Depends(get_db)) -> dict:
    updates: dict = {}
    if body.role is not None:
        if body.role not in ROLES:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, "invalid role")
        updates["role"] = body.role
    if body.status is not None:
        if body.status not in {"active", "inactive"}:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, "invalid status")
        updates["status"] = body.status
    if not updates:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "nothing to update")
    res = db.users.update_one({"user_id": user_id}, {"$set": updates})
    if res.matched_count != 1:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "user not found")
    audit.record(db, actor_id="admin", action="user_updated",
                 entity_type="user", entity_id=user_id, meta=updates)
    return {"status": "ok", "user_id": user_id, **updates}


@router.get("/admin/kpi-defs")
def list_kpi_defs(db: Database = Depends(get_db)) -> list[dict]:
    return [{k: v for k, v in d.items() if k != "_id"} for d in db.kpi_defs.find()]


@router.put("/admin/kpi-defs")
def upsert_kpi_def(body: KpiDefIn, db: Database = Depends(get_db)) -> dict:
    """Add or edit a KPI definition without a code deploy (NFR-012/013)."""
    db.kpi_defs.update_one({"kpi_id": body.kpi_id}, {"$set": body.model_dump()},
                           upsert=True)
    audit.record(db, actor_id="admin", action="kpi_def_upsert", entity_id=body.kpi_id)
    return {"status": "ok", "kpi_id": body.kpi_id}


@router.get("/admin/notification-log")
def notification_log(limit: int = 100, db: Database = Depends(get_db)) -> list[dict]:
    out = []
    for n in db.notifications.find().sort("created_at", -1).limit(limit):
        n["_id"] = str(n["_id"])
        out.append(n)
    return out


@router.get("/admin/audit")
def audit_tail(limit: int = 100, db: Database = Depends(get_db)) -> list[dict]:
    out = []
    for a in db.audit_logs.find().sort("created_at", -1).limit(limit):
        a["_id"] = str(a["_id"])
        out.append(a)
    return out
