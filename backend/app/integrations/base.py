"""Connector base class. Every integration implements `fetch()`; upsert is shared.

Records are upserted by (source_system, source_id) so re-syncs are idempotent —
this is what lets checkpoint recovery re-run a failed sync without duplicates
(PRD NFR-007).
"""
from __future__ import annotations

import datetime as dt
import re
from abc import ABC, abstractmethod

from pymongo.database import Database

STATUS_HISTORY_CAP = 20
_REOPEN_RE = re.compile(r"reopen", re.IGNORECASE)


class Connector(ABC):
    source: str  # e.g. "openproject"

    @abstractmethod
    def fetch(self) -> dict:
        """Return {"projects": [...], "tasks": [...]} in IO's normalized shape."""
        raise NotImplementedError

    def upsert(self, db: Database, data: dict) -> tuple[int, int]:
        fetched = processed = 0
        for p in data.get("projects", []):
            fetched += 1
            db.projects.update_one(
                {"source_system": self.source, "source_id": p["source_id"]},
                {"$set": {**p, "source_system": self.source}},
                upsert=True,
            )
            processed += 1

        tasks = data.get("tasks", [])
        # One batched pre-read of every task's current status, so detecting a
        # status change (Open -> Reopen, etc.) costs one query per sync
        # instead of one per task. Only tasks that already existed before this
        # sync count as a "transition" — a brand-new task's first-ever status
        # isn't a change from anything, so it doesn't spam status_history or
        # (if a work item happens to be created already in a Reopen-like
        # state) inflate reopen_count.
        prev_status: dict[str, str | None] = {}
        if tasks:
            source_ids = [t["source_id"] for t in tasks]
            prev_status = {
                row["source_id"]: row.get("status")
                for row in db.tasks.find(
                    {"source_system": self.source, "source_id": {"$in": source_ids}},
                    {"source_id": 1, "status": 1},
                )
            }

        for t in tasks:
            fetched += 1
            update: dict = {"$set": {**t, "source_system": self.source}}
            if t["source_id"] in prev_status:
                old_status, new_status = prev_status[t["source_id"]], t.get("status")
                if old_status != new_status:
                    now = dt.datetime.now(dt.timezone.utc)
                    update["$push"] = {"status_history": {
                        "$each": [{"from": old_status, "to": new_status, "at": now}],
                        "$slice": -STATUS_HISTORY_CAP,
                    }}
                    if new_status and _REOPEN_RE.search(new_status):
                        update["$inc"] = {"reopen_count": 1}
            db.tasks.update_one(
                {"source_system": self.source, "source_id": t["source_id"]},
                update,
                upsert=True,
            )
            processed += 1
        return fetched, processed
