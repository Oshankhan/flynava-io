"""Compliance calendar read endpoint (GST/PF-ESI/ISO deadlines etc.).

Feeds Ask IO evidence (services/seed.py) and the Finance/Compliance dept
panels — any authenticated user may read it (it's a shared company calendar,
not sensitive per-user data).
"""
from __future__ import annotations

from fastapi import APIRouter, Depends
from pymongo.database import Database

from ..deps import get_current_user, get_db

router = APIRouter(tags=["compliance"])


@router.get("/compliance/items")
def compliance_items(_: dict = Depends(get_current_user),
                     db: Database = Depends(get_db)) -> list[dict]:
    return [{k: v for k, v in c.items() if k != "_id"}
            for c in db.compliance_items.find().sort("due_date", 1)]
