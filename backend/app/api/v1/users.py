"""User listing — restricted to super_admin and HR."""
from __future__ import annotations

from fastapi import APIRouter, Depends
from pymongo.database import Database

from ...models.schemas import UserOut
from ..deps import get_db, require_role

router = APIRouter(tags=["users"])


@router.get("/users", response_model=list[UserOut])
def list_users(
    _: dict = Depends(require_role("super_admin", "hr")),
    db: Database = Depends(get_db),
) -> list[UserOut]:
    from ...core.rbac import user_level

    out = []
    for u in db.users.find({}, {"password_hash": 0}):
        out.append(UserOut(
            user_id=u["user_id"], name=u["name"], email=u["email"], role=u["role"],
            department=u.get("department"), status=u.get("status", "active"),
            level=user_level(u), designation=u.get("designation"),
            team_id=u.get("team_id"), reports_to=u.get("reports_to"),
        ))
    return out
