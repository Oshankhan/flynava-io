"""Meetings endpoints: create (notifies invitees), my calendar, cancel."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field
from pymongo.database import Database

from ...core import audit
from ...services import meetings as meetings_svc
from ..deps import get_current_user, get_db

router = APIRouter(tags=["meetings"])


class MeetingCreate(BaseModel):
    title: str = Field(min_length=1, max_length=200)
    start: str  # ISO "YYYY-MM-DDTHH:MM"
    end: str
    attendee_ids: list[str] = Field(default_factory=list)
    location: str = ""
    agenda: str = ""


@router.post("/meetings")
def create_meeting(body: MeetingCreate, user: dict = Depends(get_current_user),
                   db: Database = Depends(get_db)) -> dict:
    if body.end < body.start:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "end before start")
    meeting = meetings_svc.create(
        db, organizer=user, title=body.title, start=body.start, end=body.end,
        attendee_ids=body.attendee_ids, location=body.location, agenda=body.agenda)
    audit.record(db, actor_id=user["user_id"], action="meeting_created",
                 entity_type="meeting", entity_id=meeting["meeting_id"],
                 meta={"title": body.title, "attendees": len(meeting["attendee_ids"])})
    return meeting


@router.get("/meetings/my")
def my_meetings(start: str | None = Query(default=None),
                end: str | None = Query(default=None),
                user: dict = Depends(get_current_user),
                db: Database = Depends(get_db)) -> list[dict]:
    return meetings_svc.for_user(db, user["user_id"], start=start, end=end)


@router.delete("/meetings/{meeting_id}")
def cancel_meeting(meeting_id: str, user: dict = Depends(get_current_user),
                   db: Database = Depends(get_db)) -> dict:
    if not meetings_svc.cancel(db, meeting_id, user):
        raise HTTPException(status.HTTP_404_NOT_FOUND,
                            "meeting not found or not the organizer")
    audit.record(db, actor_id=user["user_id"], action="meeting_cancelled",
                 entity_type="meeting", entity_id=meeting_id)
    return {"status": "cancelled"}
