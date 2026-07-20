"""KPI explainability ("how did you come up with this number?").

Every live formula in `kpi/engine.py` gets an `@explainer` here that mirrors
its computer's exact query and returns the arithmetic trace + the underlying
records, so the number on a dashboard card is never just a number — it always
has a formula, real evidence rows, and a source/freshness stamp behind it.
KPIs whose formula is `"static"` (no integration connected yet) get an honest
disclosure instead of a fabricated explanation (PRD SEC/RAG honesty — no
inventing facts).
"""
from __future__ import annotations

import datetime as dt
from statistics import mean
from typing import Callable

from pymongo.database import Database

from ..integrations.openproject import work_package_url
from .engine import (
    CLOSED_BUG_STATUSES, _BUG_Q, _DONE_STATUSES, _as_date, _as_datetime,
    _latest_payroll_month,
)

Explainer = Callable[[Database, dict], dict]
_EXPLAINERS: dict[str, Explainer] = {}

MAX_EVIDENCE_ROWS = 15

# Where a still-static KPI's real data will eventually come from (PRD section 8).
PLANNED_SOURCE = {
    "operations": "OpenProject / Jira", "product_dev": "OpenProject / Jira / GitHub",
    "hr": "GreytHR", "finance": "Finance / ERP system",
    "marketing_sales": "HubSpot / Google Analytics / DIIB",
    "recruitment": "GreytHR / LinkedIn", "compliance": "Veda",
    "customer_support": "Zoho Desk",
}


def explainer(name: str):
    def wrap(fn: Explainer) -> Explainer:
        _EXPLAINERS[name] = fn
        return fn

    return wrap


def _project_names(db: Database) -> dict[str, str]:
    out: dict[str, str] = {}
    for p in db.projects.find({}, {"source_id": 1, "project_id": 1, "name": 1}):
        for key in (p.get("source_id"), p.get("project_id")):
            if key:
                out[str(key)] = p.get("name", "")
    return out


def _task_project(t: dict, pnames: dict[str, str]) -> str:
    pid = t.get("project_source_id") or t.get("project_id")
    return pnames.get(str(pid), "") if pid else ""


def _source_info(db: Database, collection: str, live_query: dict) -> dict:
    """Whether the evidence behind a KPI is real synced data or seed/demo data,
    and (when real) the timestamp of the last successful sync — satisfies the
    PRD RAG-rule 'Last Updated' field and stops the dashboard from silently
    presenting demo numbers as if they were live."""
    coll = db[collection]
    is_live = coll.count_documents({**live_query, "source_system": "openproject"}) > 0
    if is_live:
        log = db.integration_logs.find_one({"source": "openproject"},
                                            sort=[("run_at", -1)])
        last_sync = log["run_at"].isoformat() if log and log.get("run_at") else None
        return {
            "system": "OpenProject", "collection": collection, "live": True,
            "last_sync": last_sync,
            "note": (f"Live data synced from OpenProject." if last_sync else
                     "Live OpenProject-sourced data (no sync log recorded yet)."),
        }
    return {
        "system": "Seed data", "collection": collection, "live": False,
        "last_sync": None,
        "note": "Demo seed data — the OpenProject connector has not synced in "
                "this environment yet.",
    }


@explainer("active_project_count")
def _explain_active_projects(db: Database, kpi_def: dict) -> dict:
    projects = list(db.projects.find({"status": "active"}, {"name": 1, "project_id": 1}))
    names = ", ".join(p.get("name", "?") for p in projects) or "none"
    return {
        "formula_text": "Count of projects with status = active.",
        "computation": f"{len(projects)} project(s) are active: {names}.",
        "inputs": [{"label": "Active projects", "value": len(projects)}],
        "evidence": [{"kind": "project", "id": p.get("project_id"),
                      "label": p.get("name")} for p in projects[:MAX_EVIDENCE_ROWS]],
        "source": _source_info(db, "projects", {}),
    }


