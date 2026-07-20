"""Financial Forecaster — executive summary + 5 drill-down screens. Whole
module gated on the `finance` module (non-"own" access) since every screen
here is a company-wide financial view.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends
from pymongo.database import Database

from ...services import forecaster
from ..deps import get_db, require_any_module

router = APIRouter(tags=["forecaster"])

_require_finance = require_any_module("finance")


@router.get("/forecaster/overview")
def get_overview(month: str | None = None, _: dict = Depends(_require_finance),
                 db: Database = Depends(get_db)) -> dict:
    return forecaster.build_overview(db, forecaster.resolve_period(month))


@router.get("/forecaster/workforce")
def get_workforce(month: str | None = None, _: dict = Depends(_require_finance),
                  db: Database = Depends(get_db)) -> dict:
    return forecaster.build_workforce(db, forecaster.resolve_period(month))


@router.get("/forecaster/revenue")
def get_revenue(month: str | None = None, _: dict = Depends(_require_finance),
                db: Database = Depends(get_db)) -> dict:
    return forecaster.build_revenue(db, forecaster.resolve_period(month))


@router.get("/forecaster/cashflow")
def get_cashflow(month: str | None = None, _: dict = Depends(_require_finance),
                 db: Database = Depends(get_db)) -> dict:
    return forecaster.build_cashflow(db, forecaster.resolve_period(month))


@router.get("/forecaster/costs")
def get_costs(month: str | None = None, _: dict = Depends(_require_finance),
              db: Database = Depends(get_db)) -> dict:
    return forecaster.build_costs(db, forecaster.resolve_period(month))


@router.get("/forecaster/analyzer")
def get_analyzer(month: str | None = None, _: dict = Depends(_require_finance),
                 db: Database = Depends(get_db)) -> dict:
    return forecaster.build_analyzer(db, forecaster.resolve_period(month))
