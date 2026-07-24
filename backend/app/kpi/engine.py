"""Rules-based KPI engine (PRD ARCH tier 4).

Definitions live in the DB (`kpi_defs`). Each definition's `formula` names a
computer registered here. `run_all` computes every KPI, stores a `kpi_values`
row, and returns a snapshot with RAG status. Adding a KPI = a new row + a new
`@computer` function — no other code changes (PRD NFR-012/013).
"""
from __future__ import annotations

import datetime as dt
from statistics import mean
from typing import Callable

from pymongo.database import Database

Computer = Callable[[Database, str | None], float | int | None]
_COMPUTERS: dict[str, Computer] = {}


# Terminal-status vocabulary, confirmed against the real OpenProject workflow
# (2026-07-15 recalibration): a work item — task or bug — is done when its
# status is Closed, Not a Bug, or Done. Every other status (Reopen, Retest,
# In testing, Replica Done, PROD Retest, ...) is mid-pipeline, not done, even
# though several of those sound terminal. One shared vocabulary for both task
# and bug completion — there's no real distinction in this team's workflow.
# "Resolved"/"Rejected" are kept too: unused in real OP data today (0
# occurrences) but were already recognized as terminal in seed/demo data —
# keeping them is a pure superset of prior behavior, nothing that used to
# count as done stops counting as done.
TERMINAL_STATUSES = ["Closed", "closed", "Not a Bug", "Done", "done",
                     "Resolved", "resolved", "Rejected"]
_DONE_STATUSES = TERMINAL_STATUSES  # kept as an alias — some callers know it by this name
CLOSED_BUG_STATUSES = TERMINAL_STATUSES  # ditto
_BUG_Q = {"wp_type": {"$regex": "bug", "$options": "i"}}


def computer(name: str):
    def wrap(fn: Computer) -> Computer:
        _COMPUTERS[name] = fn
        return fn

    return wrap


# Every computer takes an optional `project` (an OpenProject `source_id`) —
# None (the default, and every existing call site) means "all projects", so
# nothing about unscoped behavior changes. Only the operations/product_dev
# computers below actually use it; formulas outside that set (payroll,
# revenue, ...) aren't project-shaped and just ignore the argument.
def _proj_q(project: str | None) -> dict:
    return {"source_id": project} if project else {}


def _task_q(project: str | None) -> dict:
    return {"project_source_id": project} if project else {}


# --- Operations computers ---
@computer("active_project_count")
def _active_projects(db: Database, project: str | None = None) -> int:
    return db.projects.count_documents({"status": "active", **_proj_q(project)})


@computer("project_completion_rate")
def _project_completion(db: Database, project: str | None = None) -> float:
    progresses = [p.get("progress", 0) for p in
                 db.projects.find({"status": "active", **_proj_q(project)})]
    return round(mean(progresses), 2) if progresses else 0.0


@computer("task_completion_rate")
def _task_completion(db: Database, project: str | None = None) -> float:
    scope = _task_q(project)
    total = db.tasks.count_documents(scope)
    if not total:
        return 0.0
    done = db.tasks.count_documents(
        {**scope, "$or": [{"status": {"$in": _DONE_STATUSES}}, {"progress": 100}]}
    )
    return round(done / total * 100, 2)


@computer("overdue_task_count")
def _overdue_tasks(db: Database, project: str | None = None) -> int:
    today = dt.date.today().isoformat()
    return db.tasks.count_documents(
        {**_task_q(project), "due_date": {"$lt": today, "$ne": None}, "progress": {"$lt": 100}}
    )


@computer("at_risk_project_count")
def _at_risk_projects(db: Database, project: str | None = None) -> int:
    """Progress < 70% of expected timeline completion (PRD AI-003)."""
    n = 0
    for p in db.projects.find({"status": "active", **_proj_q(project)}):
        expected = p.get("expected_progress")
        if expected and p.get("progress", 0) < 0.7 * expected:
            n += 1
    return n


# --- Product Development computers (real bug data from OpenProject) ---
@computer("open_bug_count")
def _open_bugs(db: Database, project: str | None = None) -> int | None:
    q = {**_BUG_Q, **_task_q(project)}
    if not db.tasks.count_documents(q):
        return None  # no bug data ingested yet
    return db.tasks.count_documents({**q, "status": {"$nin": CLOSED_BUG_STATUSES}})


@computer("critical_bug_count")
def _critical_bugs(db: Database, project: str | None = None) -> int | None:
    q = {**_BUG_Q, **_task_q(project)}
    if not db.tasks.count_documents(q):
        return None
    return db.tasks.count_documents(
        {**q, "priority": {"$in": ["Immediate", "High"]},
         "status": {"$nin": CLOSED_BUG_STATUSES}})