@explainer("project_completion_rate")
def _explain_project_completion(db: Database, kpi_def: dict) -> dict:
    projects = list(db.projects.find(
        {"status": "active"}, {"name": 1, "progress": 1, "project_id": 1}))
    progresses = [p.get("progress", 0) for p in projects]
    value = round(mean(progresses), 2) if progresses else 0.0
    terms = " + ".join(f"{p.get('name')} {p.get('progress', 0)}%" for p in projects)
    computation = (f"Mean progress across {len(projects)} active project(s): "
                   f"({terms}) / {len(projects)} = {value}%") if projects else \
        "No active projects — nothing to average."
    return {
        "formula_text": "Mean of `progress` across every project with status = active.",
        "computation": computation,
        "inputs": [{"label": p.get("name"), "value": p.get("progress", 0)}
                   for p in projects],
        "evidence": [{"kind": "project", "id": p.get("project_id"), "label": p.get("name"),
                      "extra": {"progress": p.get("progress", 0)}}
                     for p in projects[:MAX_EVIDENCE_ROWS]],
        "source": _source_info(db, "projects", {}),
    }


@explainer("task_completion_rate")
def _explain_task_completion(db: Database, kpi_def: dict) -> dict:
    total = db.tasks.count_documents({})
    done_q = {"$or": [{"status": {"$in": _DONE_STATUSES}}, {"progress": 100}]}
    done = db.tasks.count_documents(done_q)
    value = round(done / total * 100, 2) if total else 0.0
    pnames = _project_names(db)
    sample = list(db.tasks.find(
        done_q, {"title": 1, "status": 1, "progress": 1,
                 "project_id": 1, "project_source_id": 1, "task_id": 1, "source_id": 1}
    ).limit(MAX_EVIDENCE_ROWS))
    return {
        "formula_text": "Done tasks (status = Done/Closed/Resolved OR progress = 100) "
                        "÷ total tasks, across every task in the tracker.",
        "computation": f"{done} done task(s) / {total} total task(s) = {value}%"
                       if total else "No tasks tracked yet.",
        "inputs": [{"label": "Done tasks", "value": done},
                   {"label": "Total tasks", "value": total}],
        "evidence": [{"kind": "task", "id": t.get("task_id") or t.get("source_id"),
                      "label": t.get("title"),
                      "extra": {"status": t.get("status"), "project": _task_project(t, pnames)}}
                     for t in sample],
        "source": _source_info(db, "tasks", {}),
    }


@explainer("overdue_task_count")
def _explain_overdue_tasks(db: Database, kpi_def: dict) -> dict:
    today = dt.date.today().isoformat()
    q = {"due_date": {"$lt": today, "$ne": None}, "progress": {"$lt": 100}}
    total = db.tasks.count_documents(q)
    pnames = _project_names(db)
    sample = list(db.tasks.find(
        q, {"title": 1, "due_date": 1, "assignee": 1, "assignee_id": 1, "priority": 1,
            "project_id": 1, "project_source_id": 1, "task_id": 1, "source_id": 1}
    ).sort("due_date", 1).limit(MAX_EVIDENCE_ROWS))
    return {
        "formula_text": f"Tasks with due_date < today ({today}) and progress < 100%.",
        "computation": f"{total} task(s) are overdue as of {today}.",
        "inputs": [{"label": "Overdue tasks", "value": total}],
        "evidence": [{"kind": "task", "id": t.get("task_id") or t.get("source_id"),
                      "label": t.get("title"),
                      "extra": {"due_date": t.get("due_date"),
                                "assignee": t.get("assignee") or t.get("assignee_id"),
                                "project": _task_project(t, pnames)}}
                     for t in sample],
        "source": _source_info(db, "tasks", q),
    }


