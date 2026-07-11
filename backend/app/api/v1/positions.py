"""Open-positions read endpoint (recruitment pipeline — seeded demo data).

Feeds the Recruiter's "which roles are burning" panel and department-head
hiring rollups. Optional `dept` filter narrows to one department.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends
from pymongo.database import Database

from ..deps import get_current_user, get_db

router = APIRouter(tags=["positions"])


@router.get("/positions")
def positions(dept: str | None = None, _: dict = Depends(get_current_user),
              db: Database = Depends(get_db)) -> list[dict]:
    q: dict = {"status": "open"}
    if dept:
        q["dept"] = dept
    return [{k: v for k, v in p.items() if k != "_id"}
            for p in db.positions.find(q).sort("days_open", -1)]
