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

Computer = Callable[[Database], float | int | None]
_COMPUTERS: dict[str, Computer] = {}

_DONE_STATUSES = ["Done", "Closed", "done", "closed", "Resolved"]
CLOSED_BUG_STATUSES = ["Closed", "Rejected", "Resolved"]
_BUG_Q = {"wp_type": {"$regex": "bug", "$options": "i"}}


def computer(name: str):
    def wrap(fn: Computer) -> Computer:
        _COMPUTERS[name] = fn
        return fn

    return wrap


# --- Operations computers ---
@computer("active_project_count")
def _active_projects(db: Database) -> int:
    return db.projects.count_documents({"status": "active"})


@computer("project_completion_rate")
def _project_completion(db: Database) -> float:
    progresses = [p.get("progress", 0) for p in db.projects.find({"status": "active"})]
    return round(mean(progresses), 2) if progresses else 0.0


@computer("task_completion_rate")
def _task_completion(db: Database) -> float:
    total = db.tasks.count_documents({})
    if not total:
        return 0.0
    done = db.tasks.count_documents(
        {"$or": [{"status": {"$in": _DONE_STATUSES}}, {"progress": 100}]}
    )
    return round(done / total * 100, 2)


@computer("overdue_task_count")
def _overdue_tasks(db: Database) -> int:
    today = dt.date.today().isoformat()
    return db.tasks.count_documents(
        {"due_date": {"$lt": today, "$ne": None}, "progress": {"$lt": 100}}
    )


@computer("at_risk_project_count")
def _at_risk_projects(db: Database) -> int:
    """Progress < 70% of expected timeline completion (PRD AI-003)."""
    n = 0
    for p in db.projects.find({"status": "active"}):
        expected = p.get("expected_progress")
        if expected and p.get("progress", 0) < 0.7 * expected:
            n += 1
    return n


# --- Product Development computers (real bug data from OpenProject) ---
@computer("open_bug_count")
def _open_bugs(db: Database) -> int | None:
    if not db.tasks.count_documents(_BUG_Q):
        return None  # no bug data ingested yet
    return db.tasks.count_documents(
        {**_BUG_Q, "status": {"$nin": CLOSED_BUG_STATUSES}})


@computer("critical_bug_count")
def _critical_bugs(db: Database) -> int | None:
    if not db.tasks.count_documents(_BUG_Q):
        return None
    return db.tasks.count_documents(
        {**_BUG_Q, "priority": {"$in": ["Immediate", "High"]},
         "status": {"$nin": CLOSED_BUG_STATUSES}})


@computer("bug_closure_rate")
def _bug_closure(db: Database) -> float | None:
    total = db.tasks.count_documents(_BUG_Q)
    if not total:
        return None
    closed = db.tasks.count_documents(
        {**_BUG_Q, "status": {"$in": CLOSED_BUG_STATUSES}})
    return round(closed / total * 100, 2)


@computer("static")
def _static(db: Database) -> None:
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


def compute(db: Database, kpi_def: dict):
    fn = _COMPUTERS.get(kpi_def["formula"])
    if fn is None:
        return None
    return fn(db)


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
    """Latest computed value per KPI def (for dashboards), without recomputing."""
    query = {"module": {"$in": modules}} if modules else {}
    snapshot = []
    for d in db.kpi_defs.find(query):
        row = db.kpi_values.find_one({"kpi_id": d["kpi_id"]}, sort=[("calculated_at", -1)])
        value = row["value"] if row else None
        snapshot.append(_row(db, d, value))
    return snapshot