@explainer("at_risk_project_count")
def _explain_at_risk_projects(db: Database, kpi_def: dict) -> dict:
    projects = list(db.projects.find(
        {"status": "active"}, {"name": 1, "progress": 1, "expected_progress": 1, "project_id": 1}))
    flagged = [p for p in projects
               if p.get("expected_progress") and p.get("progress", 0) < 0.7 * p["expected_progress"]]
    lines = [f"{p.get('name')} ({p.get('progress', 0)}% vs 70% of {p['expected_progress']}% expected "
             f"= {round(0.7 * p['expected_progress'], 1)}%)" for p in flagged]
    computation = (f"{len(flagged)} of {len(projects)} active project(s) have progress below 70% of "
                   f"their expected timeline completion: " + "; ".join(lines) + ".") if flagged else \
        f"None of {len(projects)} active project(s) are below 70% of their expected progress."
    return {
        "formula_text": "Active projects where progress < 70% × expected_progress "
                        "(PRD AI-003 at-risk rule).",
        "computation": computation,
        "inputs": [{"label": p.get("name"),
                    "value": f"{p.get('progress', 0)}% / {p.get('expected_progress')}% expected"}
                   for p in projects if p.get("expected_progress")],
        "evidence": [{"kind": "project", "id": p.get("project_id"), "label": p.get("name"),
                      "extra": {"progress": p.get("progress", 0),
                                "expected_progress": p.get("expected_progress")}}
                     for p in flagged[:MAX_EVIDENCE_ROWS]],
        "source": _source_info(db, "projects", {}),
    }


def _bug_evidence(db: Database, q: dict, pnames: dict[str, str]) -> list[dict]:
    sample = list(db.tasks.find(
        q, {"title": 1, "status": 1, "priority": 1, "assignee": 1, "assignee_id": 1,
            "project_id": 1, "project_source_id": 1, "task_id": 1, "source_id": 1}
    ).limit(MAX_EVIDENCE_ROWS))
    out = []
    for t in sample:
        sid = t.get("source_id")
        out.append({"kind": "bug", "id": sid or t.get("task_id"), "label": t.get("title"),
                    "url": work_package_url(sid),
                    "extra": {"status": t.get("status"), "priority": t.get("priority"),
                              "assignee": t.get("assignee") or t.get("assignee_id"),
                              "project": _task_project(t, pnames)}})
    return out


@explainer("open_bug_count")
def _explain_open_bugs(db: Database, kpi_def: dict) -> dict:
    q = {**_BUG_Q, "status": {"$nin": CLOSED_BUG_STATUSES}}
    total = db.tasks.count_documents(q)
    return {
        "formula_text": f"Bugs (wp_type ~ 'bug') with status not in "
                        f"{CLOSED_BUG_STATUSES}.",
        "computation": f"{total} bug(s) are currently open.",
        "inputs": [{"label": "Open bugs", "value": total}],
        "evidence": _bug_evidence(db, q, _project_names(db)),
        "source": _source_info(db, "tasks", _BUG_Q),
    }


@explainer("critical_bug_count")
def _explain_critical_bugs(db: Database, kpi_def: dict) -> dict:
    q = {**_BUG_Q, "priority": {"$in": ["Immediate", "High"]},
         "status": {"$nin": CLOSED_BUG_STATUSES}}
    total = db.tasks.count_documents(q)
    return {
        "formula_text": "Open bugs with priority Immediate or High.",
        "computation": f"{total} bug(s) are open at Immediate/High priority.",
        "inputs": [{"label": "Critical open bugs", "value": total}],
        "evidence": _bug_evidence(db, q, _project_names(db)),
        "source": _source_info(db, "tasks", _BUG_Q),
    }


@explainer("bug_closure_rate")
def _explain_bug_closure(db: Database, kpi_def: dict) -> dict:
    total = db.tasks.count_documents(_BUG_Q)
    closed_q = {**_BUG_Q, "status": {"$in": CLOSED_BUG_STATUSES}}
    closed = db.tasks.count_documents(closed_q)
    value = round(closed / total * 100, 2) if total else 0.0
    return {
        "formula_text": f"Bugs with status in {CLOSED_BUG_STATUSES} ÷ all bugs.",
        "computation": f"{closed} closed bug(s) / {total} total bug(s) = {value}%"
                       if total else "No bug data ingested yet.",
        "inputs": [{"label": "Closed bugs", "value": closed},
                   {"label": "Total bugs", "value": total}],
        "evidence": _bug_evidence(db, closed_q, _project_names(db)),
        "source": _source_info(db, "tasks", _BUG_Q),
    }


