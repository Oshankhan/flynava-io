"""Deterministic demo data for the "Indicator Of Success" screens (Central
Dashboard, Organization/Marketing/Finance/Startup/Operational Insights).

Every write is `update_one({key}, {"$set": doc}, upsert=True)` — never a
blanket delete. These collections are wholly seed-owned (added to
`reset_roster`'s wipe list in seed.py), so idempotent upsert is enough: this
can run repeatedly, including against an already-seeded database.

13 months of history are generated (current month + 12 back), anchored to
`now` so the demo data is always "current" whenever the seed re-runs, plus
~13 months of daily rows for the screens with daily-granularity charts
(visitors/interactions, DAU, task creation) and a small Custom Range window
on Central Dashboard.
"""
from __future__ import annotations

import calendar
import datetime as dt
import random

from pymongo.database import Database

MONTHS_BACK = 13
DAILY_DAYS = 396


def shift_month(month: str, n: int) -> str:
    y, m = int(month[:4]), int(month[5:7])
    idx = y * 12 + (m - 1) + n
    y2, m2 = divmod(idx, 12)
    return f"{y2:04d}-{m2 + 1:02d}"


def month_list(anchor: str, n: int = MONTHS_BACK) -> list[str]:
    """`n` months ending at `anchor` (inclusive), oldest first."""
    return [shift_month(anchor, -(n - 1 - i)) for i in range(n)]


def series(rng: random.Random, current: float, *, mom_pct: float | None = None,
           mom_abs: float | None = None, year_growth_pct: float = 20.0,
           months: int = MONTHS_BACK, floor: float | None = None,
           round_to: int | None = None) -> list[float]:
    """`months` values ending exactly at `current`, oldest first.

    The last two points are pinned by the given month-over-month delta (so
    the headline KPI card's "vs last month" arrow matches); everything
    before that is a smooth geometric walk (with small jitter) from an
    implied start-of-window value derived from `year_growth_pct`.
    """
    vals = [0.0] * months
    vals[-1] = float(current)
    if mom_pct is not None:
        prev = current / (1 + mom_pct / 100)
    elif mom_abs is not None:
        prev = current - mom_abs
    else:
        prev = current / (1 + year_growth_pct / 100 / 12)
    vals[-2] = prev
    n_mid = months - 2
    if n_mid > 0:
        start = prev / (1 + year_growth_pct / 100) if year_growth_pct else prev
        start = start if abs(start) > 1e-6 else (0.01 if prev >= 0 else -0.01)
        ratio = (prev / start) ** (1 / n_mid) if start else 1.0
        v = start
        for i in range(n_mid):
            vals[i] = v * (1 + rng.uniform(-0.03, 0.03))
            v *= ratio
    if floor is not None:
        vals = [max(floor, v) for v in vals]
    if round_to == 0:
        vals = [int(round(v)) for v in vals]
    elif round_to is not None:
        vals = [round(v, round_to) for v in vals]
    return vals


def scale_rows(rows: list[dict], key: str, target_total: float, *,
                as_int: bool = True) -> list[dict]:
    """Rescale `rows[i][key]` proportionally so they sum to `target_total`,
    preserving every other field. The last row absorbs rounding remainder so
    the sum is always exact."""
    original = sum(r[key] for r in rows)
    if original <= 0:
        return [dict(r) for r in rows]
    out = []
    running = 0
    for i, r in enumerate(rows):
        if i == len(rows) - 1:
            v = target_total - running
        else:
            v = r[key] / original * target_total
        if as_int:
            v = int(round(v))
        out.append({**r, key: v})
        running += v
    return out


