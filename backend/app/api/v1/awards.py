"""Awards & Recognition module (PRD 10.9)."""
from __future__ import annotations

import datetime as dt
import uuid
from collections import Counter

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from pymongo.database import Database

from ...core import audit, rbac
from ...services import notifications as notif
from ..deps import get_current_user, get_db, require_role

router = APIRouter(tags=["awards"])

CATEGORIES = ["Employee of the Month", "Team of the Quarter", "Innovation Award",
              "Years of Service"]
CREATORS = ("super_admin", "leadership", "manager", "hr")


class AwardIn(BaseModel):
    recipient_id: str
    title: str
    description: str = ""
    category: str = "Innovation Award"


class ReactionIn(BaseModel):
    type: str  # like | celebrate | clap


@router.get("/awards/categories")
def categories(_: dict = Depends(get_current_user)) -> list[str]:
    return CATEGORIES


@router.get("/awards")
def list_awards(user: dict = Depends(get_current_user),
                db: Database = Depends(get_db)) -> list[dict]:
    if not rbac.has_access(user["role"], "awards"):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "no access to awards")
    out = []
    for a in db.recognitions.find().sort("awarded_at", -1).limit(50):
        a["_id"] = str(a["_id"])
        out.append(a)
    return out


@router.post("/awards")
def create_award(body: AwardIn, user: dict = Depends(require_role(*CREATORS)),
                 db: Database = Depends(get_db)) -> dict:
    recipient = db.users.find_one({"user_id": body.recipient_id}, {"password_hash": 0})
    if not recipient:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "recipient not found")
    doc = {
        "award_id": uuid.uuid4().hex,
        "recipient_id": body.recipient_id,
        "issuer_id": user["user_id"],
        "category": body.category,
        "title": body.title,
        "description": body.description,
        "awarded_at": dt.datetime.now(dt.timezone.utc),
        "reactions": {},
    }
    db.recognitions.insert_one(doc)
    doc.pop("_id", None)
    # AWR-005: notify the recipient
    notif.create(db, recipient_id=body.recipient_id, type="recognition",
                 title=f"You received: {body.title}",
                 body=f"{body.category} — {body.description}", action_link="/awards")
    audit.record(db, actor_id=user["user_id"], action="award_issued",
                 entity_type="recognition", entity_id=doc["award_id"])
    return doc


@router.post("/awards/{award_id}/react")
def react(award_id: str, body: ReactionIn, user: dict = Depends(get_current_user),
          db: Database = Depends(get_db)) -> dict:
    if not rbac.has_access(user["role"], "awards"):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "no access to awards")
    res = db.recognitions.update_one(
        {"award_id": award_id}, {"$inc": {f"reactions.{body.type}": 1}})
    if res.matched_count != 1:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "award not found")
    return {"status": "ok"}


@router.get("/awards/leaderboard")
def leaderboard(user: dict = Depends(get_current_user),
                db: Database = Depends(get_db)) -> list[dict]:
    if not rbac.has_access(user["role"], "awards"):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "no access to awards")
    counts = Counter(a["recipient_id"] for a in db.recognitions.find({}, {"recipient_id": 1}))
    out = []
    for uid, n in counts.most_common(10):
        u = db.users.find_one({"user_id": uid}, {"name": 1})
        out.append({"recipient_id": uid, "name": u["name"] if u else uid, "count": n})
    return out