def _seed_source(collection: str, note: str) -> dict:
    """Source label for KPIs computed from seed data that has no live
    integration behind it yet (invoices, payroll, attendance, CRM contacts —
    honest per the RAG rule: computed from real records in this environment,
    but not synced from an external system)."""
    return {"system": "Seed data", "collection": collection, "live": False,
            "last_sync": None, "note": note}


@explainer("invoice_collections_mtd")
def _explain_invoice_collections_mtd(db: Database, kpi_def: dict) -> dict:
    month = dt.date.today().strftime("%Y-%m")
    paid_this_month = [inv for inv in db.project_invoices.find({"status": "paid"})
                       if str(inv.get("date", "")).startswith(month)]
    total = round(sum(inv.get("amount", 0) for inv in paid_this_month), 2)
    terms = " + ".join(f"${inv.get('amount', 0):,.0f} ({inv.get('number')})"
                       for inv in paid_this_month)
    computation = (f"Paid invoices dated in {month}: {terms} = ${total:,.2f}"
                  if paid_this_month else f"No paid invoices dated in {month}.")
    return {
        "formula_text": "Sum of `amount` across invoices with status = paid and "
                        "`date` in the current calendar month.",
        "computation": computation,
        "inputs": [{"label": inv.get("number"), "value": inv.get("amount", 0)}
                  for inv in paid_this_month],
        "evidence": [{"kind": "invoice", "id": inv.get("invoice_id"),
                     "label": inv.get("number"),
                     "extra": {"amount": inv.get("amount"), "date": inv.get("date"),
                              "project": inv.get("project_id")}}
                    for inv in paid_this_month[:MAX_EVIDENCE_ROWS]],
        "source": _seed_source("project_invoices",
                               "Seeded invoice records — no ERP/accounting system "
                               "connected yet (PRD section 8.1)."),
    }


@explainer("gross_burn_monthly")
def _explain_gross_burn(db: Database, kpi_def: dict) -> dict:
    month = _latest_payroll_month(db)
    if not month:
        return {
            "formula_text": "Sum of payroll gross pay for the latest payroll month.",
            "computation": "No payroll data yet.",
            "inputs": [], "evidence": [],
            "source": _seed_source("payslips", "No payroll records yet."),
        }
    payroll = list(db.payslips.find({"month": month}))
    total = round(sum(p.get("gross", 0) for p in payroll), 2)
    return {
        "formula_text": "Sum of payroll `gross` pay (₹, INR) for the latest "
                        "payroll month. AWS infrastructure cost is tracked "
                        "separately in USD and isn't combined in here — adding "
                        "raw USD to raw INR without a real FX conversion would "
                        "misstate the number, and payroll dominates total spend "
                        "by roughly two orders of magnitude in this dataset.",
        "computation": (f"{month}: {len(payroll)} employee(s), payroll gross "
                        f"total ₹{total:,.2f}"),
        "inputs": [{"label": f"Payroll gross ({month})", "value": total}],
        "evidence": [{"kind": "payroll", "id": p.get("emp_id"), "label": p.get("emp_id"),
                     "extra": {"month": month, "gross": p.get("gross")}}
                    for p in payroll[:MAX_EVIDENCE_ROWS]],
        "source": _seed_source("payslips",
                               "Payroll is seeded — no GreytHR/payroll system "
                               "connected yet."),
    }


