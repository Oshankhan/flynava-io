"""Workspace home payload (one round-trip for the My Workspace page) and the
activity feed read from the audit dataset.

Activity scoping follows the hierarchy: L1 sees own actions, L2 their team's,
L3 their department's, L4 everything.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from pymongo.database import Database

from ...core.rbac import user_level
from ...services import approvals
from ...services import meetings as meetings_svc
from ...services import notifications as notif
from ...services import tasks as tasks_svc
from ..deps import get_current_user, get_db

router = APIRouter(tags=["workspace"])

# audit actions that read well in a human feed (auto API audit rows excluded)
_FEED_VERBS = {
    "task_created": "created task",
    "meeting_created": "scheduled meeting",
    "meeting_cancelled": "cancelled meeting",
    "request_submitted": "submitted request",
    "request_approved": "approved request",
    "request_rejected": "rejected request",
    "request_forwarded": "forwarded request",
    "document_uploaded": "uploaded document",
    "document_approved": "approved document",
    "document_rejected": "rejected document",
    "award_issued": "issued award",
    "attendance_upload": "uploaded attendance",
    "integration_sync": "synced integration",
}


def _actor_scope(db: Database, user: dict) -> list[str] | None:
    """User-ids whose activity this user may see. None = everyone (L4)."""
    level = user_level(user)
    if level >= 4 or user.get("role") == "super_admin":
        return None
    if level == 3:
        return [u["user_id"] for u in
                db.users.find({"department": user.get("department")}, {"user_id": 1})]
    if level == 2 and user.get("team_id"):
        return [u["user_id"] for u in
                db.users.find({"team_id": user["team_id"]}, {"user_id": 1})]
    return [user["user_id"]]


def recent_activity(db: Database, user: dict, limit: int = 10) -> list[dict]:
    q: dict = {"action": {"$in": list(_FEED_VERBS)}}
    scope = _actor_scope(db, user)
    if scope is not None:
        q["actor_id"] = {"$in": scope}
    rows = []
    names = {u["user_id"]: u["name"] for u in db.users.find({}, {"user_id": 1, "name": 1})}
    for a in db.audit_logs.find(q).sort("created_at", -1).limit(limit):
        meta = a.get("meta") or {}
        subject = meta.get("title") or a.get("entity_id") or ""
        rows.append({
            "actor_id": a.get("actor_id"),
            "actor_name": names.get(a.get("actor_id"), a.get("actor_id") or "system"),
            "action": a["action"],
            "text": f"{_FEED_VERBS[a['action']]} “{subject}”" if subject
                    else _FEED_VERBS[a["action"]],
            "entity_type": a.get("entity_type"),
            "at": a.get("created_at"),
        })
    return rows


@router.get("/activity/recent")
def activity(limit: int = Query(default=10, le=50),
             user: dict = Depends(get_current_user),
             db: Database = Depends(get_db)) -> list[dict]:
    return recent_activity(db, user, limit)


@router.get("/workspace/me")
def workspace_me(user: dict = Depends(get_current_user),
                 db: Database = Depends(get_db)) -> dict:
    level = user_level(user)
    my = tasks_svc.my_tasks(db, user)
    team = db.teams.find_one({"team_id": user.get("team_id")}, {"_id": 0}) \
        if user.get("team_id") else None
    lead = None
    if user.get("reports_to"):
        lu = db.users.find_one({"user_id": user["reports_to"]},
                               {"name": 1, "designation": 1})
        if lu:
            lead = {"name": lu["name"], "designation": lu.get("designation")}
    pending_inbox = approvals.inbox(db, user["user_id"]) if level >= 2 else []
    return {
        "user": {"user_id": user["user_id"], "name": user["name"],
                 "designation": user.get("designation"),
                 "department": user.get("department"), "level": level,
                 "role": user["role"], "team_id": user.get("team_id")},
        "team": team,
        "lead": lead,
        "buckets": my["buckets"],
        "tasks": my["rows"][:8],
        "reopened": my["reopened"],
        "meetings": meetings_svc.upcoming(db, user["user_id"], limit=6),
        "my_requests": approvals.mine(db, user["user_id"])[:5],
        "inbox_count": len(pending_inbox),
        "unread_notifications": notif.unread_count(db, user["user_id"]),
        "activity": recent_activity(db, user, limit=8),
    }
