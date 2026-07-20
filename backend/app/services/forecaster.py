"""Payload builders for the "Financial Forecaster" screens (Overview,
Workforce, Revenue, Cashflow, Costs, Finance Analyzer).

Consistency over screenshot-fidelity: revenue/expenses/net profit/expense
categories/headcount are read straight from `finance_monthly`/`org_monthly`
(the same collections Finance Performance / Organization Insights use) —
never re-stored here — so this module always agrees with those screens for
the same month. Only forecaster-specific figures (cash position, hiring,
payments, forward projections) live in `forecaster_monthly`
(`services/forecaster_seed.py`).

Reuses `services/success.py`'s period/card primitives (`resolve_period`,
`months_back`, `prev_month`, `mom_card`) rather than duplicating them —
those are generic "month-keyed rollup" helpers, not success-screen-specific.
"""
from __future__ import annotations

import datetime as dt

from pymongo.database import Database

from .forecaster_seed import FUTURE_MONTHS, months_forward
from .success import Period, mom_card, months_back, prev_month, resolve_period  # noqa: F401

__all__ = ["resolve_period", "Period", "build_overview", "build_workforce",
          "build_revenue", "build_cashflow", "build_costs", "build_analyzer"]


def _delta(cur: float | None, prev: float | None) -> float | None:
    if cur is None or prev is None or prev == 0:
        return None
    return round((cur - prev) / abs(prev) * 100, 1)


def _spark(db: Database, coll: str, months: list[str], field: str) -> list[dict]:
    rows = {r["month"]: r.get(field) for r in
            db[coll].find({"month": {"$in": months}}, {"month": 1, field: 1})}
    return [{"t": m, "v": rows[m]} for m in months if rows.get(m) is not None]


def _now_iso() -> str:
    return dt.datetime.now(dt.timezone.utc).isoformat()


def _fy_label(future_months: list[str]) -> str:
    if not future_months:
        return ""
    start_year, end_year = int(future_months[0][:4]), int(future_months[-1][:4])
    if start_year == end_year:
        return f"FY {start_year}"
    return f"FY {start_year}-{str(end_year)[-2:]}"


# --- Executive Insights / Alerts (derived rules, not LLM — see plan) ---
def _executive_insights(db: Database, month: str) -> list[str]:
    fin = db.finance_monthly.find_one({"month": month}, {"_id": 0}) or {}
    fin_prev = db.finance_monthly.find_one({"month": prev_month(month)}, {"_id": 0}) or {}
    org = db.org_monthly.find_one({"month": month}, {"_id": 0}) or {}
    fc = db.forecaster_monthly.find_one({"month": month}, {"_id": 0}) or {}
    mkt = db.marketing_monthly.find_one({"month": month}, {"_id": 0}) or {}

    bullets: list[str] = []

    rev_delta = _delta(fin.get("revenue"), fin_prev.get("revenue"))
    if rev_delta is not None:
        direction = "increased" if rev_delta >= 0 else "decreased"
        bullets.append(f"Revenue {direction} {abs(rev_delta)}% compared to last month.")

    categories, total_exp = fin.get("expense_breakdown", []), fin.get("expenses")
    if categories and total_exp:
        top = max(categories, key=lambda c: c["amount"])
        pct = round(top["amount"] / total_exp * 100, 1)
        bullets.append(f"{top['category']} is the largest expense category at {pct}% of total expenses.")

    cash_balance, cash_out = fc.get("cash_balance"), fc.get("cash_out")
    if cash_balance and cash_out:
        runway = round(cash_balance / cash_out, 1)
        bullets.append(f"Cash reserves are sufficient for the next {runway} months at the current burn rate.")

    today = dt.date.today().isoformat()
    week_ahead = (dt.date.today() + dt.timedelta(days=7)).isoformat()
    due_soon = db.project_invoices.count_documents({
        "status": {"$in": ["pending", "overdue"]}, "due_date": {"$gte": today, "$lte": week_ahead}})
    if due_soon:
        bullets.append(f"{due_soon} payment(s) are due within 7 days.")

    hc_now = org.get("headcount")
    future = months_forward(month, 3)
    hc_future_doc = (db.forecaster_monthly.find_one({"month": future[-1]}, {"_id": 0})
                     if future else None)
    hc_future = hc_future_doc.get("headcount_forecast") if hc_future_doc else None
    if hc_now and hc_future:
        growth = round((hc_future - hc_now) / hc_now * 100, 1)
        bullets.append(f"Workforce is projected to grow {growth}% over the next quarter.")

    channels = mkt.get("channels", [])
    if channels:
        best = max(channels, key=lambda c: c.get("roi", 0))
        bullets.append(f"{best['channel']} is generating the highest marketing ROI ({best['roi']}%).")

    return bullets