@computer("bug_closure_rate")
def _bug_closure(db: Database, project: str | None = None) -> float | None:
    q = {**_BUG_Q, **_task_q(project)}
    total = db.tasks.count_documents(q)
    if not total:
        return None
    closed = db.tasks.count_documents({**q, "status": {"$in": CLOSED_BUG_STATUSES}})
    return round(closed / total * 100, 2)


def _as_datetime(value) -> dt.datetime | None:
    """Normalize a mixed-type timestamp field to an aware datetime. OpenProject
    sync writes ISO strings (`createdAt`/`updatedAt`, sometimes `Z`-suffixed);
    seed data writes native BSON datetimes. Same tolerant parse used by the
    critical-bug-aging detector (insights/detectors_ops.py)."""
    if value is None:
        return None
    if isinstance(value, dt.datetime):
        d = value
    else:
        try:
            d = dt.datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        except ValueError:
            return None
    return d if d.tzinfo else d.replace(tzinfo=dt.timezone.utc)


def _as_date(value) -> dt.date | None:
    """Normalize a date-only field (`due_date`, invoice `date`, attendance
    `date`, ...) — these are ISO date strings regardless of source, but
    `str(x)[:10]` also tolerates a datetime accidentally landing here."""
    if not value:
        return None
    try:
        return dt.date.fromisoformat(str(value)[:10])
    except ValueError:
        return None


# --- Finance computers (invoices seeded, AWS costs from the simulated
# connector — see integrations/aws_sim.py) ---
@computer("invoice_collections_mtd")
def _invoice_collections_mtd(db: Database, project: str | None = None) -> float | None:
    if not db.project_invoices.count_documents({}):
        return None
    month = dt.date.today().strftime("%Y-%m")
    total = sum(
        inv.get("amount", 0) for inv in db.project_invoices.find({"status": "paid"})
        if str(inv.get("date", "")).startswith(month)
    )
    return round(total, 2)


def _latest_payroll_month(db: Database) -> str | None:
    row = db.payslips.find_one(sort=[("month", -1)])
    return row["month"] if row else None


@computer("gross_burn_monthly")
def _gross_burn_monthly(db: Database, project: str | None = None) -> float | None:
    """Payroll gross pay only (INR — see payslips/MyPayslip.tsx's `₹`
    formatting). AWS cost and invoice amounts are USD; summing them with
    payroll without a real FX conversion would produce a meaningless mixed-
    currency figure, so this deliberately doesn't combine them (payroll is
    also the dominant cost by two orders of magnitude in this dataset)."""
    month = _latest_payroll_month(db)
    if not month:
        return None
    payroll = sum(p.get("gross", 0) for p in db.payslips.find({"month": month}))
    return round(payroll, 2)


@computer("ar_over_60")
def _ar_over_60(db: Database, project: str | None = None) -> float | None:
    if not db.project_invoices.count_documents({}):
        return None
    today = dt.date.today()
    total = 0.0
    for inv in db.project_invoices.find({"status": {"$in": ["pending", "overdue"]}}):
        due = _as_date(inv.get("due_date"))
        if due and (today - due).days > 60:
            total += inv.get("amount", 0)
    return round(total, 2)


@computer("ar_days_outstanding")
def _ar_days_outstanding(db: Database, project: str | None = None) -> float | None:
    if not db.project_invoices.count_documents({}):
        return None
    today = dt.date.today()
    days_past_due = []
    for inv in db.project_invoices.find({"status": {"$in": ["pending", "overdue"]}}):
        due = _as_date(inv.get("due_date"))
        if due and (today - due).days > 0:
            days_past_due.append((today - due).days)
    return round(mean(days_past_due), 1) if days_past_due else 0.0


# --- HR computers (employees/attendance seeded — no GreytHR yet) ---
@computer("active_headcount")
def _active_headcount(db: Database, project: str | None = None) -> int | None:
    if not db.employees.count_documents({}):
        return None
    return db.employees.count_documents({"status": "active"})


def _attendance_rate_30d(db: Database, status: str) -> float | None:
    cutoff = (dt.date.today() - dt.timedelta(days=30)).isoformat()
    scope = {"date": {"$gte": cutoff}}
    total = db.attendance.count_documents(scope)
    if not total:
        return None
    matching = db.attendance.count_documents({**scope, "status": status})
    return round(matching / total * 100, 2)


@computer("absenteeism_rate_30d")
def _absenteeism_rate_30d(db: Database, project: str | None = None) -> float | None:
    return _attendance_rate_30d(db, "Absent")


@computer("late_rate_30d")
def _late_rate_30d(db: Database, project: str | None = None) -> float | None:
    return _attendance_rate_30d(db, "Late")


