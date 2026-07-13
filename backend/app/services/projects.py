"""Client project + editable-stage service (Team Tasks, project-centric).

New projects start from the shared `STAGE_PIPELINE` template (see
services.seed); once created, a project's `stages` list is its own — fully
editable (add/update/delete) independent of the template. Tasks/bugs
reference a project via `project_id` + `stage`.
"""
from __future__ import annotations

import datetime as dt
import uuid

from pymongo.database import Database

from ..core.rbac import user_level
from .seed import STAGE_PIPELINE, _stages_up_to

_STAGE_KEYS = [s["key"] for s in STAGE_PIPELINE]
_PROJECT_EDITABLE = {"name", "client", "description", "engagement", "priority",
                     "status", "project_manager_id", "start_date", "due_date",
                     "team_ids"}
_STAGE_EDITABLE = {"name", "description", "status", "progress", "start_date", "end_date"}


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


def _resolve_user_lite(db: Database, user_id: str | None) -> dict | None:
    if not user_id:
        return None
    u = db.users.find_one({"user_id": user_id}, {"user_id": 1, "name": 1})
    return {"user_id": u["user_id"], "name": u["name"]} if u else None


def _open_task_count(db: Database, project_id: str) -> int:
    rows = db.tasks.find({"project_id": project_id}, {"wp_type": 1, "progress": 1})
    return sum(1 for t in rows
              if "bug" not in (t.get("wp_type") or "").lower() and t.get("progress", 0) < 100)


def _summary(db: Database, p: dict) -> dict:
    total_count = db.tasks.count_documents({"project_id": p["project_id"]})
    bug_count = db.tasks.count_documents(
        {"project_id": p["project_id"], "wp_type": {"$regex": "bug", "$options": "i"}})
    task_count = total_count - bug_count
    stage_name = next((s["name"] for s in p.get("stages", []) if s["key"] == p["current_stage"]), None)
    return {
        "project_id": p["project_id"], "code": p["code"], "name": p["name"],
        "client": p.get("client"), "status": p["status"], "logo": p.get("logo"),
        "description": p.get("description"), "engagement": p.get("engagement"),
        "priority": p.get("priority"), "start_date": p.get("start_date"),
        "due_date": p.get("due_date"),
        "project_manager": _resolve_user_lite(db, p.get("project_manager_id")),
        "current_stage": p["current_stage"], "current_stage_name": stage_name,
        "progress": p.get("progress", 0), "expected_progress": p.get("expected_progress"),
        "team_ids": p.get("team_ids", []),
        "members": _resolve_members(db, p.get("member_ids", [])[:6]),
        "member_count": len(p.get("member_ids", [])),
        "bug_count": bug_count, "task_count": task_count,
        "open_tasks": _open_task_count(db, p["project_id"]),
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
        "client": p.get("client"), "status": p["status"], "logo": p.get("logo"),
        "description": p.get("description"), "engagement": p.get("engagement"),
        "priority": p.get("priority"), "start_date": p.get("start_date"),
        "due_date": p.get("due_date"),
        "project_manager": _resolve_user_lite(db, p.get("project_manager_id")),
        "current_stage": p["current_stage"], "stages": p.get("stages", []),
        "progress": p.get("progress", 0), "expected_progress": p.get("expected_progress"),
        "owner": {"user_id": owner["user_id"], "name": owner["name"]} if owner else None,
        "team_ids": p.get("team_ids", []),
        "members": _resolve_members(db, p.get("member_ids", [])),
        "tasks": regular, "bugs": bugs,
    }


