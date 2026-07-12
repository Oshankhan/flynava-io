"""Org hierarchy endpoints: my team/lead, teams directory, members, and the
drill-down (direct reports + an individual's full overview) that powers the
"click into a person's team, click into a person's dashboard" flow — same
two endpoints serve every level (L1..L4); only who they're allowed to view
differs (see `_can_view`).
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from pymongo.database import Database

from ...core.rbac import user_level
from ...services import hr
from ...services import meetings as meetings_svc
from ...services import tasks as tasks_svc
from ..deps import get_current_user, get_db
from .workspace import _FEED_VERBS

router = APIRouter(tags=["org"])

_LITE = {"_id": 0, "user_id": 1, "name": 1, "designation": 1, "team_id": 1,
         "level": 1, "department": 1, "role": 1, "reports_to": 1}


def _user_lite(u: dict | None) -> dict | None:
    if not u:
        return None
    return {k: u.get(k) for k in
            ("user_id", "name", "designation", "team_id", "level", "department",
             "role", "reports_to")}


def _team_out(db: Database, t: dict) -> dict:
    lead = db.users.find_one({"user_id": t.get("lead_id")}, _LITE)
    return {
        "team_id": t["team_id"], "name": t["name"],
        "department": t.get("department"),
        "lead": _user_lite(lead),
        "member_count": db.users.count_documents(
            {"team_id": t["team_id"], "status": "active"}),
    }


def _is_ancestor(db: Database, viewer_id: str, target_id: str, max_hops: int = 8) -> bool:
    """True if viewer is somewhere above target in the reports_to chain."""
    current = db.users.find_one({"user_id": target_id}, {"reports_to": 1})
    hops = 0
    while current and current.get("reports_to") and hops < max_hops:
        if current["reports_to"] == viewer_id:
            return True
        current = db.users.find_one({"user_id": current["reports_to"]}, {"reports_to": 1})
        hops += 1
    return False


def _can_view(db: Database, viewer: dict, target_id: str) -> bool:
    if viewer["user_id"] == target_id:
        return True
    if user_level(viewer) >= 4 or viewer.get("role") in ("super_admin", "hr"):
        return True
    return _is_ancestor(db, viewer["user_id"], target_id)


def _require_viewable(db: Database, viewer: dict, target_id: str) -> dict:
    target = db.users.find_one({"user_id": target_id})
    if not target:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "user not found")
    if not _can_view(db, viewer, target_id):
        raise HTTPException(status.HTTP_403_FORBIDDEN,
                            "you may only view your own reporting chain")
    return target


@router.get("/org/reports/{user_id}")
def reports_of(user_id: str, user: dict = Depends(get_current_user),
              db: Database = Depends(get_db)) -> list[dict]:
    """Direct reports of user_id, each decorated with enough signal for a
    drill-down card: task load, reopened bugs, attendance, pending requests,
    and whether they themselves have reports (so the UI knows to keep
    drilling or to link straight to their individual dashboard)."""
    _require_viewable(db, user, user_id)
    team_names = {t["team_id"]: t["name"] for t in db.teams.find({}, {"team_id": 1, "name": 1})}

    out = []
    for m in db.users.find({"reports_to": user_id, "status": "active"}).sort("name", 1):
        tasks = tasks_svc.tasks_for(db, [m["name"]], [m["user_id"]])
        att = hr.attendance_for(db, m["name"])
        out.append({
            **_user_lite(m),
            "team_name": team_names.get(m.get("team_id")),
            "buckets": tasks["buckets"],
            "reopened_count": len(tasks["reopened"]),
            "late_7d": att["late_count"],
            "absent_7d": att["absent_count"],
            "pending_requests": db.requests.count_documents(
                {"requester_id": m["user_id"], "status": "pending"}),
            "has_reports": db.users.count_documents(
                {"reports_to": m["user_id"], "status": "active"}) > 0,
        })
    return out


@router.get("/org/users/{user_id}/overview")
def user_overview(user_id: str, user: dict = Depends(get_current_user),
                  db: Database = Depends(get_db)) -> dict:
    """The 'clicked into someone's dashboard' payload — their tasks,
    attendance, leave, pending docs, meetings and recent activity."""
    target = _require_viewable(db, user, user_id)

    tasks = tasks_svc.my_tasks(db, target)
    attendance = hr.attendance_for(db, target["name"])
    hr_record = hr.employee_by_email(db, target["email"]) if target.get("email") else None
    lead = db.users.find_one({"user_id": target.get("reports_to")}, _LITE) \
        if target.get("reports_to") else None
    team = db.teams.find_one({"team_id": target.get("team_id")}, {"_id": 0}) \
        if target.get("team_id") else None
    pending_docs = [{k: v for k, v in d.items() if k not in ("_id", "path")} for d in
                    db.documents.find({"uploaded_by": user_id, "status": "pending"})]
    activity = []
    for a in db.audit_logs.find({"actor_id": user_id, "action": {"$in": list(_FEED_VERBS)}}) \
                          .sort("created_at", -1).limit(8):
        meta = a.get("meta") or {}
        subject = meta.get("title") or a.get("entity_id") or ""
        activity.append({
            "action": a["action"],
            "text": f"{_FEED_VERBS[a['action']]} “{subject}”" if subject
                    else _FEED_VERBS[a["action"]],
            "at": a.get("created_at"),
        })

    return {
        "user": _user_lite(target),
        "team": team,
        "lead": _user_lite(lead),
        "buckets": tasks["buckets"],
        "tasks": tasks["rows"][:10],
        "reopened": tasks["reopened"],
        "authored": tasks.get("authored", []),
        "attendance": attendance,
        "leave_balance": hr_record.get("leave_balance") if hr_record else None,
        "recent_leaves": (hr_record.get("leaves") or [])[:5] if hr_record else [],
        "pending_docs": pending_docs,
        "meetings": meetings_svc.upcoming(db, user_id, limit=5),
        "activity": activity,
    }


@router.get("/org/me")
def org_me(user: dict = Depends(get_current_user),
           db: Database = Depends(get_db)) -> dict:
    team = db.teams.find_one({"team_id": user.get("team_id")}, {"_id": 0}) \
        if user.get("team_id") else None
    lead = db.users.find_one({"user_id": user.get("reports_to")}, _LITE) \
        if user.get("reports_to") else None
    # direct reports (non-empty for L2+)
    reports = [_user_lite(u) for u in
               db.users.find({"reports_to": user["user_id"], "status": "active"}, _LITE)]
    return {
        "user": _user_lite(user),
        "level": user_level(user),
        "team": team,
        "lead": _user_lite(lead),
        "reports": reports,
    }


@router.get("/org/teams")
def list_teams(user: dict = Depends(get_current_user),
               db: Database = Depends(get_db)) -> list[dict]:
    return [_team_out(db, t) for t in db.teams.find().sort("name", 1)]


@router.get("/org/teams/{team_id}/members")
def team_members(team_id: str, user: dict = Depends(get_current_user),
                 db: Database = Depends(get_db)) -> list[dict]:
    if not db.teams.find_one({"team_id": team_id}):
        raise HTTPException(status.HTTP_404_NOT_FOUND, "team not found")
    return [_user_lite(u) for u in
            db.users.find({"team_id": team_id, "status": "active"}, _LITE)
            .sort("name", 1)]


@router.get("/org/users")
def directory(user: dict = Depends(get_current_user),
              db: Database = Depends(get_db)) -> list[dict]:
    """Lightweight company directory for pickers (invites, assignment)."""
    return [_user_lite(u) for u in
            db.users.find({"status": "active",
                           "role": {"$nin": ["investor", "partner"]}}, _LITE)
            .sort("name", 1)]