# --- Product Development computers (bug timing from OpenProject) ---
@computer("bug_resolution_days")
def _bug_resolution_days(db: Database, project: str | None = None) -> float | None:
    q = {**_BUG_Q, "status": {"$in": CLOSED_BUG_STATUSES}, **_task_q(project)}
    if not db.tasks.count_documents(q):
        return None
    durations = []
    for b in db.tasks.find(q, {"created_at": 1, "updated_at": 1, "closed_at": 1}):
        created = _as_datetime(b.get("created_at"))
        # `closed_at` (from the OpenProject Activity journal — the actual
        # moment it transitioned into a terminal status) is exact; `updated_at`
        # (last touch on the item) is only a proxy, used when the journal
        # hasn't been synced for this bug yet.
        closed = _as_datetime(b.get("closed_at")) or _as_datetime(b.get("updated_at"))
        if created and closed and closed >= created:
            durations.append((closed - created).total_seconds() / 86400)
    return round(mean(durations), 1) if durations else None


@computer("bug_reopen_rate")
def _bug_reopen_rate(db: Database, project: str | None = None) -> float | None:
    q = {**_BUG_Q, **_task_q(project)}
    docs = list(db.tasks.find(q, {"status": 1, "reopen_count": 1}))
    if not docs:
        return None
    reopened = sum(1 for d in docs
                   if (d.get("reopen_count") or 0) >= 1 or d.get("status") == "Reopen")
    terminal_clean = sum(1 for d in docs if d.get("status") in CLOSED_BUG_STATUSES
                         and (d.get("reopen_count") or 0) < 1)
    denom = reopened + terminal_clean
    return round(reopened / denom * 100, 2) if denom else 0.0


# --- Marketing computer (CRM contacts seeded) ---
@computer("contact_coverage_30d")
def _contact_coverage_30d(db: Database, project: str | None = None) -> float | None:
    active = list(db.crm_contacts.find({"status": "active"}, {"last_contact": 1}))
    if not active:
        return None
    today = dt.date.today()
    fresh = 0
    for c in active:
        last = _as_date(c.get("last_contact"))
        if last and (today - last).days <= 30:
            fresh += 1
    return round(fresh / len(active) * 100, 2)


# --- Resource Management computers ---
# "Utilization" has no stored value anywhere in this DB — see
# services/resource_mgmt.py's `person_utilizations()`, the single source of
# truth this KPI strip and the Resource Dashboard's heatmap/capacity views
# both read (imported locally below, not at module load, so this file never
# has a load-time dependency on the services package).
@computer("res_active_employee_count")
def _res_active_employees(db: Database, project: str | None = None) -> int:
    return db.users.count_documents({"status": "active"})


@computer("res_avg_utilization_pct")
def _res_avg_utilization(db: Database, project: str | None = None) -> float | None:
    from ..services.resource_mgmt import person_utilizations
    utils = person_utilizations(db)
    return round(mean(utils), 1) if utils else None


@computer("res_overloaded_count")
def _res_overloaded(db: Database, project: str | None = None) -> int:
    from ..services.resource_mgmt import person_utilizations
    return sum(1 for u in person_utilizations(db) if u > 100)


@computer("res_underutilized_count")
def _res_underutilized(db: Database, project: str | None = None) -> int:
    from ..services.resource_mgmt import person_utilizations
    return sum(1 for u in person_utilizations(db) if u < 70)


@computer("res_tasks_at_risk_count")
def _res_tasks_at_risk(db: Database, project: str | None = None) -> int:
    today = dt.date.today()
    soon = (today + dt.timedelta(days=3)).isoformat()
    return db.tasks.count_documents({
        "status": {"$nin": TERMINAL_STATUSES},
        "due_date": {"$ne": None, "$lte": soon},
    })


@computer("static")
def _static(db: Database, project: str | None = None) -> None:
    """Placeholder for KPIs whose source integration isn't connected yet."""
    return None


def rag_status(value, target, direction: str) -> str:
    if value is None or target is None:
        return "grey"
    if direction == "higher":
        if value >= target:
            return "green"
        return "amber" if value >= 0.8 * target else "red"
    # lower is better
    if value <= target:
        return "green"
    threshold = target * 1.5 if target > 0 else 3
    return "amber" if value <= threshold else "red"


def compute(db: Database, kpi_def: dict, project: str | None = None):
    fn = _COMPUTERS.get(kpi_def["formula"])
    if fn is None:
        return None
    return fn(db, project)


def _last_values(db: Database, kpi_id: str, n: int = 2) -> list:
    rows = db.kpi_values.find({"kpi_id": kpi_id}).sort("calculated_at", -1).limit(n)
    return [r["value"] for r in rows]


def change_pct(db: Database, kpi_id: str) -> float | None:
    """% change of latest value vs the previous stored value."""
    vals = _last_values(db, kpi_id, 2)
    if len(vals) < 2 or vals[0] is None or not vals[1]:
        return None
    try:
        return round((vals[0] - vals[1]) / abs(vals[1]) * 100, 1)
    except ZeroDivisionError:
        return None


