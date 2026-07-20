"""Payload builders for the "Indicator Of Success" screens (Central
Dashboard, Organization/Marketing/Finance/Startup/Operational Insights).

Kept deliberately separate from `kpi/engine.py`: registering these ~30
metrics as KPI defs would leak them into the 8 existing role dashboards
(`latest_snapshot` selects by module), and `kpi_values`'s snapshot cadence
can't answer "March 2026 vs February 2026" — these screens read month-keyed
rollup collections (`services/success_seed.py`) instead and compute a true
month-over-month delta directly from two stored documents.
"""
from __future__ import annotations

import datetime as dt
import re

from fastapi import HTTPException, status
from pymongo.database import Database

_MONTH_RE = re.compile(r"^\d{4}-(0[1-9]|1[0-2])$")
_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")


def _shift_month(month: str, n: int) -> str:
    y, m = int(month[:4]), int(month[5:7])
    idx = y * 12 + (m - 1) + n
    y2, m2 = divmod(idx, 12)
    return f"{y2:04d}-{m2 + 1:02d}"


def current_month(now: dt.datetime | None = None) -> str:
    now = now or dt.datetime.now(dt.timezone.utc)
    return now.strftime("%Y-%m")


def prev_month(month: str) -> str:
    return _shift_month(month, -1)


def months_back(month: str, n: int) -> list[str]:
    """`n` months ending at `month` (inclusive), oldest first."""
    return [_shift_month(month, -(n - 1 - i)) for i in range(n)]


class Period:
    """Resolved query period: `month` (YYYY-MM) always; `date_from`/`date_to`
    are set only for Central Dashboard's Custom Range (day-level), which
    drives the daily visitors/interactions chart — every other chart/card
    on every screen stays month-scoped."""

    __slots__ = ("month", "date_from", "date_to")

    def __init__(self, month: str, date_from: str | None = None, date_to: str | None = None):
        self.month = month
        self.date_from = date_from
        self.date_to = date_to


def resolve_period(month: str | None, date_from: str | None = None,
                   date_to: str | None = None) -> Period:
    if date_from or date_to:
        if not (date_from and date_to):
            raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY,
                                "both from and to are required for a custom range")
        if not (_DATE_RE.match(date_from) and _DATE_RE.match(date_to)):
            raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY,
                                "from/to must be YYYY-MM-DD")
        if date_from > date_to:
            raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "from must be <= to")
        return Period(date_to[:7], date_from, date_to)
    m = month or current_month()
    if not _MONTH_RE.match(m):
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "month must be YYYY-MM")
    return Period(m)


def _delta(cur: float | None, prev: float | None) -> float | None:
    if cur is None or prev is None or prev == 0:
        return None
    return round((cur - prev) / abs(prev) * 100, 1)


def mom_card(card_id: str, label: str, value, unit: str, prev_value, *,
            spark: list[dict] | None = None, link: str | None = None,
            higher_is_better: bool = True) -> dict:
    """A KPI card with a true month-over-month delta (current vs. the prior
    month's stored value — NOT `kpi.engine.change_pct`, which compares the
    last two computed snapshots and isn't calendar-aware)."""
    delta = _delta(value, prev_value)
    direction = None
    good = None
    if delta is not None:
        direction = "up" if delta > 0 else ("down" if delta < 0 else "flat")
        good = True if delta == 0 else (delta > 0) == higher_is_better
    card = {"id": card_id, "label": label, "value": value, "unit": unit,
           "delta_pct": delta, "delta_direction": direction, "good": good}
    if spark is not None:
        card["spark"] = spark
    if link:
        card["link"] = link
    return card


def _spark(db: Database, coll: str, months: list[str], field: str) -> list[dict]:
    rows = {r["month"]: r.get(field) for r in
            db[coll].find({"month": {"$in": months}}, {"month": 1, field: 1})}
    return [{"t": m, "v": rows[m]} for m in months if rows.get(m) is not None]


def _now_iso() -> str:
    return dt.datetime.now(dt.timezone.utc).isoformat()