def _executive_alerts(db: Database, month: str) -> list[dict]:
    fin = db.finance_monthly.find_one({"month": month}, {"_id": 0}) or {}
    fin_prev = db.finance_monthly.find_one({"month": prev_month(month)}, {"_id": 0}) or {}
    fc = db.forecaster_monthly.find_one({"month": month}, {"_id": 0}) or {}

    alerts: list[dict] = []

    rev_growth = _delta(fin.get("revenue"), fin_prev.get("revenue"))
    exp_growth = _delta(fin.get("expenses"), fin_prev.get("expenses"))
    if rev_growth is not None and exp_growth is not None and exp_growth > rev_growth:
        alerts.append({"severity": "high", "title": "High Spending",
                       "detail": f"Expenses grew {exp_growth}% vs revenue growth of {rev_growth}%."})

    cash_balance, cash_out = fc.get("cash_balance"), fc.get("cash_out")
    if cash_balance and cash_out:
        runway = cash_balance / cash_out
        if runway < 6:
            alerts.append({"severity": "medium", "title": "Low Cash Warning",
                           "detail": f"Cash balance covers ~{round(runway, 1)} months at current burn."})

    actual_rev, forecast_rev = fin.get("revenue"), fc.get("forecast_revenue")
    gap = _delta(actual_rev, forecast_rev) if forecast_rev else None
    if gap is not None and gap < 0:
        alerts.append({"severity": "high", "title": "Revenue Below Target",
                       "detail": f"Actual revenue is {abs(gap)}% below forecast."})

    pending_n = db.project_invoices.count_documents({"status": "pending"})
    if pending_n:
        alerts.append({"severity": "low", "title": "Pending Payments",
                       "detail": f"{pending_n} payment(s) pending approval."})

    overdue = list(db.project_invoices.find({"status": "overdue"}))
    if overdue:
        overdue_total = sum(i.get("amount", 0) for i in overdue)
        alerts.append({"severity": "high", "title": "Overdue Payments",
                       "detail": f"{len(overdue)} invoice(s) totaling {overdue_total:,.0f} overdue."})

    return alerts


