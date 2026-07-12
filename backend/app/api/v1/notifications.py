"""Notification center endpoints (PRD NOT-001/003), plus a best-effort SSE
stream for near-real-time delivery. The stream is purely additive: the
client's 10s poll (Layout.tsx) is the reliable path and keeps working
unchanged whether or not the stream connects, reconnects, or errors out —
nothing about it can break the UI.
"""
from __future__ import annotations

import time

import jwt as pyjwt
from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import StreamingResponse
from pymongo.database import Database

from ...core.security import decode_token
from ...services import notifications as notif
from ..deps import get_current_user, get_db

router = APIRouter(tags=["notifications"])

# Module-level so tests can shrink them instead of sleeping for real seconds.
STREAM_INTERVAL_SECONDS = 3.0
STREAM_MAX_TICKS = 1200  # ~1 hour cap at the default interval


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


@router.get("/notifications/stream")
def stream(token: str = Query(...), db: Database = Depends(get_db)) -> StreamingResponse:
    """Server-Sent Events push of the unread count. EventSource can't set an
    Authorization header, so the access token travels as a query param —
    validated the same way get_current_user validates it from the header."""
    try:
        payload = decode_token(token)
    except pyjwt.PyJWTError:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "invalid or expired token")
    if payload.get("type") != "access":
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "wrong token type")
    user_id = payload["sub"]
    requester = db.users.find_one({"user_id": user_id})
    if not requester or requester.get("status") != "active":
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "user not found or inactive")

    def gen():
        last = None
        for _ in range(STREAM_MAX_TICKS):
            try:
                count = notif.unread_count(db, user_id)
            except Exception:  # noqa: BLE001 - a stream hiccup must not 500 the client
                return
            if count != last:
                yield f"data: {{\"count\": {count}}}\n\n"
                last = count
            else:
                yield ": ping\n\n"
            time.sleep(STREAM_INTERVAL_SECONDS)

    return StreamingResponse(gen(), media_type="text/event-stream",
                             headers={"Cache-Control": "no-cache",
                                     "X-Accel-Buffering": "no"})
