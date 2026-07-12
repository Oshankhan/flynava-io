"""Personal + team task views over the tasks collection.

Tasks come from two places: OpenProject sync (assignee = display name) and
internal quick-create (assignee_id = user_id, source_system "io"). Matching a
login user to OP tasks rides on the name (login users double as employees,
and OP assignees are harvested into the same roster — see services/hr.py).
"""
from __future__ import annotations

import datetime as dt
import uuid

from pymongo.database import Database

DONE = ("done", "closed", "resolved")
IN_PROGRESS = ("progress", "develop", "test", "specif", "review")


def classify(status: str | None) -> str:
    s = (status or "").lower()
    if any(k in s for k in DONE):
        return "completed"
    if any(k in s for k in IN_PROGRESS):
        return "in_progress"
    return "pending"


def _is_overdue(task: dict) -> bool:
    due = task.get("due_date")
    if not due or classify(task.get("status")) == "completed":
        return False
    try:
        return dt.date.fromisoformat(str(due)[:10]) < dt.date.today()
    except ValueError:
        return False


def _row(t: dict, project_names: dict[str, str]) -> dict:
    pid = t.get("project_source_id") or t.get("project_id")
    return {
        "task_id": t.get("task_id") or t.get("source_id"),
        "title": t.get("title"),
        "status": t.get("status"),
        "bucket": "overdue" if _is_overdue(t) else classify(t.get("status")),
        "wp_type": t.get("wp_type"),
        "priority": t.get("priority"),
        "due_date": t.get("due_date"),
        "progress": t.get("progress", 0),
        "project": project_names.get(str(pid), ""),
        "assignee": t.get("assignee") or t.get("assignee_id"),
        "source": t.get("source_system"),
    }


def _project_names(db: Database) -> dict[str, str]:
    out: dict[str, str] = {}
    for p in db.projects.find({}, {"source_id": 1, "project_id": 1, "name": 1}):
        for key in (p.get("source_id"), p.get("project_id")):
            if key:
                out[str(key)] = p.get("name", "")
    return out


def _match_query(names: list[str], user_ids: list[str]) -> dict:
    return {"$or": [{"assignee": {"$in": names}},
                    {"assignee_id": {"$in": user_ids}}]}


def _buckets(rows: list[dict]) -> dict:
    b = {"total": len(rows), "completed": 0, "in_progress": 0,
         "pending": 0, "overdue": 0}
    for r in rows:
        b[r["bucket"]] += 1
    return b


def tasks_for(db: Database, names: list[str], user_ids: list[str]) -> dict:
    pnames = _project_names(db)
    rows = [_row(t, pnames) for t in
            db.tasks.find(_match_query(names, user_ids)).sort("due_date", 1)]
    reopened = [r for r in rows
                if "bug" in (r["wp_type"] or "").lower()
                and "reopen" in (r["status"] or "").lower()]
    return {"rows": rows, "buckets": _buckets(rows), "reopened": reopened}


def authored_by(db: Database, name: str) -> list[dict]:
    """OpenProject tasks this user raised (author == name) — 'bugs I reported'."""
    pnames = _project_names(db)
    return [_row(t, pnames) for t in
            db.tasks.find({"source_system": "openproject", "author": name})
            .sort("due_date", 1)]


def my_tasks(db: Database, user: dict) -> dict:
    result = tasks_for(db, [user["name"]], [user["user_id"]])
    result["authored"] = authored_by(db, user["name"])
    return result


def team_tasks(db: Database, team_id: str) -> dict:
    return team_tasks_bulk(db, [team_id])[team_id]


def team_tasks_bulk(db: Database, team_ids: list[str]) -> dict[str, dict]:
    """Same per-team shape as calling `team_tasks()` once per id, but O(1)
    Mongo round trips instead of O(len(team_ids)) — batches members and
    tasks across every team into one pair of queries. `team_tasks()` calling
    this with a single id is the common case; callers rolling up many teams
    (department/exec dashboards) should call this directly instead of
    looping `team_tasks()`, since each `team_tasks()` call re-runs
    `_project_names()` and a task query on its own.
    """
    if not team_ids:
        return {}
    members = list(db.users.find(
        {"team_id": {"$in": team_ids}, "status": "active"},
        {"user_id": 1, "name": 1, "team_id": 1},
    ))
    names = [m["name"] for m in members]
    ids = [m["user_id"] for m in members]
    pnames = _project_names(db)
    rows = [_row(t, pnames) for t in
            db.tasks.find(_match_query(names, ids)).sort("due_date", 1)]

    members_by_team: dict[str, list[dict]] = {tid: [] for tid in team_ids}
    owner_to_team: dict[str, str] = {}
    for m in members:
        members_by_team.setdefault(m["team_id"], []).append(m)
        owner_to_team[m["name"]] = m["team_id"]
        owner_to_team[m["user_id"]] = m["team_id"]

    rows_by_team: dict[str, list[dict]] = {tid: [] for tid in team_ids}
    for r in rows:
        tid = owner_to_team.get(r["assignee"])
        if tid:
            rows_by_team[tid].append(r)

    result = {}
    for tid in team_ids:
        trows = rows_by_team[tid]
        reopened = [r for r in trows
                    if "bug" in (r["wp_type"] or "").lower()
                    and "reopen" in (r["status"] or "").lower()]
        per_member = []
        for m in members_by_team.get(tid, []):
            mrows = [r for r in trows if r["assignee"] in (m["name"], m["user_id"])]
            per_member.append({"user_id": m["user_id"], "name": m["name"],
                               **_buckets(mrows)})
        result[tid] = {"rows": trows, "buckets": _buckets(trows),
                       "reopened": reopened, "members": per_member}
    return result


def create_task(db: Database, *, creator: dict, title: str, assignee_id: str,
                description: str = "", due_date: str | None = None,
                priority: str = "Normal", project_id: str | None = None,
                stage: str | None = None) -> dict:
    assignee = db.users.find_one({"user_id": assignee_id}, {"name": 1, "user_id": 1})
    task = {
        "task_id": "io_" + uuid.uuid4().hex[:10],
        "title": title,
        "description": description,
        "status": "Open",
        "wp_type": "Task",
        "priority": priority,
        "due_date": due_date,
        "progress": 0,
        "assignee_id": assignee_id,
        "assignee": assignee["name"] if assignee else assignee_id,
        "created_by": creator["user_id"],
        "source_system": "io",
        "project_id": project_id,
        "stage": stage,
        "created_at": dt.datetime.now(dt.timezone.utc),
    }
    db.tasks.insert_one(task)
    task.pop("_id", None)
    return task