# --- Overview ---
def build_overview(db: Database, period: Period) -> dict:
    month = period.month
    hist = months_back(month, 6)
    fin = db.finance_monthly.find_one({"month": month}, {"_id": 0}) or {}
    fin_prev = db.finance_monthly.find_one({"month": prev_month(month)}, {"_id": 0}) or {}
    org = db.org_monthly.find_one({"month": month}, {"_id": 0}) or {}
    org_prev = db.org_monthly.find_one({"month": prev_month(month)}, {"_id": 0}) or {}
    fc = db.forecaster_monthly.find_one({"month": month}, {"_id": 0}) or {}
    fc_prev = db.forecaster_monthly.find_one({"month": prev_month(month)}, {"_id": 0}) or {}

    health_value = fc.get("health_score")
    health_band = None
    if health_value is not None:
        health_band = "Healthy" if health_value >= 70 else "Watch" if health_value >= 50 else "At Risk"
    health_card = mom_card("health_score", "Financial Health Score", health_value, "score",
                          fc_prev.get("health_score"))
    health_card["band"] = health_band

    cards = [
        mom_card("total_revenue", "Total Revenue", fin.get("revenue"), "inr",
                fin_prev.get("revenue"), link="/forecaster/revenue"),
        mom_card("total_expenses", "Total Expenses", fin.get("expenses"), "inr",
                fin_prev.get("expenses"), higher_is_better=False, link="/forecaster/costs"),
        mom_card("net_profit", "Net Profit", fin.get("net_profit"), "inr", fin_prev.get("net_profit")),
        mom_card("cash_balance", "Cash Balance", fc.get("cash_balance"), "inr",
                fc_prev.get("cash_balance"), link="/forecaster/cashflow"),
        mom_card("total_employees", "Total Employees", org.get("headcount"), "count",
                org_prev.get("headcount"), link="/forecaster/workforce"),
        mom_card("outstanding_payments", "Outstanding Payments", fc.get("outstanding_payments"),
                "inr", fc_prev.get("outstanding_payments"), higher_is_better=False,
                link="/forecaster/analyzer"),
        mom_card("forecast_accuracy", "Forecast Accuracy", fc.get("forecast_accuracy"), "pct",
                fc_prev.get("forecast_accuracy")),
        health_card,
    ]

    revenue_panel = {
        "this_month": fin.get("revenue"), "mom_pct": _delta(fin.get("revenue"), fin_prev.get("revenue")),
        "forecast_this_month": fc.get("forecast_revenue"),
        "vs_forecast_pct": _delta(fin.get("revenue"), fc.get("forecast_revenue")),
        "trend": _spark(db, "finance_monthly", hist, "revenue"),
    }
    workforce_panel = {
        "total_employees": org.get("headcount"), "new_joiners": fc.get("joiners"),
        "resigned": fc.get("resigned"), "conversion_rate": fc.get("conversion_rate"),
        "trend": _spark(db, "org_monthly", hist, "headcount"),
    }
    top_categories = sorted(fin.get("expense_breakdown", []),
                           key=lambda c: c["amount"], reverse=True)[:5]
    costs_panel = {
        "total_expenses": fin.get("expenses"),
        "mom_pct": _delta(fin.get("expenses"), fin_prev.get("expenses")),
        "top_categories": top_categories,
    }
    cash_in, cash_out = fc.get("cash_in"), fc.get("cash_out")
    net_cash_flow = (cash_in - cash_out) if cash_in is not None and cash_out is not None else None
    cashflow_panel = {
        "cash_balance": fc.get("cash_balance"), "net_cash_flow": net_cash_flow,
        "trend": _spark(db, "forecaster_monthly", hist, "cash_balance"),
    }
    payments = fc.get("payments", {})
    analyzer_panel = {
        "pending_count": payments.get("pending_count"),
        "overdue_amount": payments.get("overdue_amount"),
        "upcoming_due_7d": payments.get("upcoming_due_7d"),
        "success_rate": payments.get("success_rate"),
        "status_breakdown": payments.get("status_breakdown", []),
    }

    future_months = months_forward(month, FUTURE_MONTHS)
    future_docs = {r["month"]: r for r in
                  db.forecaster_monthly.find({"month": {"$in": future_months}}, {"_id": 0})}
    future_rows = [future_docs[m] for m in future_months if m in future_docs]

    fy_revenue = sum(r.get("forecast_revenue", 0) for r in future_rows) if future_rows else None
    fy_expenses = sum(r.get("forecast_expenses", 0) for r in future_rows) if future_rows else None
    fy_profit = (fy_revenue - fy_expenses) if fy_revenue is not None and fy_expenses is not None else None
    fy_cash_balance = future_rows[-1].get("forecast_cash_balance") if future_rows else None

    run_rate_revenue = fin.get("revenue") * 12 if fin.get("revenue") is not None else None
    run_rate_expenses = fin.get("expenses") * 12 if fin.get("expenses") is not None else None
    run_rate_profit = fin.get("net_profit") * 12 if fin.get("net_profit") is not None else None
    run_rate_cash = fc.get("cash_balance")

    forecast_cards = [
        mom_card("revenue_forecast", "Revenue Forecast", fy_revenue, "inr", run_rate_revenue,
                spark=[{"t": r["month"], "v": r.get("forecast_revenue")} for r in future_rows]),
        mom_card("expense_forecast", "Expense Forecast", fy_expenses, "inr", run_rate_expenses,
                higher_is_better=False,
                spark=[{"t": r["month"], "v": r.get("forecast_expenses")} for r in future_rows]),
        mom_card("profit_forecast", "Profit Forecast", fy_profit, "inr", run_rate_profit,
                spark=[{"t": r["month"], "v": r.get("forecast_profit")} for r in future_rows]),
        mom_card("cash_balance_forecast", "Cash Balance Forecast", fy_cash_balance, "inr",
                run_rate_cash,
                spark=[{"t": r["month"], "v": r.get("forecast_cash_balance")} for r in future_rows]),
    ]

    return {
        "month": month, "cards": cards,
        "panels": {
            "revenue": revenue_panel, "workforce": workforce_panel, "costs": costs_panel,
            "cashflow": cashflow_panel, "analyzer": analyzer_panel,
        },
        "insights": _executive_insights(db, month),
        "alerts": _executive_alerts(db, month),
        "forecast_cards": forecast_cards,
        "forecast_label": _fy_label(future_months),
        "last_updated": _now_iso(),
    }


