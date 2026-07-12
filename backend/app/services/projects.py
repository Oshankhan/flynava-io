"""Client project + stage-pipeline service (Team Tasks, project-centric).

Projects move through the shared `STAGE_PIPELINE` (see services.seed).
Tasks/bugs reference a project via `project_id` + `stage`.
"""
from __future__ import annotations

import datetime as dt
import uuid

from pymongo.database import Database

from ..core.rbac import user_level
from .seed import STAGE_PIPELINE, _stages_up_to

_STAGE_KEYS = [s["key"] for s in STAGE_PIPELINE]


def visible_to(user: dict, project: dict) -> bool:
    if user_level(user) >= 3 or user.get("role") == "super_admin":
        return True
    if user["user_id"] in project.get("member_ids", []):
        return True
    if user.get("team_id") in project.get("team_ids", []):
        return True
    return False


def _resolve_members(db: Database, member_ids: list[str]) -> list[dict]:
    rows = db.users.find({"user_id": {"$in": member_ids}},
                         {"user_id": 1, "name": 1, "designation": 1, "team_id": 1})
    by_id = {r["user_id"]: r for r in rows}
    return [
        {"user_id": mid, "name": by_id[mid]["name"],
         "designation": by_id[mid].get("designation"), "team_id": by_id[mid].get("team_id")}
        for mid in member_ids if mid in by_id
    ]


def _summary(db: Database, p: dict) -> dict:
    total_count = db.tasks.count_documents({"project_id": p["project_id"]})
    bug_count = db.tasks.count_documents(
        {"project_id": p["project_id"], "wp_type": {"$regex": "bug", "$options": "i"}})
    task_count = total_count - bug_count
    stage_name = next((s["name"] for s in p.get("stages", []) if s["key"] == p["current_stage"]), None)
    return {
        "project_id": p["project_id"], "code": p["code"], "name": p["name"],
        "client": p.get("client"), "status": p["status"],
        "current_stage": p["current_stage"], "current_stage_name": stage_name,
        "progress": p.get("progress", 0), "expected_progress": p.get("expected_progress"),
        "team_ids": p.get("team_ids", []),
        "members": _resolve_members(db, p.get("member_ids", [])[:6]),
        "member_count": len(p.get("member_ids", [])),
        "bug_count": bug_count, "task_count": task_count,
    }


def list_for_user(db: Database, user: dict) -> list[dict]:
    projects = list(db.projects.find({}))
    visible = [p for p in projects if visible_to(user, p)]
    return [_summary(db, p) for p in visible]


def _task_row(t: dict) -> dict:
    return {
        "task_id": t.get("task_id"), "title": t.get("title"), "status": t.get("status"),
        "wp_type": t.get("wp_type"), "priority": t.get("priority"),
        "assignee_id": t.get("assignee_id"), "assignee": t.get("assignee"),
        "progress": t.get("progress", 0), "due_date": t.get("due_date"),
        "stage": t.get("stage"),
    }


def detail(db: Database, project_id: str) -> dict | None:
    p = db.projects.find_one({"project_id": project_id})
    if not p:
        return None
    tasks = list(db.tasks.find({"project_id": project_id}))
    bugs = [_task_row(t) for t in tasks if "bug" in (t.get("wp_type") or "").lower()]
    regular = [_task_row(t) for t in tasks if "bug" not in (t.get("wp_type") or "").lower()]
    owner = db.users.find_one({"user_id": p.get("owner_id")}, {"user_id": 1, "name": 1})
    return {
        "project_id": p["project_id"], "code": p["code"], "name": p["name"],
        "client": p.get("client"), "status": p["status"],
        "current_stage": p["current_stage"], "stages": p.get("stages", []),
        "progress": p.get("progress", 0), "expected_progress": p.get("expected_progress"),
        "owner": {"user_id": owner["user_id"], "name": owner["name"]} if owner else None,
        "team_ids": p.get("team_ids", []),
        "members": _resolve_members(db, p.get("member_ids", [])),
        "tasks": regular, "bugs": bugs,
    }


def create(db: Database, *, creator: dict, code: str, name: str, client: str,
           team_ids: list[str], member_ids: list[str]) -> dict:
    now = dt.datetime.now(dt.timezone.utc)
    first_stage = _STAGE_KEYS[0]
    member_ids = sorted(set(member_ids) | {creator["user_id"]})
    project = {
        "project_id": "proj_" + uuid.uuid4().hex[:8],
        "code": code, "name": name, "client": client, "status": "pipeline",
        "current_stage": first_stage, "stages": _stages_up_to(first_stage),
        "owner_id": creator["user_id"], "team_ids": team_ids, "member_ids": member_ids,
        "progress": 0, "expected_progress": None, "created_at": now,
    }
    db.projects.insert_one(project)
    project.pop("_id", None)
    return project


def set_stage(db: Database, project_id: str, stage: str, status: str | None = None) -> dict | None:
    if stage not in _STAGE_KEYS:
        raise ValueError(f"unknown stage: {stage}")
    update = {"current_stage": stage, "stages": _stages_up_to(stage)}
    if status:
        update["status"] = status
    db.projects.update_one({"project_id": project_id}, {"$set": update})
    p = db.projects.find_one({"project_id": project_id})
    if not p:
        return None
    p.pop("_id", None)
    return p


def add_members(db: Database, project_id: str, member_ids: list[str]) -> list[str]:
    """Adds member_ids to the project, returning only the ones newly added
    (so the caller notifies just the new joiners, not existing members)."""
    p = db.projects.find_one({"project_id": project_id}, {"member_ids": 1})
    if not p:
        return []
    existing = set(p.get("member_ids", []))
    new_ids = [m for m in member_ids if m not in existing]
    if new_ids:
        db.projects.update_one({"project_id": project_id},
                               {"$addToSet": {"member_ids": {"$each": new_ids}}})
    return new_ids
