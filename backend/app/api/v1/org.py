"""Org hierarchy endpoints: my team/lead, teams directory, members.

Backs the workspace shell (L1 sees own team + lead; L2+ see their members)
and people-pickers (meeting invites, task assignment).
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from pymongo.database import Database

from ...core.rbac import user_level
from ..deps import get_current_user, get_db

router = APIRouter(tags=["org"])

_LITE = {"_id": 0, "user_id": 1, "name": 1, "designation": 1, "team_id": 1,
         "level": 1, "department": 1, "role": 1}


def _user_lite(u: dict | None) -> dict | None:
    if not u:
        return None
    return {k: u.get(k) for k in
            ("user_id", "name", "designation", "team_id", "level", "department", "role")}


def _team_out(db: Database, t: dict) -> dict:
    lead = db.users.find_one({"user_id": t.get("lead_id")}, _LITE)
    return {
        "team_id": t["team_id"], "name": t["name"],
        "department": t.get("department"),
        "lead": _user_lite(lead),
        "member_count": db.users.count_documents(
            {"team_id": t["team_id"], "status": "active"}),
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