# --- Workforce ---
def build_workforce(db: Database, period: Period) -> dict:
    month = period.month
    hist = months_back(month, 12)
    org = db.org_monthly.find_one({"month": month}, {"_id": 0}) or {}
    org_prev = db.org_monthly.find_one({"month": prev_month(month)}, {"_id": 0}) or {}
    fc = db.forecaster_monthly.find_one({"month": month}, {"_id": 0}) or {}
    fc_prev = db.forecaster_monthly.find_one({"month": prev_month(month)}, {"_id": 0}) or {}

    cards = [
        mom_card("headcount", "Total Employees", org.get("headcount"), "count",
                org_prev.get("headcount")),
        mom_card("joiners", "New Joiners", fc.get("joiners"), "count", fc_prev.get("joiners")),
        mom_card("resigned", "Resigned", fc.get("resigned"), "count", fc_prev.get("resigned"),
                higher_is_better=False),
        mom_card("conversion_rate", "Conversion Rate", fc.get("conversion_rate"), "pct",
                fc_prev.get("conversion_rate")),
    ]

    actual_points = _spark(db, "org_monthly", hist, "headcount")
    future_months = months_forward(month, FUTURE_MONTHS)
    future_docs = {r["month"]: r for r in
                  db.forecaster_monthly.find({"month": {"$in": future_months}}, {"_id": 0})}
    forecast_points = [{"t": m, "v": future_docs[m].get("headcount_forecast")}
                       for m in future_months if m in future_docs]

    return {
        "month": month, "cards": cards,
        "charts": {
            "headcount_forecast": {"actual": actual_points, "forecast": forecast_points},
            "joiners_vs_resigned": {
                "joiners": _spark(db, "forecaster_monthly", hist, "joiners"),
                "resigned": _spark(db, "forecaster_monthly", hist, "resigned"),
            },
        },
        "tables": {"departments": org.get("dept_headcounts", [])},
        "last_updated": _now_iso(),
    }


# --- Revenue ---
def build_revenue(db: Database, period: Period) -> dict:
    month = period.month
    hist = months_back(month, 12)
    fin = db.finance_monthly.find_one({"month": month}, {"_id": 0}) or {}
    fin_prev = db.finance_monthly.find_one({"month": prev_month(month)}, {"_id": 0}) or {}
    fc = db.forecaster_monthly.find_one({"month": month}, {"_id": 0}) or {}
    fc_prev = db.forecaster_monthly.find_one({"month": prev_month(month)}, {"_id": 0}) or {}

    cards = [
        mom_card("revenue", "Total Revenue", fin.get("revenue"), "inr", fin_prev.get("revenue")),
        mom_card("forecast_revenue", "Forecast (this month)", fc.get("forecast_revenue"), "inr",
                fc_prev.get("forecast_revenue")),
        mom_card("forecast_accuracy", "Forecast Accuracy", fc.get("forecast_accuracy"), "pct",
                fc_prev.get("forecast_accuracy")),
    ]

    actual_points = _spark(db, "finance_monthly", hist, "revenue")
    forecast_past = _spark(db, "forecaster_monthly", hist, "forecast_revenue")
    future_months = months_forward(month, 6)
    future_docs = {r["month"]: r for r in
                  db.forecaster_monthly.find({"month": {"$in": future_months}}, {"_id": 0})}
    forecast_future = [{"t": m, "v": future_docs[m].get("forecast_revenue")}
                       for m in future_months if m in future_docs]

    fin_by_month = {r["month"]: r for r in db.finance_monthly.find({"month": {"$in": hist}}, {"_id": 0})}
    fc_by_month = {r["month"]: r for r in db.forecaster_monthly.find({"month": {"$in": hist}}, {"_id": 0})}
    table_rows = []
    for m in hist:
        actual = fin_by_month.get(m, {}).get("revenue")
        forecast = fc_by_month.get(m, {}).get("forecast_revenue")
        table_rows.append({"month": m, "actual": actual, "forecast": forecast,
                           "variance_pct": _delta(actual, forecast)})

    return {
        "month": month, "cards": cards,
        "charts": {"revenue_trend": {"actual": actual_points, "forecast": forecast_past + forecast_future}},
        "tables": {
            "actual_vs_forecast": table_rows,
            "revenue_segments": fin.get("revenue_segments", []),
        },
        "last_updated": _now_iso(),
    }


