"""Notification creation + dispatch record (PRD module 10.10).

In-app is written to the `notifications` collection. Email/push channels are
recorded here too (delivery adapters plug in later); the Notification Log
(NOT-005) reads this collection.
"""
from __future__ import annotations

import datetime as dt
import uuid

from pymongo.database import Database


def create(db: Database, *, recipient_id: str, type: str, title: str,
           body: str = "", channel: str = "in_app", action_link: str = "") -> dict:
    doc = {
        "notif_id": uuid.uuid4().hex,
        "recipient_id": recipient_id,
        "type": type,
        "title": title,
        "body": body,
        "channel": channel,
        "action_link": action_link,
        "status": "unread",
        "created_at": dt.datetime.now(dt.timezone.utc),
        "read_at": None,
    }
    db.notifications.insert_one(doc)
    doc.pop("_id", None)
    return doc


def for_user(db: Database, user_id: str, limit: int = 50) -> list[dict]:
    out = []
    for n in db.notifications.find({"recipient_id": user_id}).sort("created_at", -1).limit(limit):
        n["_id"] = str(n["_id"])
        out.append(n)
    return out


def unread_count(db: Database, user_id: str) -> int:
    return db.notifications.count_documents({"recipient_id": user_id, "status": "unread"})


def mark_read(db: Database, user_id: str, notif_id: str) -> bool:
    res = db.notifications.update_one(
        {"notif_id": notif_id, "recipient_id": user_id},
        {"$set": {"status": "read", "read_at": dt.datetime.now(dt.timezone.utc)}},
    )
    return res.matched_count == 1
