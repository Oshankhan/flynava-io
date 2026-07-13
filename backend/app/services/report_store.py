"""Report visibility + CRUD-support helpers.

Extends the folder role/team access model from `api/v1/documents.py` with an
explicit `visibility` enum (org/restricted/private — a folder's "empty access
= everyone" default is wrong for a personal report) plus a confidential tier
for salary/finance/AWS-billing reports. `shared_with` always overrides, same
as documents.
"""
from __future__ import annotations

from pymongo.database import Database

from ..core.rbac import user_level, user_roles


def is_ceo_tier(user: dict) -> bool:
    return user.get("role") in ("super_admin", "leadership") or user_level(user) >= 4


def is_manager(user: dict) -> bool:
    return user_level(user) >= 3 or user.get("role") == "super_admin"


def report_visible(user: dict, rd: dict) -> bool:
    uid = user["user_id"]
    if uid in (rd.get("shared_with") or []):
        return True
    if is_ceo_tier(user):
        return True
    if rd.get("confidential"):
        return uid == rd.get("owner_id") or uid in (rd.get("allowed_user_ids") or [])
    visibility = rd.get("visibility", "org")
    if visibility == "private":
        return uid == rd.get("owner_id")
    if visibility == "restricted":
        if is_manager(user):
            return True
        access = rd.get("access") or {}
        roles, teams = access.get("roles") or [], access.get("teams") or []
        if any(r in roles for r in user_roles(user)):
            return True
        if user.get("team_id") in teams:
            return True
        return uid == rd.get("owner_id")
    return True  # org


def visible_defs(db: Database, user: dict, query: dict | None = None) -> list[dict]:
    rows = db.report_defs.find(query or {})
    return [rd for rd in rows if report_visible(user, rd)]


def can_create(user: dict, visibility: str, confidential: bool, has_schedule: bool) -> bool:
    level = user_level(user)
    if confidential and not (level >= 3 or user.get("role") == "hr"):
        return False
    if (visibility != "private" or has_schedule) and level < 2:
        return False
    return True


def can_edit(user: dict, rd: dict) -> bool:
    if user["user_id"] == rd.get("owner_id"):
        return True
    if rd.get("confidential"):
        return is_ceo_tier(user)
    return is_manager(user)


def can_delete(user: dict, rd: dict) -> bool:
    return user["user_id"] == rd.get("owner_id") or user.get("role") == "super_admin"


def _owner_names(db: Database, owner_ids: list[str]) -> dict[str, str]:
    if not owner_ids:
        return {}
    rows = db.users.find({"user_id": {"$in": owner_ids}}, {"user_id": 1, "name": 1})
    return {r["user_id"]: r["name"] for r in rows}


def public_many(db: Database, rds: list[dict], user: dict) -> list[dict]:
    """Shapes many defs for API output in a fixed number of queries (owner
    names + last-run status batched), not one query per def."""
    if not rds:
        return []
    owner_ids = list({rd["owner_id"] for rd in rds if rd.get("owner_id")})
    names = _owner_names(db, owner_ids)
    report_ids = [rd["report_id"] for rd in rds]
    last_by_report: dict[str, dict] = {}
    for run in db.report_runs.find(
        {"report_id": {"$in": report_ids}}, {"report_id": 1, "at": 1, "status": 1}
    ).sort("at", -1):
        last_by_report.setdefault(run["report_id"], run)

    out = []
    for rd in rds:
        o = {k: v for k, v in rd.items() if k != "_id"}
        o["owner_name"] = names.get(rd.get("owner_id"), rd.get("owner_id"))
        o["is_mine"] = rd.get("owner_id") == user["user_id"]
        last = last_by_report.get(rd["report_id"])
        o["last_run_at"] = last["at"] if last else None
        o["last_run_status"] = last["status"] if last else None
        out.append(o)
    return out


def public(db: Database, rd: dict, user: dict) -> dict:
    return public_many(db, [rd], user)[0]