# --- Cashflow ---
def build_cashflow(db: Database, period: Period) -> dict:
    month = period.month
    hist = months_back(month, 12)
    fc = db.forecaster_monthly.find_one({"month": month}, {"_id": 0}) or {}
    fc_prev = db.forecaster_monthly.find_one({"month": prev_month(month)}, {"_id": 0}) or {}

    cash_in, cash_out = fc.get("cash_in"), fc.get("cash_out")
    net_cash_flow = (cash_in - cash_out) if cash_in is not None and cash_out is not None else None
    prev_in, prev_out = fc_prev.get("cash_in"), fc_prev.get("cash_out")
    prev_net = (prev_in - prev_out) if prev_in is not None and prev_out is not None else None

    cards = [
        mom_card("cash_balance", "Cash Balance", fc.get("cash_balance"), "inr",
                fc_prev.get("cash_balance")),
        mom_card("cash_in", "Cash In", cash_in, "inr", prev_in),
        mom_card("cash_out", "Cash Out", cash_out, "inr", prev_out, higher_is_better=False),
        mom_card("net_cash_flow", "Net Cash Flow", net_cash_flow, "inr", prev_net),
    ]

    bars_months = hist[-6:]
    by_month = {r["month"]: r for r in
               db.forecaster_monthly.find({"month": {"$in": bars_months}}, {"_id": 0})}
    bars = [{"t": m, "cash_in": by_month.get(m, {}).get("cash_in"),
            "cash_out": by_month.get(m, {}).get("cash_out")} for m in bars_months]

    actual_balance = _spark(db, "forecaster_monthly", hist, "cash_balance")
    future_months = months_forward(month, 6)
    future_docs = {r["month"]: r for r in
                  db.forecaster_monthly.find({"month": {"$in": future_months}}, {"_id": 0})}
    forecast_balance = [{"t": m, "v": future_docs[m].get("forecast_cash_balance")}
                        for m in future_months if m in future_docs]

    return {
        "month": month, "cards": cards,
        "charts": {
            "cash_in_vs_out": {"bars": bars},
            "cash_balance_forecast": {"actual": actual_balance, "forecast": forecast_balance},
        },
        "last_updated": _now_iso(),
    }