@explainer("ar_over_60")
def _explain_ar_over_60(db: Database, kpi_def: dict) -> dict:
    today = dt.date.today()
    flagged = []
    for inv in db.project_invoices.find({"status": {"$in": ["pending", "overdue"]}}):
        due = _as_date(inv.get("due_date"))
        if due and (today - due).days > 60:
            flagged.append((inv, (today - due).days))
    total = round(sum(inv.get("amount", 0) for inv, _ in flagged), 2)
    terms = "; ".join(f"{inv.get('number')} ${inv.get('amount', 0):,.0f} "
                      f"({days}d past due)" for inv, days in flagged)
    return {
        "formula_text": "Sum of `amount` for unpaid (pending/overdue) invoices "
                        f"whose due_date is more than 60 days before today ({today}).",
        "computation": (f"{len(flagged)} invoice(s) over 60 days past due: {terms} "
                        f"= ${total:,.2f}") if flagged else
                       "No unpaid invoices are more than 60 days past due.",
        "inputs": [{"label": inv.get("number"), "value": inv.get("amount", 0)}
                  for inv, _ in flagged],
        "evidence": [{"kind": "invoice", "id": inv.get("invoice_id"),
                     "label": inv.get("number"),
                     "extra": {"amount": inv.get("amount"), "due_date": inv.get("due_date"),
                              "days_past_due": days}}
                    for inv, days in flagged[:MAX_EVIDENCE_ROWS]],
        "source": _seed_source("project_invoices",
                               "Seeded invoice records — no ERP/accounting system "
                               "connected yet."),
    }


@explainer("ar_days_outstanding")
def _explain_ar_days(db: Database, kpi_def: dict) -> dict:
    today = dt.date.today()
    overdue = []
    for inv in db.project_invoices.find({"status": {"$in": ["pending", "overdue"]}}):
        due = _as_date(inv.get("due_date"))
        if due and (today - due).days > 0:
            overdue.append((inv, (today - due).days))
    value = round(mean(d for _, d in overdue), 1) if overdue else 0.0
    terms = " + ".join(str(d) for _, d in overdue)
    computation = (f"({terms}) / {len(overdue)} = {value} days"
                   if overdue else "No unpaid invoices are past their due date.")
    return {
        "formula_text": "Mean of (today − due_date) across unpaid invoices "
                        f"currently past due (today = {today}).",
        "computation": computation,
        "inputs": [{"label": inv.get("number"), "value": d} for inv, d in overdue],
        "evidence": [{"kind": "invoice", "id": inv.get("invoice_id"),
                     "label": inv.get("number"),
                     "extra": {"amount": inv.get("amount"), "due_date": inv.get("due_date"),
                              "days_past_due": d}}
                    for inv, d in overdue[:MAX_EVIDENCE_ROWS]],
        "source": _seed_source("project_invoices",
                               "Seeded invoice records — no ERP/accounting system "
                               "connected yet."),
    }


@explainer("active_headcount")
def _explain_active_headcount(db: Database, kpi_def: dict) -> dict:
    active = list(db.employees.find({"status": "active"},
                                    {"emp_id": 1, "name": 1, "department": 1}))
    return {
        "formula_text": "Count of employees with status = active.",
        "computation": f"{len(active)} employee(s) are active.",
        "inputs": [{"label": "Active employees", "value": len(active)}],
        "evidence": [{"kind": "employee", "id": e.get("emp_id"), "label": e.get("name"),
                     "extra": {"department": e.get("department")}}
                    for e in active[:MAX_EVIDENCE_ROWS]],
        "source": _seed_source("employees",
                               "Employee roster is seeded/harvested from OpenProject "
                               "assignees — no GreytHR connection yet."),
    }


