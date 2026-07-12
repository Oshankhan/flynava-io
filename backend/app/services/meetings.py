"""Internal meetings module: create, list, cancel + attendee notifications.

Own collection (`meetings`) with ISO datetimes; Google/Outlook sync can layer
on later as another source the same way integrations do.
"""
from __future__ import annotations

import datetime as dt
import uuid

from pymongo.database import Database

from . import notifications as notif


def _clean(m: dict) -> dict:
    m.pop("_id", None)
    return m


def create(db: Database, *, organizer: dict, title: str, start: str, end: str,
           attendee_ids: list[str], location: str = "", agenda: str = "") -> dict:
    meeting = {
        "meeting_id": uuid.uuid4().hex[:12],
        "title": title,
        "agenda": agenda,
        "start": start,
        "end": end,
        "location": location,
        "organizer_id": organizer["user_id"],
        "organizer_name": organizer["name"],
        "attendee_ids": sorted(set(attendee_ids) | {organizer["user_id"]}),
        "status": "scheduled",
        "created_at": dt.datetime.now(dt.timezone.utc),
    }
    db.meetings.insert_one(meeting)
    day = str(start)[:16].replace("T", " ")
    for uid in meeting["attendee_ids"]:
        if uid != organizer["user_id"]:
            notif.create(db, recipient_id=uid, type="meeting_invite",
                         title=f"Meeting: {title}",
                         body=f"{day} — invited by {organizer['name']}",
                         action_link="/calendar")
    return _clean(meeting)


def for_user(db: Database, user_id: str, *, start: str | None = None,
             end: str | None = None) -> list[dict]:
    q: dict = {"attendee_ids": user_id, "status": "scheduled"}
    if start or end:
        rng: dict = {}
        if start:
            rng["$gte"] = start
        if end:
            rng["$lte"] = end
        q["start"] = rng
    return [_clean(m) for m in db.meetings.find(q).sort("start", 1)]


def upcoming(db: Database, user_id: str, limit: int = 5) -> list[dict]:
    now = dt.datetime.now().isoformat(timespec="minutes")
    return for_user(db, user_id, start=now)[:limit]


def cancel(db: Database, meeting_id: str, user: dict) -> bool:
    m = db.meetings.find_one({"meeting_id": meeting_id, "status": "scheduled"})
    if not m or m["organizer_id"] != user["user_id"]:
        return False
    db.meetings.update_one({"meeting_id": meeting_id},
                           {"$set": {"status": "cancelled"}})
    for uid in m["attendee_ids"]:
        if uid != user["user_id"]:
            notif.create(db, recipient_id=uid, type="meeting_cancelled",
                         title=f"Cancelled: {m['title']}",
                         body=f"By {user['name']}", action_link="/calendar")
    return True


def seed_meetings(db: Database) -> int:
    """Demo meetings around 'today' so calendars look alive. Idempotent-ish:
    replaces prior seeded meetings."""
    db.meetings.delete_many({"seeded": True})
    today = dt.date.today()
    tomorrow = today + dt.timedelta(days=1)

    def iso(day: dt.date, hhmm: str) -> str:
        return f"{day.isoformat()}T{hhmm}"

    team_python = [u["user_id"] for u in db.users.find({"team_id": "team_python"})]
    heads = [u["user_id"] for u in db.users.find({"level": {"$gte": 3}})]
    rows = [
        {"title": "Python Stand-up", "start": iso(today, "10:30"),
         "end": iso(today, "10:45"), "organizer_id": "u_murugan",
         "attendee_ids": team_python, "location": "Meet"},
        {"title": "Finance Sync", "start": iso(today, "10:30"),
         "end": iso(today, "11:00"), "organizer_id": "u_rakshitha",
         "attendee_ids": sorted(set(["u_rakshitha"] + heads)), "location": "Meet"},
        {"title": "Budget Review", "start": iso(today, "14:00"),
         "end": iso(today, "15:00"), "organizer_id": "u_rakshitha",
         "attendee_ids": sorted(set(["u_rakshitha"] + heads)), "location": "Board Room"},
        {"title": "Monthly Reporting", "start": iso(tomorrow, "11:00"),
         "end": iso(tomorrow, "12:00"), "organizer_id": "u_ceo",
         "attendee_ids": heads, "location": "Meet"},
        {"title": "Team Training", "start": iso(tomorrow, "15:30"),
         "end": iso(tomorrow, "16:30"), "organizer_id": "u_murugan",
         "attendee_ids": team_python, "location": "Training Room"},
    ]
    for r in rows:
        org = db.users.find_one({"user_id": r["organizer_id"]}, {"name": 1})
        db.meetings.insert_one({
            "meeting_id": uuid.uuid4().hex[:12], "agenda": "", "status": "scheduled",
            "organizer_name": org["name"] if org else "", "seeded": True,
            "created_at": dt.datetime.now(dt.timezone.utc), **r,
        })
    return len(rows)
