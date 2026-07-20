"""Management Overview — Project Bugs Tracker + Project Report. Fully
live-derived (see services/management.py); gated on operations/product_dev
(non-"own" access) since both screens are project/team-wide views.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pymongo.database import Database

from ...services import management
from ..deps import get_db, require_any_module

router = APIRouter(tags=["management"])

_require_access = require_any_module("operations", "product_dev")


@router.get("/management/bugs")
def get_bugs(preset: str | None = None,
            from_: str | None = Query(None, alias="from"), to: str | None = None,
            project: str | None = None,
            _: dict = Depends(_require_access),
            db: Database = Depends(get_db)) -> dict:
    window = management.resolve_window(preset, from_, to)
    return management.build_bugs(db, window, project)


@router.get("/management/report")
def get_report(project: str, _: dict = Depends(_require_access),
               db: Database = Depends(get_db)) -> dict:
    return management.build_report(db, project)


@router.get("/management/projects")
def get_projects(_: dict = Depends(_require_access), db: Database = Depends(get_db)) -> list[dict]:
    return management.list_projects_for_selector(db)
