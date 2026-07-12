"""Workspace home payload (one round-trip for the My Workspace page) and the
activity feed read from the audit dataset.

Activity scoping follows the hierarchy: L1 sees own actions, L2 their team's,
L3 their department's, L4 everything.
"""
from __future__ import annotations

import datetime as dt

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pymongo.database import Database

from ...core import rbac
from ...core.rbac import user_level
from ...kpi import engine
from ...services import approvals
from ...services import dashboards as dashboards_svc
from ...services import meetings as meetings_svc
from ...services import notifications as notif
from ...services import tasks as tasks_svc
from ..deps import get_current_user, get_db

router = APIRouter(tags=["workspace"])

# Which KPI modules feed a department head's "Dept KPI pulse" strip.
# Intersected with rbac.has_access(role, module) as defence in depth — a
# dept head's role (manager/hr/marketing) already covers these in MATRIX,
# this just guards against a future role/module mismatch silently leaking.
DEPT_KPI_MODULES = {
    "eng": ["operations", "product_dev"],
    "fin": ["finance", "compliance"],
    "hr": ["hr", "recruitment"],
    "mkt": ["marketing_sales"],
}

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


@router.get("/workspace/department")
def workspace_department(user: dict = Depends(get_current_user),
                         db: Database = Depends(get_db)) -> dict:
    """Department-head rollup: per-team buckets, dept KPI strip, open
    positions. Personal stuff (my tasks/meetings/requests/activity) still
    comes from /workspace/me — this is additive, not a replacement."""
    if user_level(user) < 3:
        raise HTTPException(status.HTTP_403_FORBIDDEN,
                            "department heads and above only")
    dept = user.get("department")

    dept_teams = list(db.teams.find({"department": dept}))
    bulk = tasks_svc.team_tasks_bulk(db, [t["team_id"] for t in dept_teams])
    leads = {u["user_id"]: u["name"] for u in db.users.find(
        {"user_id": {"$in": [t.get("lead_id") for t in dept_teams if t.get("lead_id")]}},
        {"user_id": 1, "name": 1})}

    teams = []
    for t in dept_teams:
        info = bulk[t["team_id"]]
        teams.append({
            "team_id": t["team_id"],
            "name": t["name"],
            "lead_name": leads.get(t.get("lead_id")),
            "buckets": info["buckets"],
            "reopened_count": len(info["reopened"]),
            "member_count": len(info["members"]),
        })

    modules = [m for m in DEPT_KPI_MODULES.get(dept, [])
              if rbac.has_access(user["role"], m)]
    dept_kpis = engine.latest_snapshot(db, modules) if modules else []

    positions = [{k: v for k, v in p.items() if k != "_id"} for p in
                db.positions.find({"status": "open", "dept": dept})] if dept else []

    return {"department": dept, "teams": teams, "dept_kpis": dept_kpis,
            "positions": positions}


@router.get("/workspace/exec")
def workspace_exec(user: dict = Depends(get_current_user),
                   db: Database = Depends(get_db)) -> dict:
    """CEO-grade org overview: company KPIs/projects/bugs (reuses the
    leadership dashboard payload), a department-by-department rollup with
    drill-in anchors, QA automation backlog, pending product docs, today's
    attendance, and escalations awaiting the CEO."""
    if user_level(user) < 4:
        raise HTTPException(status.HTTP_403_FORBIDDEN,
                            "super_admin/leadership only")

    base = dashboards_svc.build(db, "leadership", user)

    today = dt.date.today().isoformat()
    today_status = {r["name"]: r["status"] for r in
                    db.attendance.find({"date": today}, {"name": 1, "status": 1})}

    # Batch every department's teams/members/tasks into a handful of queries
    # instead of looping `team_tasks()` (3 queries each) per team per
    # department — that N+1 is what made this endpoint slow under real
    # network latency to the DB.
    all_teams = list(db.teams.find({}))
    teams_by_dept: dict[str, list[dict]] = {}
    for t in all_teams:
        teams_by_dept.setdefault(t.get("department"), []).append(t)
    bulk = tasks_svc.team_tasks_bulk(db, [t["team_id"] for t in all_teams])

    all_active_users = list(db.users.find(
        {"status": "active"}, {"user_id": 1, "name": 1, "department": 1,
                               "level": 1, "designation": 1, "roles": 1}))
    users_by_dept: dict[str, list[dict]] = {}
    heads_by_dept: dict[str, dict] = {}
    # A multi-role L3 (e.g. a manager who's also the marketing lead) heads
    # their primary department AND any secondary department their extra
    # role implies — otherwise that department shows no head at all.
    _ROLE_DEPT = {"marketing": "mkt", "hr": "hr"}
    for u in all_active_users:
        users_by_dept.setdefault(u.get("department"), []).append(u)
        if u.get("level") == 3:
            if u.get("department") not in heads_by_dept:
                heads_by_dept[u["department"]] = u
            for r in u.get("roles") or []:
                dept = _ROLE_DEPT.get(r)
                if dept and dept not in heads_by_dept:
                    heads_by_dept[dept] = u

    departments = []
    for d in db.departments.find({"dept_id": {"$ne": "exec"}}):
        dept_id = d["dept_id"]
        head = heads_by_dept.get(dept_id)
        dept_users = users_by_dept.get(dept_id, [])
        teams = teams_by_dept.get(dept_id, [])
        agg = {"total": 0, "completed": 0, "in_progress": 0, "pending": 0, "overdue": 0}
        reopened = 0
        for t in teams:
            info = bulk[t["team_id"]]
            for k in agg:
                agg[k] += info["buckets"][k]
            reopened += len(info["reopened"])
        late_today = sum(1 for u in dept_users if today_status.get(u["name"]) == "Late")
        departments.append({
            "dept_id": dept_id, "name": d["name"],
            "head": {"user_id": head["user_id"], "name": head["name"],
                     "designation": head.get("designation")} if head else None,
            "teams_count": len(teams), "member_count": len(dept_users),
            "buckets": agg, "reopened_count": reopened, "late_today": late_today,
        })

    automation_rows = [{k: v for k, v in a.items() if k != "_id"}
                       for a in db.automation_scripts.find()]
    by_module: dict[str, dict[str, int]] = {}
    for a in automation_rows:
        bucket = by_module.setdefault(a["module"], {"pending": 0, "in_review": 0, "done": 0})
        bucket[a["status"]] = bucket.get(a["status"], 0) + 1

    pending_docs = [{k: v for k, v in p.items() if k != "_id"} for p in
                    db.product_docs.find({"status": "pending"}).sort("created_at", 1)]

    attendance_today = {
        "present": sum(1 for s in today_status.values() if s == "Present"),
        "late": sum(1 for s in today_status.values() if s == "Late"),
        "absent": sum(1 for s in today_status.values() if s == "Absent"),
        "late_names": [n for n, s in today_status.items() if s == "Late"][:5],
    }

    return {
        **base,
        "departments": departments,
        "automation": {
            "pending": sum(1 for a in automation_rows if a["status"] == "pending"),
            "by_module": by_module, "rows": automation_rows,
        },
        "pending_docs": pending_docs,
        "attendance_today": attendance_today,
        "inbox_count": len(approvals.inbox(db, user["user_id"])),
        "meetings": meetings_svc.upcoming(db, user["user_id"], limit=5),
        "activity": recent_activity(db, user, limit=8),
    }
