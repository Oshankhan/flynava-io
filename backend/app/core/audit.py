"""Immutable audit trail writer (PRD SEC-008, ARCH-008)."""
from __future__ import annotations

import datetime as dt

from pymongo.database import Database


def record(db: Database, *, actor_id: str | None, action: str, entity_type: str = "",
           entity_id: str = "", meta: dict | None = None) -> None:
    db.audit_logs.insert_one({
        "actor_id": actor_id,
        "action": action,
        "entity_type": entity_type,
        "entity_id": entity_id,
        "meta": meta or {},
        "created_at": dt.datetime.now(dt.timezone.utc),
    })