# --- Central Dashboard ---
def build_central(db: Database, period: Period) -> dict:
    month = period.month
    hist = months_back(month, 7)
    doc = db.central_monthly.find_one({"month": month}, {"_id": 0}) or {}
    prev = db.central_monthly.find_one({"month": prev_month(month)}, {"_id": 0}) or {}
    fin_doc = db.finance_monthly.find_one({"month": month}, {"_id": 0}) or {}
    fin_prev = db.finance_monthly.find_one({"month": prev_month(month)}, {"_id": 0}) or {}

    cards = [
        mom_card("productivity", "Overall Productivity", doc.get("productivity_hours"), "hours",
                prev.get("productivity_hours"),
                spark=_spark(db, "central_monthly", hist, "productivity_hours"),
                link="/success/operations"),
        mom_card("efficiency", "Overall Efficiency", doc.get("efficiency_pct"), "pct",
                prev.get("efficiency_pct"),
                spark=_spark(db, "central_monthly", hist, "efficiency_pct"),
                link="/success/operations"),
        mom_card("net_cash_flow", "Net Cash Flow", fin_doc.get("net_cash_flow"), "inr",
                fin_prev.get("net_cash_flow"),
                spark=_spark(db, "finance_monthly", hist, "net_cash_flow"),
                link="/success/finance"),
        mom_card("revenue_growth", "Revenue Growth Rate", fin_doc.get("revenue_growth_pct"), "pct",
                fin_prev.get("revenue_growth_pct"),
                spark=_spark(db, "finance_monthly", hist, "revenue_growth_pct"),
                link="/success/finance"),
    ]

    mini_cards = [
        mom_card("annual_run_rate", "Annual Run Rate", doc.get("annual_run_rate"), "inr",
                prev.get("annual_run_rate"),
                spark=_spark(db, "central_monthly", hist, "annual_run_rate")),
        mom_card("active_customers", "Active Customers", doc.get("active_customers"), "count",
                prev.get("active_customers"),
                spark=_spark(db, "central_monthly", hist, "active_customers")),
        mom_card("demos", "Demos This Month", doc.get("demos_this_month"), "count",
                prev.get("demos_this_month"),
                spark=_spark(db, "central_monthly", hist, "demos_this_month")),
        mom_card("headcount_growth", "Headcount Growth", doc.get("headcount_growth_pct"), "pct",
                prev.get("headcount_growth_pct"),
                spark=_spark(db, "central_monthly", hist, "headcount_growth_pct")),
        mom_card("absenteeism", "Absenteeism Rate", doc.get("absenteeism_rate"), "pct",
                prev.get("absenteeism_rate"),
                spark=_spark(db, "central_monthly", hist, "absenteeism_rate"),
                higher_is_better=False),
        mom_card("tardiness", "Tardiness Rate", doc.get("tardiness_rate"), "pct",
                prev.get("tardiness_rate"),
                spark=_spark(db, "central_monthly", hist, "tardiness_rate"),
                higher_is_better=False),
    ]

    if period.date_from and period.date_to:
        d_from, d_to = period.date_from, period.date_to
    else:
        d_from, d_to = f"{month}-01", f"{month}-31"
    traffic = list(db.traffic_daily.find(
        {"date": {"$gte": d_from, "$lte": d_to}}, {"_id": 0}).sort("date", 1))
    total_visitors = sum(t["visitors"] for t in traffic)
    total_interactions = sum(t["interactions"] for t in traffic)
    engagement_rate = round(total_interactions / total_visitors * 100, 1) if total_visitors else 0.0

    progress = doc.get("progress", {})
    timeline = list(db.milestones.find({}, {"_id": 0}).sort("order", 1))

    return {
        "month": month, "period": {"from": d_from, "to": d_to}, "cards": cards,
        "charts": {
            "visitors": {
                "points": [{"t": t["date"], "visitors": t["visitors"], "interactions": t["interactions"]}
                          for t in traffic],
                "footer": {"total_visitors": total_visitors, "total_interactions": total_interactions,
                          "engagement_rate": engagement_rate},
            },
            "progress": {"slices": [{"label": k, "value": v} for k, v in progress.items()],
                        "overall_pct": doc.get("progress_overall_pct")},
        },
        "tables": {"timeline": timeline, "mini_cards": mini_cards},
        "last_updated": _now_iso(),
    }