# --- Central Dashboard ---
def _seed_central(db: Database, months: list[str], now: dt.datetime,
                  rng: random.Random) -> None:
    cur = months[-1]
    productivity = series(rng, 78.4, mom_pct=12.5, round_to=1)
    efficiency = series(rng, 82.6, mom_pct=8.3, round_to=1)
    arr = series(rng, 12_450_000, mom_pct=14.2, round_to=0)
    active_customers = series(rng, 125, mom_pct=9.7, round_to=0)
    demos = series(rng, 24, mom_pct=20.0, round_to=0)
    headcount_growth = series(rng, 18.6, mom_pct=4.3, round_to=1)
    absenteeism = series(rng, 2.4, mom_pct=-1.2, year_growth_pct=-5, floor=0.1, round_to=1)
    tardiness = series(rng, 1.8, mom_pct=-0.6, year_growth_pct=-5, floor=0.1, round_to=1)

    base_progress = {"Completed": 42, "In Progress": 21, "On Hold": 8, "Not Started": 29}
    for i, month in enumerate(months):
        if month == cur:
            progress = dict(base_progress)
            overall_pct = 63
        else:
            weights = {k: max(1, v + rng.randint(-4, 4)) for k, v in base_progress.items()}
            total_w = sum(weights.values())
            progress = {k: round(v / total_w * 100) for k, v in weights.items()}
            diff = 100 - sum(progress.values())
            progress["Completed"] += diff
            overall_pct = max(30, min(90, 60 + rng.randint(-8, 8)))
        db.central_monthly.update_one({"month": month}, {"$set": {
            "month": month,
            "productivity_hours": productivity[i],
            "efficiency_pct": efficiency[i],
            "annual_run_rate": arr[i],
            "active_customers": active_customers[i],
            "demos_this_month": demos[i],
            "headcount_growth_pct": headcount_growth[i],
            "absenteeism_rate": absenteeism[i],
            "tardiness_rate": tardiness[i],
            "progress": progress,
            "progress_overall_pct": overall_pct,
        }}, upsert=True)


# --- Organization Insights ---
_DEPT_BASE = [
    {"dept": "Engineering", "headcount": 399, "performance": 88.6, "attrition": 6.1},
    {"dept": "Sales & Marketing", "headcount": 225, "performance": 82.7, "attrition": 7.3},
    {"dept": "Finance", "headcount": 150, "performance": 78.2, "attrition": 5.8},
    {"dept": "Operations", "headcount": 125, "performance": 80.0, "attrition": 6.5},
    {"dept": "HR", "headcount": 100, "performance": 84.0, "attrition": 4.9},
    {"dept": "Others", "headcount": 249, "performance": 76.5, "attrition": 8.0},
]
_GENDER_BASE = [{"label": "Male", "pct": 68.0}, {"label": "Female", "pct": 30.0},
               {"label": "Other", "pct": 2.0}]
_AGE_BASE = [{"band": "<25", "pct": 8.0}, {"band": "25-34", "pct": 32.0},
            {"band": "35-44", "pct": 28.0}, {"band": "45-54", "pct": 20.0},
            {"band": "55+", "pct": 12.0}]
_EDU_BASE = [{"level": "Bachelor's", "pct": 45.0}, {"level": "Master's", "pct": 35.0},
            {"level": "Diploma", "pct": 15.0}, {"level": "Others", "pct": 5.0}]


def _seed_organization(db: Database, months: list[str], now: dt.datetime,
                       rng: random.Random) -> None:
    headcount = series(rng, 1248, mom_pct=5.6, year_growth_pct=24.8, round_to=0)
    attrition = series(rng, 8.2, mom_pct=-1.3, year_growth_pct=-10, floor=1.0, round_to=1)
    tenure = series(rng, 3.6, mom_abs=0.4, floor=0.5, round_to=1)
    payroll = series(rng, 84_200_000, mom_pct=6.8, round_to=0)
    dept_count = series(rng, 18, mom_abs=2, floor=5, round_to=0)

    for i, month in enumerate(months):
        hc = int(headcount[i])
        dept_rows = scale_rows(
            [{**d, "trend": [round(max(1.0, d["performance"] + rng.uniform(-3, 3)), 1)
                             for _ in range(6)]} for d in _DEPT_BASE],
            "headcount", hc)
        gender = scale_rows(
            [{"label": g["label"], "count": g["pct"] / 100 * hc} for g in _GENDER_BASE],
            "count", hc)
        age = scale_rows(
            [{"band": a["band"], "count": a["pct"] / 100 * hc} for a in _AGE_BASE],
            "count", hc)
        edu = scale_rows(
            [{"level": e["level"], "count": e["pct"] / 100 * hc} for e in _EDU_BASE],
            "count", hc)
        db.org_monthly.update_one({"month": month}, {"$set": {
            "month": month,
            "headcount": hc,
            "active_departments": int(dept_count[i]),
            "attrition_rate": attrition[i],
            "avg_tenure_years": tenure[i],
            "payroll_total": payroll[i],
            "dept_headcounts": dept_rows,
            "demographics": {"gender": gender, "age": age, "education": edu},
        }}, upsert=True)