def create(db: Database, *, creator: dict, code: str, name: str, client: str,
           team_ids: list[str], member_ids: list[str], description: str = "",
           engagement: str = "", priority: str = "Medium",
           project_manager_id: str | None = None, start_date: str | None = None,
           due_date: str | None = None) -> dict:
    now = dt.datetime.now(dt.timezone.utc)
    first_stage = _STAGE_KEYS[0]
    member_ids = sorted(set(member_ids) | {creator["user_id"]})
    project = {
        "project_id": "proj_" + uuid.uuid4().hex[:8],
        "code": code, "name": name, "client": client, "status": "planning",
        "description": description, "engagement": engagement, "priority": priority,
        "project_manager_id": project_manager_id or creator["user_id"],
        "start_date": start_date, "due_date": due_date,
        "current_stage": first_stage, "stages": _stages_up_to(first_stage),
        "owner_id": creator["user_id"], "team_ids": team_ids, "member_ids": member_ids,
        "progress": 0, "expected_progress": None, "created_at": now,
    }
    db.projects.insert_one(project)
    project.pop("_id", None)
    return project


def update(db: Database, project_id: str, fields: dict) -> dict | None:
    patch = {k: v for k, v in fields.items() if k in _PROJECT_EDITABLE and v is not None}
    if patch:
        db.projects.update_one({"project_id": project_id}, {"$set": patch})
    p = db.projects.find_one({"project_id": project_id})
    if not p:
        return None
    p.pop("_id", None)
    return p


def _recompute(db: Database, project_id: str) -> None:
    """Overall progress = mean of stage progress; current_stage = the first
    stage that isn't done (or the last stage if every stage is done)."""
    p = db.projects.find_one({"project_id": project_id}, {"stages": 1})
    stages = p.get("stages", []) if p else []
    if not stages:
        return
    progress = round(sum(s.get("progress", 0) for s in stages) / len(stages))
    current = next((s["key"] for s in stages if s.get("status") != "done"), stages[-1]["key"])
    db.projects.update_one({"project_id": project_id},
                           {"$set": {"progress": progress, "current_stage": current}})


def add_stage(db: Database, project_id: str, *, key: str, name: str, description: str = "",
             status: str = "pending", progress: int = 0, start_date: str | None = None,
             end_date: str | None = None) -> dict | None:
    p = db.projects.find_one({"project_id": project_id}, {"stages": 1})
    if not p:
        return None
    if any(s["key"] == key for s in p.get("stages", [])):
        raise ValueError(f"stage key already exists: {key}")
    stage = {"key": key, "name": name, "description": description, "status": status,
             "progress": progress, "start_date": start_date, "end_date": end_date,
             "owner_team": ""}
    db.projects.update_one({"project_id": project_id}, {"$push": {"stages": stage}})
    _recompute(db, project_id)
    updated = db.projects.find_one({"project_id": project_id})
    updated.pop("_id", None)
    return updated


def update_stage(db: Database, project_id: str, stage_key: str, fields: dict) -> dict | None:
    p = db.projects.find_one({"project_id": project_id}, {"stages": 1})
    if not p or not any(s["key"] == stage_key for s in p.get("stages", [])):
        return None
    patch = {f"stages.$.{k}": v for k, v in fields.items()
            if k in _STAGE_EDITABLE and v is not None}
    if patch:
        db.projects.update_one(
            {"project_id": project_id, "stages.key": stage_key}, {"$set": patch})
    _recompute(db, project_id)
    updated = db.projects.find_one({"project_id": project_id})
    updated.pop("_id", None)
    return updated


def delete_stage(db: Database, project_id: str, stage_key: str) -> dict | None:
    p = db.projects.find_one({"project_id": project_id}, {"stages": 1})
    if not p:
        return None
    db.projects.update_one({"project_id": project_id},
                           {"$pull": {"stages": {"key": stage_key}}})
    _recompute(db, project_id)
    updated = db.projects.find_one({"project_id": project_id})
    updated.pop("_id", None)
    return updated


def delete(db: Database, project_id: str) -> bool:
    """Permanently removes a project and everything scoped to it (tasks,
    documents, CRM contacts, invoices). Irreversible — callers must gate
    this to a trusted role."""
    if not db.projects.find_one({"project_id": project_id}, {"_id": 1}):
        return False
    db.tasks.delete_many({"project_id": project_id})
    db.documents.delete_many({"project_id": project_id})
    db.crm_contacts.delete_many({"project_id": project_id})
    db.project_invoices.delete_many({"project_id": project_id})
    db.projects.delete_one({"project_id": project_id})
    return True


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