def _explain_attendance_rate(db: Database, status: str) -> dict:
    cutoff = (dt.date.today() - dt.timedelta(days=30)).isoformat()
    scope = {"date": {"$gte": cutoff}}
    total = db.attendance.count_documents(scope)
    matching = list(db.attendance.find({**scope, "status": status}))
    value = round(len(matching) / total * 100, 2) if total else 0.0
    return {
        "formula_text": f"{status} attendance rows ÷ all attendance rows, "
                        f"last 30 days (since {cutoff}).",
        "computation": (f"{len(matching)} {status.lower()} / {total} total rows "
                        f"= {value}%") if total else "No attendance data in the "
                        "last 30 days.",
        "inputs": [{"label": f"{status} rows", "value": len(matching)},
                  {"label": "Total rows", "value": total}],
        "evidence": [{"kind": "attendance", "id": r.get("emp_code"), "label": r.get("name"),
                     "extra": {"date": r.get("date"), "status": r.get("status")}}
                    for r in matching[:MAX_EVIDENCE_ROWS]],
        "source": _seed_source("attendance",
                               "Attendance is seeded/uploaded via the HR biometric CSV "
                               "importer — see Admin → HR → Attendance."),
    }


@explainer("absenteeism_rate_30d")
def _explain_absenteeism(db: Database, kpi_def: dict) -> dict:
    return _explain_attendance_rate(db, "Absent")


@explainer("late_rate_30d")
def _explain_late_rate(db: Database, kpi_def: dict) -> dict:
    return _explain_attendance_rate(db, "Late")


@explainer("bug_resolution_days")
def _explain_bug_resolution(db: Database, kpi_def: dict) -> dict:
    q = {**_BUG_Q, "status": {"$in": CLOSED_BUG_STATUSES}}
    pnames = _project_names(db)
    resolved = []
    journal_backed = 0
    for b in db.tasks.find(q):
        created = _as_datetime(b.get("created_at"))
        closed_at = b.get("closed_at")
        closed = _as_datetime(closed_at) or _as_datetime(b.get("updated_at"))
        if created and closed and closed >= created:
            resolved.append((b, round((closed - created).total_seconds() / 86400, 1),
                            bool(closed_at)))
            if closed_at:
                journal_backed += 1
    value = round(mean(d for _, d, _ in resolved), 1) if resolved else None
    resolved.sort(key=lambda bd: -bd[1])
    return {
        "formula_text": "Mean of (closed_at − created_at) in days, across closed bugs "
                        "(status in Closed/Not a Bug/Done/...) — `closed_at` is the exact "
                        "moment the OpenProject Activity journal recorded the transition "
                        "into a terminal status; for bugs whose journal hasn't synced yet, "
                        "`updated_at` (last touch on the item) is used as a fallback proxy.",
        "computation": (f"{len(resolved)} closed bug(s) with timestamps average "
                        f"{value} day(s) to resolve ({journal_backed} from the exact "
                        f"journal closure time, {len(resolved) - journal_backed} from "
                        f"the updated_at proxy).") if resolved else
                       "No closed bugs have both created_at and a resolvable close "
                       "timestamp yet.",
        "inputs": [{"label": b.get("title"), "value": d} for b, d, _ in resolved[:MAX_EVIDENCE_ROWS]],
        "evidence": [{"kind": "bug", "id": b.get("source_id") or b.get("task_id"),
                     "label": b.get("title"), "url": work_package_url(b.get("source_id")),
                     "extra": {"days_to_resolve": d,
                              "closed_by": b.get("closed_by") if exact else None,
                              "source": "journal" if exact else "updated_at proxy",
                              "project": _task_project(b, pnames)}}
                    for b, d, exact in resolved[:MAX_EVIDENCE_ROWS]],
        "source": _source_info(db, "tasks", q),
    }