def history(db: Database, kpi_id: str, n: int = 12) -> list[dict]:
    rows = list(db.kpi_values.find({"kpi_id": kpi_id})
                .sort("calculated_at", -1).limit(n))
    rows.reverse()
    return [{"t": r["calculated_at"].strftime("%Y-%m-%d"), "v": r["value"]}
            for r in rows if r.get("value") is not None]


def history_bulk(db: Database, kpi_ids: list[str], n: int = 12) -> dict[str, list[dict]]:
    """Batched `history()` for many KPI ids in a single query.

    Dashboards scan several KPIs' history looking for the first few with
    enough points for a trend chart (see dashboards.py's `_series`) — doing
    that one `history()` call at a time means one query per KPI checked.
    """
    if not kpi_ids:
        return {}
    buckets: dict[str, list[dict]] = {kid: [] for kid in kpi_ids}
    cursor = db.kpi_values.find(
        {"kpi_id": {"$in": kpi_ids}}, {"kpi_id": 1, "value": 1, "calculated_at": 1}
    ).sort("calculated_at", -1)
    for v in cursor:
        bucket = buckets[v["kpi_id"]]
        if len(bucket) < n:
            bucket.append(v)
    out: dict[str, list[dict]] = {}
    for kid, rows in buckets.items():
        rows = list(reversed(rows))
        out[kid] = [{"t": r["calculated_at"].strftime("%Y-%m-%d"), "v": r["value"]}
                    for r in rows if r.get("value") is not None]
    return out


def _row(db: Database, d: dict, value) -> dict:
    # Only trend KPIs (monthly history) get a change arrow. Computed KPIs
    # (ops/bugs) recalc many times a day, so a run-to-run delta is noise.
    delta = change_pct(db, d["kpi_id"]) if d.get("formula") == "static" else None
    return {
        "kpi_id": d["kpi_id"], "name": d["name"], "module": d["module"],
        "value": value, "unit": d.get("unit"), "target": d.get("target"),
        "direction": d.get("direction", "higher"),
        "rag": rag_status(value, d.get("target"), d.get("direction", "higher")),
        "change_pct": delta,
    }


def run_all(db: Database, module: str | None = None) -> list[dict]:
    now = dt.datetime.now(dt.timezone.utc)
    period_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    query = {"module": module} if module else {}
    snapshot = []
    for d in db.kpi_defs.find(query):
        value = compute(db, d)
        if value is not None:
            db.kpi_values.insert_one({
                "kpi_id": d["kpi_id"], "value": value,
                "period_start": period_start, "period_end": now,
                "calculated_at": now, "source_data_ref": d["formula"],
            })
        else:
            # Non-computable (integration not wired) — keep the last known value
            # instead of overwriting it with null.
            row = db.kpi_values.find_one(
                {"kpi_id": d["kpi_id"]}, sort=[("calculated_at", -1)])
            value = row["value"] if row else None
        snapshot.append(_row(db, d, value))
    return snapshot


def latest_snapshot(db: Database, modules: list[str] | None = None) -> list[dict]:
    """Latest computed value per KPI def (for dashboards), without recomputing.

    Batches every kpi_values read into a single query. This used to issue a
    `find_one` per KPI def (plus a second query per "static" KPI for the
    change-arrow) — fine locally, but under real network latency to the DB
    (e.g. cross-region to Atlas) a ~30-KPI dashboard meant 30-50+ round
    trips for one page load. Now it's always exactly two queries.
    """
    query = {"module": {"$in": modules}} if modules else {}
    defs = list(db.kpi_defs.find(query))
    kpi_ids = [d["kpi_id"] for d in defs]
    if not kpi_ids:
        return []

    last_two: dict[str, list] = {}
    cursor = db.kpi_values.find(
        {"kpi_id": {"$in": kpi_ids}}, {"kpi_id": 1, "value": 1, "calculated_at": 1}
    ).sort("calculated_at", -1)
    for v in cursor:
        bucket = last_two.setdefault(v["kpi_id"], [])
        if len(bucket) < 2:
            bucket.append(v["value"])

    snapshot = []
    for d in defs:
        vals = last_two.get(d["kpi_id"], [])
        value = vals[0] if vals else None
        delta = None
        if d.get("formula") == "static" and len(vals) == 2 and vals[1]:
            try:
                delta = round((vals[0] - vals[1]) / abs(vals[1]) * 100, 1)
            except ZeroDivisionError:
                delta = None
        snapshot.append({
            "kpi_id": d["kpi_id"], "name": d["name"], "module": d["module"],
            "value": value, "unit": d.get("unit"), "target": d.get("target"),
            "direction": d.get("direction", "higher"),
            "rag": rag_status(value, d.get("target"), d.get("direction", "higher")),
            "change_pct": delta,
        })
    return snapshot