# --- Costs ---
def build_costs(db: Database, period: Period) -> dict:
    month = period.month
    hist = months_back(month, 12)
    fin = db.finance_monthly.find_one({"month": month}, {"_id": 0}) or {}
    fin_prev = db.finance_monthly.find_one({"month": prev_month(month)}, {"_id": 0}) or {}
    fc = db.forecaster_monthly.find_one({"month": month}, {"_id": 0}) or {}
    fc_prev = db.forecaster_monthly.find_one({"month": prev_month(month)}, {"_id": 0}) or {}

    categories = fin.get("expense_breakdown", [])
    prev_by_name = {c["category"]: c["amount"] for c in fin_prev.get("expense_breakdown", [])}
    category_rows = []
    for c in sorted(categories, key=lambda x: x["amount"], reverse=True):
        prev_amount = prev_by_name.get(c["category"])
        category_rows.append({"category": c["category"], "amount": c["amount"],
                              "previous": prev_amount, "change_pct": _delta(c["amount"], prev_amount)})
    largest = category_rows[0] if category_rows else None

    cards = [
        mom_card("total_expenses", "Total Expenses", fin.get("expenses"), "inr",
                fin_prev.get("expenses"), higher_is_better=False),
        {"id": "largest_category", "label": "Largest Category",
         "value": largest["amount"] if largest else None, "unit": "inr",
         "delta_pct": None, "delta_direction": None, "good": None,
         "category": largest["category"] if largest else None},
        mom_card("forecast_expenses", "Forecast (this month)", fc.get("forecast_expenses"), "inr",
                fc_prev.get("forecast_expenses"), higher_is_better=False),
    ]

    actual_points = _spark(db, "finance_monthly", hist, "expenses")
    forecast_past = _spark(db, "forecaster_monthly", hist, "forecast_expenses")
    future_months = months_forward(month, 6)
    future_docs = {r["month"]: r for r in
                  db.forecaster_monthly.find({"month": {"$in": future_months}}, {"_id": 0})}
    forecast_future = [{"t": m, "v": future_docs[m].get("forecast_expenses")}
                       for m in future_months if m in future_docs]

    return {
        "month": month, "cards": cards,
        "charts": {"expense_trend": {"actual": actual_points, "forecast": forecast_past + forecast_future}},
        "tables": {"categories": category_rows},
        "last_updated": _now_iso(),
    }


# --- Finance Analyzer ---
def build_analyzer(db: Database, period: Period) -> dict:
    month = period.month
    hist = months_back(month, 12)
    fc = db.forecaster_monthly.find_one({"month": month}, {"_id": 0}) or {}
    fc_prev = db.forecaster_monthly.find_one({"month": prev_month(month)}, {"_id": 0}) or {}
    payments = fc.get("payments", {})
    prev_payments = fc_prev.get("payments", {})

    cards = [
        mom_card("pending_count", "Pending Payments", payments.get("pending_count"), "count",
                prev_payments.get("pending_count"), higher_is_better=False),
        mom_card("overdue_amount", "Overdue Amount", payments.get("overdue_amount"), "inr",
                prev_payments.get("overdue_amount"), higher_is_better=False),
        mom_card("upcoming_due_7d", "Upcoming Due (7 Days)", payments.get("upcoming_due_7d"), "inr",
                prev_payments.get("upcoming_due_7d")),
        mom_card("success_rate", "Payment Success Rate", payments.get("success_rate"), "pct",
                prev_payments.get("success_rate")),
    ]

    hist_docs = {r["month"]: r for r in db.forecaster_monthly.find(
        {"month": {"$in": hist}}, {"_id": 0, "month": 1, "payments": 1})}
    success_rate_hist = [
        {"t": m, "v": hist_docs[m]["payments"]["success_rate"]}
        for m in hist
        if hist_docs.get(m, {}).get("payments", {}).get("success_rate") is not None
    ]

    # Not every `projects` doc carries `project_id` — OpenProject-synced rows
    # are keyed by source_system/source_id instead; only seed-owned projects
    # (which is what `project_invoices` actually references) have it.
    project_names = {p["project_id"]: p.get("name") for p in
                    db.projects.find({"project_id": {"$exists": True}}, {"project_id": 1, "name": 1})}
    invoice_rows = []
    for inv in db.project_invoices.find(
            {"status": {"$in": ["pending", "overdue"]}}).sort("due_date", 1):
        invoice_rows.append({
            "invoice_id": inv.get("invoice_id"), "number": inv.get("number"),
            "project": project_names.get(inv.get("project_id"), inv.get("project_id")),
            "date": inv.get("date"), "due_date": inv.get("due_date"),
            "amount": inv.get("amount"), "status": inv.get("status"),
        })

    return {
        "month": month, "cards": cards,
        "charts": {
            "status_breakdown": {"slices": [{"label": s["status"], "value": s["pct"]}
                                            for s in payments.get("status_breakdown", [])]},
            "success_rate_trend": {"points": success_rate_hist},
        },
        "tables": {"invoices": invoice_rows},
        "last_updated": _now_iso(),
    }