# --- Organization Insights ---
def build_organization(db: Database, period: Period) -> dict:
    month = period.month
    hist = months_back(month, 12)
    doc = db.org_monthly.find_one({"month": month}, {"_id": 0}) or {}
    prev = db.org_monthly.find_one({"month": prev_month(month)}, {"_id": 0}) or {}

    cards = [
        mom_card("headcount", "Total Headcount", doc.get("headcount"), "count",
                prev.get("headcount"), spark=_spark(db, "org_monthly", hist, "headcount")),
        mom_card("active_departments", "Active Departments", doc.get("active_departments"), "count",
                prev.get("active_departments"),
                spark=_spark(db, "org_monthly", hist, "active_departments")),
        mom_card("attrition_rate", "Attrition Rate", doc.get("attrition_rate"), "pct",
                prev.get("attrition_rate"), spark=_spark(db, "org_monthly", hist, "attrition_rate"),
                higher_is_better=False),
        mom_card("avg_tenure", "Avg Tenure", doc.get("avg_tenure_years"), "years",
                prev.get("avg_tenure_years"), spark=_spark(db, "org_monthly", hist, "avg_tenure_years")),
        mom_card("payroll_total", "Total Payroll", doc.get("payroll_total"), "inr",
                prev.get("payroll_total"), spark=_spark(db, "org_monthly", hist, "payroll_total")),
    ]

    dept_rows = doc.get("dept_headcounts", [])
    top_depts = sorted(dept_rows, key=lambda d: d.get("performance", 0), reverse=True)[:4]

    return {
        "month": month, "cards": cards,
        "charts": {
            "headcount_trend": {"points": _spark(db, "org_monthly", hist, "headcount")},
            "dept_headcount": {"slices": [{"label": d["dept"], "value": d["headcount"]}
                                          for d in dept_rows]},
            "attrition_trend": {"points": _spark(db, "org_monthly", hist, "attrition_rate")},
            "demographics": doc.get("demographics", {}),
        },
        "tables": {"top_departments": top_depts},
        "last_updated": _now_iso(),
    }


# --- Marketing Insights ---
def build_marketing(db: Database, period: Period) -> dict:
    month = period.month
    hist = months_back(month, 12)
    doc = db.marketing_monthly.find_one({"month": month}, {"_id": 0}) or {}
    prev = db.marketing_monthly.find_one({"month": prev_month(month)}, {"_id": 0}) or {}

    cards = [
        mom_card("campaigns", "Total Campaigns", doc.get("campaigns_active"), "count",
                prev.get("campaigns_active"),
                spark=_spark(db, "marketing_monthly", hist, "campaigns_active")),
        mom_card("leads", "Total Leads", doc.get("leads"), "count", prev.get("leads"),
                spark=_spark(db, "marketing_monthly", hist, "leads")),
        mom_card("conversion_rate", "Conversion Rate", doc.get("conversion_rate"), "pct",
                prev.get("conversion_rate"),
                spark=_spark(db, "marketing_monthly", hist, "conversion_rate")),
        mom_card("cost_per_lead", "Cost Per Lead", doc.get("cost_per_lead"), "inr",
                prev.get("cost_per_lead"),
                spark=_spark(db, "marketing_monthly", hist, "cost_per_lead"),
                higher_is_better=False),
        mom_card("roi", "Marketing ROI", doc.get("roi"), "pct", prev.get("roi"),
                spark=_spark(db, "marketing_monthly", hist, "roi")),
    ]

    sources = doc.get("leads_by_source", [])

    return {
        "month": month, "cards": cards,
        "charts": {
            "leads_by_source": {"slices": [{"label": s["source"], "value": s["leads"]}
                                           for s in sources]},
            "leads_trend": {"points": _spark(db, "marketing_monthly", hist, "leads")},
        },
        "tables": {
            "leads_by_source": sources,
            "top_campaigns": doc.get("top_campaigns", []),
            "channels": doc.get("channels", []),
        },
        "last_updated": _now_iso(),
    }


