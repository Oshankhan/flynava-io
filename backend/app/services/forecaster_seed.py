"""Deterministic demo data for the Financial Forecaster screens.

Consistency over screenshot-fidelity: revenue, expenses, net profit,
expense categories, and headcount are NOT stored here — the service layer
(`services/forecaster.py`) reads them straight from `finance_monthly` /
`org_monthly` (seeded in `success_seed.py`) so Forecaster always agrees
with Finance Performance / Organization Insights for the same month. Only
forecaster-specific figures (cash position, hiring, payments, forecasts)
live in `forecaster_monthly`.

Same idempotent-upsert convention as `success_seed.py`: every write is
`update_one({key}, {"$set": doc}, upsert=True)`, never a blanket delete —
this collection is wholly seed-owned (added to `reset_roster`'s wipe list
in seed.py).
"""
from __future__ import annotations

import datetime as dt
import random

from pymongo.database import Database

from .success_seed import MONTHS_BACK, month_list, series, shift_month

FUTURE_MONTHS = 12  # forward forecast horizon — one fiscal year


def months_forward(anchor: str, n: int) -> list[str]:
    """`n` months after `anchor` (exclusive), nearest first."""
    return [shift_month(anchor, i) for i in range(1, n + 1)]


def seed_forecaster(db: Database, now: dt.datetime) -> None:
    rng = random.Random(20260702)
    cur_month = now.strftime("%Y-%m")
    months = month_list(cur_month, MONTHS_BACK)
    future = months_forward(cur_month, FUTURE_MONTHS)

    fin_by_month = {r["month"]: r for r in
                   db.finance_monthly.find({"month": {"$in": months}}, {"_id": 0})}
    org_by_month = {r["month"]: r for r in
                   db.org_monthly.find({"month": {"$in": months}}, {"_id": 0})}

    cash_balance = series(rng, 100_000_000, mom_pct=5.0, round_to=0)
    cash_in = series(rng, 30_000_000, mom_pct=8.0, round_to=0)
    cash_out = series(rng, 28_000_000, mom_pct=6.0, round_to=0)
    joiners = series(rng, 14, mom_abs=2, floor=0, round_to=0)
    resigned = series(rng, 6, mom_abs=-1, floor=0, round_to=0)
    conversion_rate = series(rng, 71.4, mom_pct=2.0, floor=10.0, round_to=1)
    outstanding_payments = series(rng, 13_200_000, mom_pct=8.0, round_to=0)
    forecast_accuracy = series(rng, 92.7, mom_pct=2.0, floor=50.0, round_to=1)
    health_score = series(rng, 82, mom_abs=3, floor=30, round_to=0)
    pending_count = series(rng, 12, mom_abs=1, floor=0, round_to=0)
    overdue_amount = series(rng, 4_875_000, mom_pct=10.0, floor=0, round_to=0)
    upcoming_due_7d = series(rng, 6_340_000, mom_pct=5.0, floor=0, round_to=0)
    success_rate = series(rng, 88.3, mom_pct=1.5, floor=50.0, round_to=1)

    for i, month in enumerate(months):
        fin = fin_by_month.get(month, {})
        actual_revenue = fin.get("revenue")
        actual_expenses = fin.get("expenses")
        # The forecast that "would have been made" for this historical
        # month — lets past months show a forecast-vs-actual comparison
        # (actual usually a few % above/below what was projected).
        forecast_revenue = (
            round(actual_revenue * (1 + rng.uniform(-0.06, 0.10)))
            if actual_revenue is not None else None
        )
        forecast_expenses = (
            round(actual_expenses * (1 + rng.uniform(-0.05, 0.07)))
            if actual_expenses is not None else None
        )
        sr = success_rate[i]
        status_breakdown = [
            {"status": "Paid", "pct": sr},
            {"status": "Pending", "pct": round((100 - sr) * 0.7, 1)},
            {"status": "Overdue", "pct": round((100 - sr) * 0.3, 1)},
        ]
        db.forecaster_monthly.update_one({"month": month}, {"$set": {
            "month": month,
            "cash_balance": cash_balance[i], "cash_in": cash_in[i], "cash_out": cash_out[i],
            "joiners": int(joiners[i]), "resigned": int(resigned[i]),
            "conversion_rate": conversion_rate[i],
            "outstanding_payments": outstanding_payments[i],
            "forecast_accuracy": forecast_accuracy[i],
            "health_score": int(health_score[i]),
            "forecast_revenue": forecast_revenue,
            "forecast_expenses": forecast_expenses,
            "payments": {
                "pending_count": int(pending_count[i]),
                "overdue_amount": overdue_amount[i],
                "upcoming_due_7d": upcoming_due_7d[i],
                "success_rate": sr,
                "status_breakdown": status_breakdown,
            },
        }}, upsert=True)

    # --- Forward-looking forecast months — projection only, no actuals ---
    cur_fin = fin_by_month.get(cur_month, {})
    cur_org = org_by_month.get(cur_month, {})
    rev = cur_fin.get("revenue") or 280_000_000
    exp = cur_fin.get("expenses") or 160_000_000
    hc = cur_org.get("headcount") or 1200
    cash = cash_balance[-1]

    for month in future:
        rev *= (1 + 0.05) * (1 + rng.uniform(-0.02, 0.02))
        exp *= (1 + 0.045) * (1 + rng.uniform(-0.02, 0.02))
        hc *= 1.01  # ~12%/yr, matching a "12% headcount growth next quarter" narrative
        cash *= (1 + 0.03) * (1 + rng.uniform(-0.02, 0.02))
        # Derive profit from the SAME rounded figures that get stored for
        # revenue/expenses — computing it from the unrounded accumulators
        # instead can be off by a rupee from forecast_revenue - forecast_expenses.
        rev_rounded, exp_rounded = round(rev), round(exp)
        db.forecaster_monthly.update_one({"month": month}, {"$set": {
            "month": month,
            "headcount_forecast": round(hc),
            "forecast_revenue": rev_rounded,
            "forecast_expenses": exp_rounded,
            "forecast_profit": rev_rounded - exp_rounded,
            "forecast_cash_balance": round(cash),
        }}, upsert=True)
