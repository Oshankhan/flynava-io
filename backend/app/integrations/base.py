"""Connector base class. Every integration implements `fetch()`; upsert is shared.

Records are upserted by (source_system, source_id) so re-syncs are idempotent —
this is what lets checkpoint recovery re-run a failed sync without duplicates
(PRD NFR-007).
"""
from __future__ import annotations

from abc import ABC, abstractmethod

from pymongo.database import Database


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
        for t in data.get("tasks", []):
            fetched += 1
            db.tasks.update_one(
                {"source_system": self.source, "source_id": t["source_id"]},
                {"$set": {**t, "source_system": self.source}},
                upsert=True,
            )
            processed += 1
        return fetched, processed
