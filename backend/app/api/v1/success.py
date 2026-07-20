"""Indicator Of Success — 6 KPI dashboard screens. Each endpoint returns a
plain-dict payload built by `services/success.py` from month-keyed rollup
collections seeded in `services/success_seed.py`.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pymongo.database import Database

from ...core import rbac
from ...services import success
from ..deps import get_current_user, get_db, has_aggregate_access, require_any_module

router = APIRouter(tags=["success"])


def _require_startup_access(user: dict = Depends(get_current_user)) -> dict:
    if has_aggregate_access(user, "finance") or rbac.user_level(user) >= 4:
        return user
    raise HTTPException(status.HTTP_403_FORBIDDEN, "no access to startup metrics")


@router.get("/success/central")
def get_central(month: str | None = None,
                from_: str | None = Query(None, alias="from"), to: str | None = None,
                _: dict = Depends(require_any_module(
                    "operations", "hr", "finance", "marketing_sales")),
                db: Database = Depends(get_db)) -> dict:
    period = success.resolve_period(month, from_, to)
    return success.build_central(db, period)


@router.get("/success/organization")
def get_organization(month: str | None = None,
                     _: dict = Depends(require_any_module("hr")),
                     db: Database = Depends(get_db)) -> dict:
    period = success.resolve_period(month)
    return success.build_organization(db, period)


@router.get("/success/marketing")
def get_marketing(month: str | None = None,
                  _: dict = Depends(require_any_module("marketing_sales")),
                  db: Database = Depends(get_db)) -> dict:
    period = success.resolve_period(month)
    return success.build_marketing(db, period)


@router.get("/success/finance")
def get_finance(month: str | None = None, granularity: str = "monthly",
                _: dict = Depends(require_any_module("finance")),
                db: Database = Depends(get_db)) -> dict:
    if granularity not in ("monthly", "yearly"):
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY,
                            "granularity must be 'monthly' or 'yearly'")
    period = success.resolve_period(month)
    return success.build_finance(db, period, granularity)


@router.get("/success/startup")
def get_startup(month: str | None = None,
                _: dict = Depends(_require_startup_access),
                db: Database = Depends(get_db)) -> dict:
    period = success.resolve_period(month)
    return success.build_startup(db, period)


@router.get("/success/operations")
def get_operations(month: str | None = None,
                   _: dict = Depends(require_any_module("operations")),
                   db: Database = Depends(get_db)) -> dict:
    period = success.resolve_period(month)
    return success.build_operations(db, period)
