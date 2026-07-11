"""Notification center endpoints (PRD NOT-001/003)."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from pymongo.database import Database

from ...services import notifications as notif
from ..deps import get_current_user, get_db

router = APIRouter(tags=["notifications"])


@router.get("/notifications")
def my_notifications(user: dict = Depends(get_current_user),
                     db: Database = Depends(get_db)) -> list[dict]:
    return notif.for_user(db, user["user_id"])


@router.get("/notifications/unread_count")
def unread(user: dict = Depends(get_current_user),
           db: Database = Depends(get_db)) -> dict:
    return {"count": notif.unread_count(db, user["user_id"])}


@router.post("/notifications/{notif_id}/read")
def read(notif_id: str, user: dict = Depends(get_current_user),
         db: Database = Depends(get_db)) -> dict:
    if not notif.mark_read(db, user["user_id"], notif_id):
        raise HTTPException(status.HTTP_404_NOT_FOUND, "notification not found")
    return {"status": "ok"}