# --- Finance Performance ---
def build_finance(db: Database, period: Period, granularity: str = "monthly") -> dict:
    month = period.month
    hist = months_back(month, 12)

    if granularity == "yearly":
        year_months = months_back(month, 12)
        by_month = {r["month"]: r for r in
                   db.finance_monthly.find({"month": {"$in": year_months}}, {"_id": 0})}
        rows = [by_month[m] for m in year_months if m in by_month]
        revenue = sum(r["revenue"] for r in rows)
        expenses = sum(r["expenses"] for r in rows)
        net_profit = sum(r["net_profit"] for r in rows)
        ebitda = sum(r["ebitda"] for r in rows)
        net_cash_flow = sum(r["net_cash_flow"] for r in rows)
        latest = rows[-1] if rows else {}
        operating_margin = latest.get("operating_margin")
        current_ratio = latest.get("current_ratio")
        revenue_growth_pct = latest.get("revenue_growth_pct")

        # A prior-year comparison is only meaningful once a full 12-month
        # window exists that far back — with fewer months seeded/accrued,
        # summing a partial window against a full one produces a misleading
        # (often huge) "change" rather than a real YoY figure. Self-heals
        # once 24 months of real history has accumulated.
        prior_months = months_back(_shift_month(month, -12), 12)
        prior_by_month = {r["month"]: r for r in
                         db.finance_monthly.find({"month": {"$in": prior_months}}, {"_id": 0})}
        prior_rows = [prior_by_month[m] for m in prior_months if m in prior_by_month]
        has_full_prior_year = len(prior_rows) == len(prior_months)
        prior_revenue = sum(r["revenue"] for r in prior_rows) if has_full_prior_year else None
        prior_expenses = sum(r["expenses"] for r in prior_rows) if has_full_prior_year else None
        prior_net_profit = sum(r["net_profit"] for r in prior_rows) if has_full_prior_year else None
        prior_ebitda = sum(r["ebitda"] for r in prior_rows) if has_full_prior_year else None
        prior_cash_flow = sum(r["net_cash_flow"] for r in prior_rows) if has_full_prior_year else None
        prior_current_ratio = prior_rows[-1].get("current_ratio") if has_full_prior_year else None
        prior_operating_margin = prior_rows[-1].get("operating_margin") if has_full_prior_year else None
        prior_revenue_growth_pct = (
            prior_rows[-1].get("revenue_growth_pct") if has_full_prior_year else None)
    else:
        doc = db.finance_monthly.find_one({"month": month}, {"_id": 0}) or {}
        prev = db.finance_monthly.find_one({"month": prev_month(month)}, {"_id": 0}) or {}
        revenue, expenses = doc.get("revenue"), doc.get("expenses")
        net_profit, ebitda = doc.get("net_profit"), doc.get("ebitda")
        net_cash_flow = doc.get("net_cash_flow")
        operating_margin, current_ratio = doc.get("operating_margin"), doc.get("current_ratio")
        revenue_growth_pct = doc.get("revenue_growth_pct")
        prior_revenue, prior_expenses = prev.get("revenue"), prev.get("expenses")
        prior_net_profit, prior_ebitda = prev.get("net_profit"), prev.get("ebitda")
        prior_cash_flow = prev.get("net_cash_flow")
        prior_current_ratio = prev.get("current_ratio")
        prior_operating_margin = prev.get("operating_margin")
        prior_revenue_growth_pct = prev.get("revenue_growth_pct")

    cards = [
        mom_card("net_cash_flow", "Net Cash Flow", net_cash_flow, "inr", prior_cash_flow,
                spark=_spark(db, "finance_monthly", hist, "net_cash_flow")),
        mom_card("revenue_growth", "Revenue Growth Rate", revenue_growth_pct, "pct",
                prior_revenue_growth_pct,
                spark=_spark(db, "finance_monthly", hist, "revenue_growth_pct")),
        mom_card("current_ratio", "Current Ratio", current_ratio, "ratio", prior_current_ratio,
                spark=_spark(db, "finance_monthly", hist, "current_ratio")),
    ]

    latest_doc = db.finance_monthly.find_one({"month": month}, {"_id": 0}) or {}

    summary_rows = [
        {"metric": "Total Revenue", "current": revenue, "previous": prior_revenue},
        {"metric": "Total Expenses", "current": expenses, "previous": prior_expenses},
        {"metric": "Net Profit", "current": net_profit, "previous": prior_net_profit},
        {"metric": "EBITDA", "current": ebitda, "previous": prior_ebitda},
        {"metric": "Operating Margin", "current": operating_margin, "previous": prior_operating_margin},
    ]
    for r in summary_rows:
        has_both = r["current"] is not None and r["previous"] is not None
        r["change"] = (r["current"] - r["previous"]) if has_both else None
        r["change_pct"] = _delta(r["current"], r["previous"])

    return {
        "month": month, "granularity": granularity, "cards": cards,
        "charts": {
            "net_cash_flow_trend": {"points": _spark(db, "finance_monthly", hist, "net_cash_flow")},
            "revenue_growth_trend": {"points": _spark(db, "finance_monthly", hist, "revenue_growth_pct")},
            "current_ratio_trend": {"points": _spark(db, "finance_monthly", hist, "current_ratio")},
        },
        "tables": {
            "financial_summary": summary_rows,
            "revenue_segments": latest_doc.get("revenue_segments", []),
            "expense_breakdown": latest_doc.get("expense_breakdown", []),
        },
        "last_updated": _now_iso(),
    }


