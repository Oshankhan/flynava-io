"""Integration control: on-demand sync + logs (super_admin only)."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from pymongo.database import Database

from ...core import audit
from ...integrations.registry import get_connector, sources
from ...services.ingest import run_connector
from ..deps import get_db, require_role

router = APIRouter(tags=["integrations"])


@router.get("/integrations")
def list_sources(_: dict = Depends(require_role("super_admin"))) -> dict:
    return {"sources": sources()}


@router.post("/integrations/{source}/sync")
def sync(source: str, user: dict = Depends(require_role("super_admin")),
         db: Database = Depends(get_db)) -> dict:
    connector = get_connector(source)
    if not connector:
        raise HTTPException(status.HTTP_404_NOT_FOUND, f"unknown source {source}")
    log = run_connector(db, connector)
    audit.record(db, actor_id=user["user_id"], action="integration_sync",
                 entity_type="integration", entity_id=source, meta=log)
    return log


@router.get("/integrations/logs")
def logs(source: str | None = None, limit: int = 20,
         _: dict = Depends(require_role("super_admin")),
         db: Database = Depends(get_db)) -> list[dict]:
    q = {"source": source} if source else {}
    out = []
    for row in db.integration_logs.find(q).sort("run_at", -1).limit(limit):
        row["_id"] = str(row["_id"])
        out.append(row)
    return out