# --- Marketing Insights ---
_SOURCE_BASE = [
    {"source": "Organic Search", "leads": 1250}, {"source": "Social Media", "leads": 950},
    {"source": "Email Marketing", "leads": 720}, {"source": "Paid Ads", "leads": 480},
    {"source": "Referrals", "leads": 160}, {"source": "Others", "leads": 90},
]
_CAMPAIGN_BASE = [
    {"name": "Summer Offer 2026", "leads": 820, "roi": 285, "status": "Active"},
    {"name": "Product Launch", "leads": 650, "roi": 240, "status": "Active"},
    {"name": "Webinar Series", "leads": 520, "roi": 210, "status": "Active"},
    {"name": "Social Media Drive", "leads": 480, "roi": 195, "status": "Completed"},
    {"name": "Email Nurture", "leads": 430, "roi": 180, "status": "Active"},
]
_CHANNEL_BASE = [
    {"channel": "Organic Search", "impressions": 125000, "clicks": 8450, "leads": 1250,
     "cost": 62500, "roi": 320},
    {"channel": "Social Media", "impressions": 98500, "clicks": 6250, "leads": 950,
     "cost": 45500, "roi": 260},
    {"channel": "Email Marketing", "impressions": 62300, "clicks": 3850, "leads": 720,
     "cost": 28800, "roi": 210},
    {"channel": "Paid Ads", "impressions": 155800, "clicks": 10250, "leads": 480,
     "cost": 62400, "roi": 150},
    {"channel": "Referrals", "impressions": 15200, "clicks": 890, "leads": 160,
     "cost": 4800, "roi": 280},
]


def _seed_marketing(db: Database, months: list[str], now: dt.datetime,
                    rng: random.Random) -> None:
    campaigns_active = series(rng, 28, mom_pct=16.7, round_to=0)
    leads = series(rng, 3650, mom_pct=18.3, round_to=0)
    conversion = series(rng, 5.42, mom_pct=8.9, round_to=2)
    cpl = series(rng, 126, mom_pct=-6.4, year_growth_pct=-15, round_to=0)
    roi = series(rng, 242, mom_pct=12.1, round_to=0)

    for i, month in enumerate(months):
        lead_total = int(leads[i])
        sources = scale_rows([dict(s) for s in _SOURCE_BASE], "leads", lead_total)

        campaigns = scale_rows([dict(c) for c in _CAMPAIGN_BASE], "leads", lead_total)
        for base, c in zip(_CAMPAIGN_BASE, campaigns):
            ratio = c["leads"] / base["leads"] if base["leads"] else 1
            c["conv_rate"] = round(5.0 * ratio * (1 + rng.uniform(-0.05, 0.05)), 1)
            c["roi"] = round(base["roi"] * (1 + rng.uniform(-0.05, 0.05)))

        channels = scale_rows([dict(c) for c in _CHANNEL_BASE], "leads", lead_total)
        for base, c in zip(_CHANNEL_BASE, channels):
            ratio = c["leads"] / base["leads"] if base["leads"] else 1
            c["impressions"] = round(base["impressions"] * ratio)
            c["clicks"] = round(base["clicks"] * ratio)
            c["cost"] = round(base["cost"] * ratio)
            c["ctr"] = round(c["clicks"] / c["impressions"] * 100, 2) if c["impressions"] else 0
            c["conv_rate"] = round(c["leads"] / c["clicks"] * 100, 2) if c["clicks"] else 0
            c["cpl"] = round(c["cost"] / c["leads"]) if c["leads"] else 0
            c["roi"] = round(base["roi"] * (1 + rng.uniform(-0.05, 0.05)))

        db.marketing_monthly.update_one({"month": month}, {"$set": {
            "month": month,
            "campaigns_active": int(campaigns_active[i]),
            "leads": lead_total,
            "conversion_rate": conversion[i],
            "cost_per_lead": cpl[i],
            "roi": roi[i],
            "leads_by_source": sources,
            "top_campaigns": [{"name": c["name"], "leads": c["leads"], "conv_rate": c["conv_rate"],
                               "roi": c["roi"], "status": c["status"]} for c in campaigns],
            "channels": channels,
        }}, upsert=True)


# --- Finance Performance ---
_REVSEG_BASE = [{"segment": "Product Sales", "amount": 124_500_000},
               {"segment": "Services", "amount": 87_600_000},
               {"segment": "Consulting", "amount": 51_200_000},
               {"segment": "Others", "amount": 24_300_000}]
_EXP_BASE = [{"category": "Operations", "amount": 64_500_000},
            {"category": "Marketing", "amount": 32_100_000},
            {"category": "R&D", "amount": 27_800_000},
            {"category": "Admin", "amount": 21_200_000},
            {"category": "Others", "amount": 17_500_000}]


