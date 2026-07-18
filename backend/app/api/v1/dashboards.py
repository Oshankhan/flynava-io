"""Dashboard endpoints — one per role view, RBAC-gated."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from pymongo.database import Database

from ...services import dashboards
from ..deps import get_current_user, get_db

router = APIRouter(tags=["dashboards"])


@router.get("/dashboards")
def list_dashboards(user: dict = Depends(get_current_user)) -> list[dict]:
    """Dashboards the caller may open (drives the sidebar)."""
    return [{"key": k, "title": v["title"]}
            for k, v in dashboards.DASHBOARDS.items()
            if dashboards.can_view(user, k)]


@router.get("/dashboards/{key}")
def get_dashboard(key: str, project: str | None = None,
                  user: dict = Depends(get_current_user),
                  db: Database = Depends(get_db)) -> dict:
    if key not in dashboards.DASHBOARDS:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "unknown dashboard")
    if not dashboards.can_view(user, key):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "no access to this dashboard")
    if project and not db.projects.find_one(
            {"source_system": "openproject", "source_id": project}):
        raise HTTPException(status.HTTP_404_NOT_FOUND, "unknown project")
    return dashboards.build(db, key, user, project=project)