# --- Startup Metrics ---
def build_startup(db: Database, period: Period) -> dict:
    month = period.month
    hist = months_back(month, 12)
    doc = db.startup_monthly.find_one({"month": month}, {"_id": 0}) or {}
    prev = db.startup_monthly.find_one({"month": prev_month(month)}, {"_id": 0}) or {}

    mrr, prev_mrr = doc.get("mrr"), prev.get("mrr")
    arr = mrr * 12 if mrr is not None else None
    prev_arr = prev_mrr * 12 if prev_mrr is not None else None

    cards = [
        mom_card("active_customers", "Active Customers", doc.get("active_customers"), "count",
                prev.get("active_customers"),
                spark=_spark(db, "startup_monthly", hist, "active_customers")),
        mom_card("arpa", "Avg Revenue / Account", doc.get("arpa"), "inr", prev.get("arpa"),
                spark=_spark(db, "startup_monthly", hist, "arpa")),
        mom_card("gross_burn", "Gross Burn Rate", doc.get("gross_burn"), "inr",
                prev.get("gross_burn"), spark=_spark(db, "startup_monthly", hist, "gross_burn"),
                higher_is_better=False),
        mom_card("mrr", "Monthly Recurring Revenue", mrr, "inr", prev_mrr,
                spark=_spark(db, "startup_monthly", hist, "mrr")),
        mom_card("arr", "Annual Run Rate", arr, "inr", prev_arr),
    ]

    day_from, day_to = f"{month}-01", f"{month}-31"
    dau_rows = list(db.startup_daily.find(
        {"date": {"$gte": day_from, "$lte": day_to}}, {"_id": 0}).sort("date", 1))
    avg_dau = round(sum(r["dau"] for r in dau_rows) / len(dau_rows)) if dau_rows else 0

    def _kpi_row(metric: str, cur, pv, field: str | None = None) -> dict:
        row = {"metric": metric, "current": cur, "previous": pv,
              "spark": _spark(db, "startup_monthly", hist, field) if field else None}
        row["change"] = (cur - pv) if (cur is not None and pv is not None) else None
        row["change_pct"] = _delta(cur, pv)
        return row

    kpi_rows = [
        _kpi_row("Active Customers", doc.get("active_customers"), prev.get("active_customers"),
                "active_customers"),
        _kpi_row("Average Revenue Per Account", doc.get("arpa"), prev.get("arpa"), "arpa"),
        _kpi_row("Gross Burn Rate", doc.get("gross_burn"), prev.get("gross_burn"), "gross_burn"),
        _kpi_row("Monthly Recurring Revenue (MRR)", mrr, prev_mrr, "mrr"),
        _kpi_row("Annual Run Rate", arr, prev_arr),
    ]

    return {
        "month": month, "cards": cards,
        "charts": {
            "mrr_trend": {"points": _spark(db, "startup_monthly", hist, "mrr")},
            "dau_trend": {"points": [{"t": r["date"], "v": r["dau"]} for r in dau_rows],
                         "average": avg_dau},
            "cac_trend": {"points": _spark(db, "startup_monthly", hist, "cac")},
        },
        "tables": {"kpi_overview": kpi_rows},
        "last_updated": _now_iso(),
    }