def _seed_finance(db: Database, months: list[str], now: dt.datetime,
                  rng: random.Random) -> None:
    revenue = series(rng, 287_600_000, mom_pct=6.72, round_to=0)
    expenses = series(rng, 163_100_000, mom_pct=8.59, round_to=0)
    net_profit = series(rng, 124_500_000, mom_pct=4.36, round_to=0)
    ebitda = series(rng, 146_700_000, mom_pct=9.40, round_to=0)
    op_margin = series(rng, 21.3, mom_abs=0.6, floor=5.0, round_to=1)
    net_cash_flow = series(rng, 124_500_000, mom_pct=15.7, year_growth_pct=24.8, round_to=0)
    growth_pct = series(rng, 18.6, mom_pct=6.4, round_to=1)
    current_ratio = series(rng, 1.78, mom_abs=0.08, floor=0.5, round_to=2)

    for i, month in enumerate(months):
        rev, exp = revenue[i], expenses[i]
        segs = scale_rows([dict(s) for s in _REVSEG_BASE], "amount", rev)
        exps = scale_rows([dict(e) for e in _EXP_BASE], "amount", exp)
        db.finance_monthly.update_one({"month": month}, {"$set": {
            "month": month,
            "revenue": rev, "expenses": exp, "net_profit": net_profit[i],
            "ebitda": ebitda[i], "operating_margin": op_margin[i],
            "net_cash_flow": net_cash_flow[i], "revenue_growth_pct": growth_pct[i],
            "current_ratio": current_ratio[i],
            "revenue_segments": segs, "expense_breakdown": exps,
        }}, upsert=True)


# --- Startup Metrics ---
def _seed_startup(db: Database, months: list[str], now: dt.datetime,
                  rng: random.Random) -> None:
    active_customers = series(rng, 2350, mom_pct=12.5, round_to=0)
    arpa = series(rng, 24580, mom_pct=8.3, round_to=0)
    burn = series(rng, 1_845_000, mom_pct=-5.6, year_growth_pct=-15, round_to=0)
    mrr = series(rng, 12_800_000, mom_pct=15.4, year_growth_pct=28.4, round_to=0)
    cac = series(rng, 2340, year_growth_pct=-21.6, round_to=0)

    for i, month in enumerate(months):
        db.startup_monthly.update_one({"month": month}, {"$set": {
            "month": month,
            "active_customers": int(active_customers[i]),
            "arpa": arpa[i], "gross_burn": burn[i], "mrr": mrr[i], "cac": cac[i],
        }}, upsert=True)


# --- Operational Insights ---
_STATUS_BASE = [{"status": "Completed", "count": 1072}, {"status": "In Progress", "count": 92},
               {"status": "On Hold", "count": 52}, {"status": "Overdue", "count": 32}]
_PRIORITY_BASE = [{"priority": "High", "count": 352}, {"priority": "Medium", "count": 536},
                  {"priority": "Low", "count": 264}, {"priority": "Critical", "count": 96}]
_PROCESS_BASE = [
    {"process": "Customer Support", "total_tasks": 320, "completed": 284, "on_time_pct": 88.8,
     "overdue": 12, "avg_completion_hours": 2.4},
    {"process": "Order Fulfillment", "total_tasks": 280, "completed": 244, "on_time_pct": 85.7,
     "overdue": 10, "avg_completion_hours": 3.1},
    {"process": "Inventory Management", "total_tasks": 200, "completed": 176, "on_time_pct": 90.0,
     "overdue": 6, "avg_completion_hours": 2.0},
    {"process": "Vendor Management", "total_tasks": 160, "completed": 132, "on_time_pct": 82.5,
     "overdue": 8, "avg_completion_hours": 2.8},
    {"process": "System Maintenance", "total_tasks": 128, "completed": 112, "on_time_pct": 87.5,
     "overdue": 4, "avg_completion_hours": 1.6},
]


