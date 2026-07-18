"""Small helpers shared by more than one detector module."""
from __future__ import annotations

from pymongo.database import Database


def project_names(db: Database) -> dict[str, str]:
    out: dict[str, str] = {}
    for p in db.projects.find({}, {"source_id": 1, "project_id": 1, "name": 1}):
        for key in (p.get("source_id"), p.get("project_id")):
            if key:
                out[str(key)] = p.get("name", "")
    return out


def task_project(t: dict, pnames: dict[str, str]) -> str:
    pid = t.get("project_source_id") or t.get("project_id")
    return pnames.get(str(pid), "") if pid else ""


def who(t: dict) -> str:
    return t.get("assignee") or t.get("assignee_id") or "Unassigned"