# --- Operational Insights ---
def build_operations(db: Database, period: Period) -> dict:
    month = period.month
    hist = months_back(month, 12)
    doc = db.ops_monthly.find_one({"month": month}, {"_id": 0}) or {}
    prev = db.ops_monthly.find_one({"month": prev_month(month)}, {"_id": 0}) or {}

    cards = [
        mom_card("tasks_total", "Total Tasks", doc.get("tasks_total"), "count",
                prev.get("tasks_total"), spark=_spark(db, "ops_monthly", hist, "tasks_total")),
        mom_card("tasks_completed", "Tasks Completed", doc.get("tasks_completed"), "count",
                prev.get("tasks_completed"),
                spark=_spark(db, "ops_monthly", hist, "tasks_completed")),
        mom_card("on_time_pct", "On-Time Completion", doc.get("on_time_pct"), "pct",
                prev.get("on_time_pct"), spark=_spark(db, "ops_monthly", hist, "on_time_pct")),
        mom_card("pending", "Pending Tasks", doc.get("pending"), "count", prev.get("pending"),
                spark=_spark(db, "ops_monthly", hist, "pending"), higher_is_better=False),
        mom_card("overdue", "Overdue Tasks", doc.get("overdue"), "count", prev.get("overdue"),
                spark=_spark(db, "ops_monthly", hist, "overdue"), higher_is_better=False),
    ]

    day_from, day_to = f"{month}-01", f"{month}-31"
    daily_rows = list(db.ops_daily.find(
        {"date": {"$gte": day_from, "$lte": day_to}}, {"_id": 0}).sort("date", 1))
    cumulative = 0
    trend_points = []
    for r in daily_rows:
        cumulative += r["tasks_created"]
        trend_points.append({"t": r["date"], "v": cumulative})

    efficiency = doc.get("efficiency", {})
    prev_efficiency = prev.get("efficiency", {})

    def _eff_row(metric: str, key: str) -> dict:
        return {"metric": metric, "value": efficiency.get(key),
               "delta_pct": _delta(efficiency.get(key), prev_efficiency.get(key))}

    efficiency_rows = [
        _eff_row("Resource Utilization", "resource_utilization"),
        _eff_row("Process Efficiency", "process_efficiency"),
        _eff_row("Quality Assurance", "qa_score"),
        _eff_row("SLA Compliance", "sla_compliance"),
    ]

    return {
        "month": month, "cards": cards,
        "charts": {
            "by_status": {"slices": [{"label": s["status"], "value": s["count"]}
                                     for s in doc.get("by_status", [])]},
            "by_priority": {"slices": [{"label": p["priority"], "value": p["count"]}
                                       for p in doc.get("by_priority", [])]},
            "tasks_trend": {"points": trend_points},
        },
        "tables": {
            "by_status": doc.get("by_status", []),
            "by_priority": doc.get("by_priority", []),
            "top_processes": doc.get("top_processes", []),
            "efficiency": efficiency_rows,
        },
        "last_updated": _now_iso(),
    }