def _seed_operations(db: Database, months: list[str], now: dt.datetime,
                     rng: random.Random) -> None:
    tasks_total = series(rng, 1248, mom_pct=12.8, round_to=0)
    on_time = series(rng, 86.5, mom_pct=6.7, floor=40.0, round_to=1)
    overdue = series(rng, 32, mom_pct=-18.8, year_growth_pct=-18.8, floor=0, round_to=0)
    resource_util = series(rng, 78.6, mom_pct=6.3, round_to=1)
    process_eff = series(rng, 82.4, mom_pct=5.7, round_to=1)
    qa_score = series(rng, 93.1, mom_pct=4.2, round_to=1)
    sla = series(rng, 90.2, mom_pct=7.1, round_to=1)

    for i, month in enumerate(months):
        total = int(tasks_total[i])
        status_rows = scale_rows([dict(s) for s in _STATUS_BASE], "count", total)
        completed = next(s["count"] for s in status_rows if s["status"] == "Completed")
        pending = sum(s["count"] for s in status_rows if s["status"] != "Completed")
        priority_rows = scale_rows([dict(p) for p in _PRIORITY_BASE], "count", total)

        scale = total / 1248
        proc_rows = []
        for p in _PROCESS_BASE:
            row = dict(p)
            row["total_tasks"] = max(1, round(p["total_tasks"] * scale))
            row["completed"] = max(0, round(p["completed"] * scale))
            row["overdue"] = max(0, round(p["overdue"] * scale))
            row["status"] = "Good" if row["on_time_pct"] >= 85 else "Attention"
            proc_rows.append(row)

        db.ops_monthly.update_one({"month": month}, {"$set": {
            "month": month,
            "tasks_total": total, "tasks_completed": completed,
            "on_time_pct": on_time[i], "pending": pending, "overdue": int(overdue[i]),
            "by_status": status_rows, "by_priority": priority_rows,
            "top_processes": proc_rows,
            "efficiency": {
                "resource_utilization": resource_util[i], "process_efficiency": process_eff[i],
                "qa_score": qa_score[i], "sla_compliance": sla[i],
            },
        }}, upsert=True)


# --- Daily collections (traffic, DAU, ops task creation) ---
def _daily_range(now: dt.datetime, days: int) -> list[dt.date]:
    today = now.date()
    return [today - dt.timedelta(days=days - 1 - i) for i in range(days)]


def _seed_daily(db: Database, now: dt.datetime, rng: random.Random) -> None:
    days = _daily_range(now, DAILY_DAYS)
    today = now.date()

    for d in days:
        weekday = d.weekday() < 5
        date_s = d.isoformat()

        base_v = 950 if weekday else 650
        visitors = max(50, round(base_v * (1 + rng.uniform(-0.15, 0.15))))
        interactions = max(20, round(visitors * (0.6 + rng.uniform(-0.08, 0.08))))
        db.traffic_daily.update_one({"date": date_s}, {"$set": {
            "date": date_s, "visitors": visitors, "interactions": interactions,
        }}, upsert=True)

        base_dau = 620 if weekday else 480
        dau = 620 if d == today else max(30, round(base_dau * (1 + rng.uniform(-0.1, 0.1))))
        db.startup_daily.update_one({"date": date_s}, {"$set": {
            "date": date_s, "dau": dau,
        }}, upsert=True)

        created = max(0, round(rng.gauss(45, 10) if weekday else rng.gauss(12, 5)))
        completed = max(0, round(created * (0.8 + rng.uniform(-0.1, 0.1))))
        db.ops_daily.update_one({"date": date_s}, {"$set": {
            "date": date_s, "tasks_created": created, "tasks_completed": completed,
        }}, upsert=True)


# --- Central Dashboard timeline milestones ---
def _seed_milestones(db: Database, now: dt.datetime) -> None:
    y, m = now.year, now.month
    last_day = calendar.monthrange(y, m)[1]
    templates = [
        ("Project Kickoff", "Website Redesign", 3),
        ("Feature Development", "Dashboard Module", 10),
        ("Testing & QA", "Performance Testing", 20),
        ("Project Launch", "Go Live", 31),
    ]
    today = now.date()
    dates = [dt.date(y, m, min(day, last_day)) for _, _, day in templates]
    in_progress_idx = next((i for i, d in enumerate(dates) if d >= today), len(dates) - 1)
    for i, ((name, sublabel, _day), date) in enumerate(zip(templates, dates)):
        if i < in_progress_idx:
            status = "Completed"
        elif i == in_progress_idx:
            status = "In Progress"
        else:
            status = "Upcoming"
        db.milestones.update_one({"milestone_id": f"m{i + 1}"}, {"$set": {
            "milestone_id": f"m{i + 1}", "name": name, "sublabel": sublabel,
            "date": date.isoformat(), "status": status, "order": i + 1,
        }}, upsert=True)


def seed_success(db: Database, now: dt.datetime) -> None:
    rng = random.Random(20260701)
    cur_month = now.strftime("%Y-%m")
    months = month_list(cur_month, MONTHS_BACK)
    _seed_central(db, months, now, rng)
    _seed_organization(db, months, now, rng)
    _seed_marketing(db, months, now, rng)
    _seed_finance(db, months, now, rng)
    _seed_startup(db, months, now, rng)
    _seed_operations(db, months, now, rng)
    _seed_daily(db, now, rng)
    _seed_milestones(db, now)