@explainer("bug_reopen_rate")
def _explain_bug_reopen_rate(db: Database, kpi_def: dict) -> dict:
    pnames = _project_names(db)
    docs = list(db.tasks.find(_BUG_Q))
    reopened = [d for d in docs
               if (d.get("reopen_count") or 0) >= 1 or d.get("status") == "Reopen"]
    terminal_clean = [d for d in docs if d.get("status") in CLOSED_BUG_STATUSES
                      and (d.get("reopen_count") or 0) < 1]
    denom = len(reopened) + len(terminal_clean)
    value = round(len(reopened) / denom * 100, 2) if denom else 0.0
    journal_backed = sum(1 for d in docs if d.get("journal_synced_updated_at"))
    return {
        "formula_text": "Bugs ever reopened ÷ (those + bugs closed cleanly without a "
                        "reopen). For bugs whose OpenProject Activity journal has synced, "
                        "'reopened' counts every transition OUT of a terminal status "
                        "(Closed/Not a Bug/Done/...) — including one that lands on a "
                        "status not literally named 'Reopen' (e.g. Closed → Developed), "
                        "which the older sync-time-diff signal alone would miss. Bugs "
                        "without a synced journal yet fall back to that diff signal "
                        "(reopen_count ≥ 1 or current status = Reopen).",
        "computation": (f"{len(reopened)} reopened / ({len(reopened)} + "
                        f"{len(terminal_clean)} cleanly-closed) = {value}% "
                        f"({journal_backed} of {len(docs)} bug(s) have journal-verified "
                        f"reopen counts).")
                       if denom else "No bug data ingested yet.",
        "inputs": [{"label": "Ever reopened", "value": len(reopened)},
                  {"label": "Closed cleanly", "value": len(terminal_clean)}],
        "evidence": [{"kind": "bug", "id": b.get("source_id") or b.get("task_id"),
                     "label": b.get("title"), "url": work_package_url(b.get("source_id")),
                     "extra": {"status": b.get("status"),
                              "reopen_count": b.get("reopen_count") or 0,
                              "journal_verified": bool(b.get("journal_synced_updated_at")),
                              "project": _task_project(b, pnames)}}
                    for b in reopened[:MAX_EVIDENCE_ROWS]],
        "source": _source_info(db, "tasks", _BUG_Q),
    }


@explainer("contact_coverage_30d")
def _explain_contact_coverage(db: Database, kpi_def: dict) -> dict:
    active = list(db.crm_contacts.find({"status": "active"}))
    today = dt.date.today()
    fresh = []
    for c in active:
        last = _as_date(c.get("last_contact"))
        if last and (today - last).days <= 30:
            fresh.append(c)
    value = round(len(fresh) / len(active) * 100, 2) if active else 0.0
    return {
        "formula_text": "Active CRM contacts with last_contact within the last 30 "
                        "days ÷ all active contacts.",
        "computation": (f"{len(fresh)} contacted in the last 30 days / {len(active)} "
                        f"active contact(s) = {value}%") if active else
                       "No active CRM contacts yet.",
        "inputs": [{"label": "Contacted within 30 days", "value": len(fresh)},
                  {"label": "Active contacts", "value": len(active)}],
        "evidence": [{"kind": "contact", "id": c.get("contact_id"), "label": c.get("name"),
                     "extra": {"project": c.get("project_id"),
                              "last_contact": c.get("last_contact")}}
                    for c in active[:MAX_EVIDENCE_ROWS]],
        "source": _seed_source("crm_contacts",
                               "CRM contacts are seeded — no HubSpot/CRM system "
                               "connected yet."),
    }


@explainer("static")
def _explain_static(db: Database, kpi_def: dict) -> dict:
    module = kpi_def.get("module", "")
    planned = PLANNED_SOURCE.get(module, "a future integration")
    value = kpi_def.get("demo_value")
    return {
        "formula_text": "Fixed demo placeholder — not computed from live data.",
        "computation": f"Demo value set at seed time: {value}.",
        "inputs": [],
        "evidence": [],
        "source": {
            "system": "None (demo)", "collection": None, "live": False,
            "last_sync": None,
            "note": f"Demo placeholder — {planned} is not connected yet "
                    f"(PRD section 8.1). Once wired, this KPI's formula in "
                    f"kpi/engine.py will compute a real value from that source.",
        },
    }


def explain(db: Database, kpi_def: dict, value) -> dict:
    fn = _EXPLAINERS.get(kpi_def.get("formula", "static"), _explain_static)
    result = fn(db, kpi_def)
    result["value"] = value
    return result
