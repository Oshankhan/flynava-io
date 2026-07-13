"""Report generation engine.

A report definition (`report_defs`) carries a list of `sections`, each naming
a builder `kind` + `params`. `run_report` calls each builder and stores the
result as an immutable `report_runs` snapshot (history/versioning). Adding a
new report data source = a new `@builder` function — same extension pattern
as `kpi/engine.py`'s `@computer` registry.

All aggregation here is plain Python loops over `find()` cursors, never
`$group`/`$facet` — the test suite runs on mongomock, which doesn't implement
the aggregation pipeline (same constraint `api/v1/analytics.py` works under).
"""
from __future__ import annotations

import csv
import datetime as dt
import html as html_lib
import io
import json
import uuid
from typing import Callable

from fastapi import HTTPException, status
from pymongo.database import Database

from ..ai.provider import get_provider
from ..core.rbac import user_level
from ..kpi import engine as kpi_engine
from .report_store import is_ceo_tier

Builder = Callable[[Database, dict, dict, dict], dict]
_BUILDERS: dict[str, Builder] = {}

DOMAINS = ["development", "qa", "operations", "projects", "marketing", "sales",
           "finance", "hr", "infrastructure"]
TYPES = ["tabular", "chart", "summary", "dashboard"]
MAX_ROWS = 200

# Builder kinds whose data is billing/salary-sensitive — re-checked at
# generation time in addition to the report def's own visibility gate
# (defense in depth: a def's confidential flag could in principle drift from
# its section content).
CONFIDENTIAL_KINDS = {
    "payroll_summary", "finance_budget", "aws_monthly_cost", "aws_cost_by_service",
    "aws_trends", "aws_budget_vs_actual", "aws_optimization",
}


def builder(kind: str):
    def wrap(fn: Builder) -> Builder:
        _BUILDERS[kind] = fn
        return fn

    return wrap


def section_kinds() -> list[str]:
    return list(_BUILDERS)


def section_catalog(user: dict) -> list[dict]:
    """Section kinds this user is allowed to add to a report, for the wizard."""
    privileged = is_ceo_tier(user) or user.get("role") == "hr" or user_level(user) >= 3
    return [
        {"kind": k, "confidential": k in CONFIDENTIAL_KINDS}
        for k in _BUILDERS
        if k not in CONFIDENTIAL_KINDS or privileged
    ]


def _require(cond: bool, msg: str) -> None:
    if not cond:
        raise HTTPException(status.HTTP_403_FORBIDDEN, msg)


def _owner_or(user: dict, rd: dict, ok: bool) -> bool:
    # The report's own owner can always generate it — a role-only check would
    # otherwise lock a def's creator out of their own confidential report
    # (e.g. a Finance Manager whose seeded `role` is "manager", not "hr").
    return ok or user["user_id"] == rd.get("owner_id")


def _require_payroll_access(user: dict, rd: dict) -> None:
    ok = user.get("role") in {"hr", "super_admin", "leadership"}
    _require(_owner_or(user, rd, ok), "payroll data requires HR/leadership access")


def _require_finance_access(user: dict, rd: dict) -> None:
    ok = is_ceo_tier(user) or (user.get("department") == "fin" and user_level(user) >= 3)
    _require(_owner_or(user, rd, ok), "finance data requires finance/leadership access")


def _require_aws_billing_access(user: dict, rd: dict) -> None:
    ok = is_ceo_tier(user) or user["user_id"] in (rd.get("allowed_user_ids") or [])
    _require(_owner_or(user, rd, ok), "AWS billing data requires authorized access")


# --- Development / QA / Operations ---
@builder("tasks_table")
def _tasks_table(db: Database, params: dict, user: dict, rd: dict) -> dict:
    q: dict = {}
    if params.get("project_id"):
        q["project_id"] = params["project_id"]
    if params.get("bug_only"):
        q["wp_type"] = {"$regex": "bug", "$options": "i"}
    if params.get("status"):
        q["status"] = params["status"]
    if params.get("assignee_id"):
        q["assignee_id"] = params["assignee_id"]
    rows = list(db.tasks.find(q).limit(MAX_ROWS))
    columns = [{"key": "title", "label": "Task"}, {"key": "status", "label": "Status"},
               {"key": "priority", "label": "Priority"}, {"key": "assignee", "label": "Assignee"},
               {"key": "due_date", "label": "Due"}]
    out_rows = [{"title": r.get("title"), "status": r.get("status"), "priority": r.get("priority"),
                 "assignee": r.get("assignee"), "due_date": r.get("due_date")} for r in rows]
    return {"key": "tasks_table", "title": params.get("title", "Tasks"), "kind": "table",
            "columns": columns, "rows": out_rows}


@builder("tasks_breakdown")
def _tasks_breakdown(db: Database, params: dict, user: dict, rd: dict) -> dict:
    q: dict = {}
    if params.get("project_id"):
        q["project_id"] = params["project_id"]
    if params.get("bug_only"):
        q["wp_type"] = {"$regex": "bug", "$options": "i"}
    if params.get("assignee_id"):
        q["assignee_id"] = params["assignee_id"]
    group_by = params.get("group_by", "status")
    counts: dict[str, int] = {}
    for r in db.tasks.find(q, {group_by: 1}):
        key = r.get(group_by) or "—"
        counts[key] = counts.get(key, 0) + 1
    stats = [{"label": k, "value": v} for k, v in sorted(counts.items(), key=lambda kv: -kv[1])]
    return {"key": "tasks_breakdown", "title": params.get("title", f"By {group_by}"), "kind": "stats",
            "stats": stats}


@builder("test_execution")
def _test_execution(db: Database, params: dict, user: dict, rd: dict) -> dict:
    q = {"module": params["module"]} if params.get("module") else {}
    rows = list(db.automation_scripts.find(q).limit(MAX_ROWS))
    columns = [{"key": "title", "label": "Test"}, {"key": "module", "label": "Module"},
               {"key": "owner", "label": "Owner"}, {"key": "status", "label": "Status"}]
    out_rows = [{"title": r.get("title"), "module": r.get("module"), "owner": r.get("owner"),
                 "status": r.get("status")} for r in rows]
    return {"key": "test_execution", "title": "Test Case Execution", "kind": "table",
            "columns": columns, "rows": out_rows}


@builder("test_execution_stats")
def _test_execution_stats(db: Database, params: dict, user: dict, rd: dict) -> dict:
    q = {"module": params["module"]} if params.get("module") else {}
    rows = list(db.automation_scripts.find(q))
    total = len(rows)
    done = sum(1 for r in rows if r.get("status") == "done")
    pending = sum(1 for r in rows if r.get("status") == "pending")
    in_review = sum(1 for r in rows if r.get("status") == "in_review")
    pass_rate = round(done / total * 100, 1) if total else 0.0
    stats = [{"label": "Total Test Cases", "value": total}, {"label": "Passed", "value": done},
              {"label": "Pending", "value": pending}, {"label": "In Review", "value": in_review},
              {"label": "Pass Rate", "value": pass_rate, "unit": "%"}]
    return {"key": "test_execution_stats", "title": "Execution Summary", "kind": "stats", "stats": stats}


@builder("kpi_stats")
def _kpi_stats(db: Database, params: dict, user: dict, rd: dict) -> dict:
    module = params.get("module")
    kpi_ids = params.get("kpi_ids")
    snapshot = kpi_engine.latest_snapshot(db, [module] if module else None)
    if kpi_ids:
        snapshot = [s for s in snapshot if s["kpi_id"] in kpi_ids]
    stats = [{"label": s["name"], "value": s["value"], "unit": s.get("unit"),
              "delta": s.get("change_pct"), "rag": s.get("rag")} for s in snapshot]
    return {"key": "kpi_stats", "title": params.get("title", "KPI Snapshot"), "kind": "stats", "stats": stats}


@builder("kpi_trend")
def _kpi_trend(db: Database, params: dict, user: dict, rd: dict) -> dict:
    module = params.get("module")
    kpi_ids = params.get("kpi_ids")
    if not kpi_ids:
        kpi_ids = [d["kpi_id"] for d in db.kpi_defs.find({"module": module} if module else {})]
    hist = kpi_engine.history_bulk(db, kpi_ids, n=12)
    names = {d["kpi_id"]: d["name"] for d in db.kpi_defs.find({"kpi_id": {"$in": kpi_ids}})}
    series = [{"name": names.get(kid, kid), "points": pts} for kid, pts in hist.items() if pts]
    return {"key": "kpi_trend", "title": params.get("title", "Trend"), "kind": "chart", "series": series}


# --- HR / Finance (payroll & finance_budget are confidential-class) ---
@builder("attendance_summary")
def _attendance_summary(db: Database, params: dict, user: dict, rd: dict) -> dict:
    days = params.get("days", 7)
    cutoff = (dt.date.today() - dt.timedelta(days=days)).isoformat()
    rows = list(db.attendance.find({"date": {"$gte": cutoff}}))
    counts: dict[str, int] = {}
    for r in rows:
        s = r.get("status", "Unknown")
        counts[s] = counts.get(s, 0) + 1
    stats = [{"label": k, "value": v} for k, v in counts.items()]
    stats.append({"label": "Total Records", "value": len(rows)})
    return {"key": "attendance_summary", "title": "Attendance Summary", "kind": "stats", "stats": stats}


@builder("leaves_summary")
def _leaves_summary(db: Database, params: dict, user: dict, rd: dict) -> dict:
    rows = list(db.leaves.find({}))
    by_status: dict[str, int] = {}
    by_type: dict[str, int] = {}
    for r in rows:
        by_status[r.get("status", "?")] = by_status.get(r.get("status", "?"), 0) + 1
        by_type[r.get("type", "?")] = by_type.get(r.get("type", "?"), 0) + 1
    stats = [{"label": f"{k} leaves", "value": v} for k, v in by_status.items()]
    stats += [{"label": f"{k} (type)", "value": v} for k, v in by_type.items()]
    return {"key": "leaves_summary", "title": "Leave Summary", "kind": "stats", "stats": stats}


@builder("payroll_summary")
def _payroll_summary(db: Database, params: dict, user: dict, rd: dict) -> dict:
    _require_payroll_access(user, rd)
    rows = list(db.payslips.find({}))
    by_month: dict[str, float] = {}
    for r in rows:
        by_month[r["month"]] = by_month.get(r["month"], 0) + r.get("gross", 0)
    columns = [{"key": "month", "label": "Month"}, {"key": "total_gross", "label": "Total Gross"}]
    table_rows = [{"month": m, "total_gross": round(v, 2)} for m, v in sorted(by_month.items())]
    return {"key": "payroll_summary", "title": "Payroll Cost Summary", "kind": "table",
            "columns": columns, "rows": table_rows}


@builder("finance_budget")
def _finance_budget(db: Database, params: dict, user: dict, rd: dict) -> dict:
    _require_finance_access(user, rd)
    kpi_id = params.get("kpi_id", "fin_revenue_mtd")
    d = db.kpi_defs.find_one({"kpi_id": kpi_id})
    target = d.get("target") if d else None
    hist = kpi_engine.history(db, kpi_id, n=12)
    series = [{"name": "Actual", "points": hist}]
    if target:
        series.append({"name": "Budget", "points": [{"t": p["t"], "v": target} for p in hist]})
    return {"key": "finance_budget", "title": "Budget vs Actual", "kind": "chart", "series": series}


@builder("documents_stats")
def _documents_stats(db: Database, params: dict, user: dict, rd: dict) -> dict:
    docs = list(db.documents.find({}))
    by_status: dict[str, int] = {}
    for d in docs:
        by_status[d.get("status", "?")] = by_status.get(d.get("status", "?"), 0) + 1
    stats = [{"label": f"{k.title()} Docs", "value": v} for k, v in by_status.items()]
    stats.append({"label": "Total Downloads", "value": sum(d.get("downloads", 0) for d in docs)})
    return {"key": "documents_stats", "title": "Document Upload Summary", "kind": "stats", "stats": stats}


@builder("audit_activity")
def _audit_activity(db: Database, params: dict, user: dict, rd: dict) -> dict:
    days = params.get("days", 30)
    cutoff = dt.datetime.now(dt.timezone.utc) - dt.timedelta(days=days)
    rows = list(db.audit_logs.find({"created_at": {"$gte": cutoff}}))
    by_action: dict[str, int] = {}
    by_actor: dict[str, int] = {}
    for r in rows:
        by_action[r.get("action", "?")] = by_action.get(r.get("action", "?"), 0) + 1
        if r.get("actor_id"):
            by_actor[r["actor_id"]] = by_actor.get(r["actor_id"], 0) + 1
    top_actions = sorted(by_action.items(), key=lambda kv: -kv[1])[:5]
    stats = [{"label": "Total Actions", "value": len(rows)}]
    stats += [{"label": f"Top: {a}", "value": n} for a, n in top_actions]
    return {"key": "audit_activity", "title": "Activity Summary", "kind": "stats", "stats": stats}


# --- Infrastructure / AWS (simulated connector data — see integrations/aws_sim.py) ---
@builder("aws_monthly_cost")
def _aws_monthly_cost(db: Database, params: dict, user: dict, rd: dict) -> dict:
    _require_aws_billing_access(user, rd)
    totals: dict[str, float] = {}
    for c in db.aws_costs.find({}):
        totals[c["month"]] = totals.get(c["month"], 0) + c["cost"]
    points = [{"t": m, "v": round(v, 2)} for m, v in sorted(totals.items())]
    return {"key": "aws_monthly_cost", "title": "AWS Monthly Cost", "kind": "chart",
            "series": [{"name": "Total Cost", "points": points}]}


@builder("aws_cost_by_service")
def _aws_cost_by_service(db: Database, params: dict, user: dict, rd: dict) -> dict:
    _require_aws_billing_access(user, rd)
    months = sorted({c["month"] for c in db.aws_costs.find({}, {"month": 1})})
    if not months:
        return {"key": "aws_cost_by_service", "title": "AWS Cost by Service", "kind": "table",
                "columns": [], "rows": []}
    latest = months[-1]
    prior = months[-2] if len(months) > 1 else None
    latest_costs = {c["service"]: c["cost"] for c in db.aws_costs.find({"month": latest})}
    prior_costs = {c["service"]: c["cost"] for c in db.aws_costs.find({"month": prior})} if prior else {}
    rows = []
    for svc, cost in sorted(latest_costs.items(), key=lambda kv: -kv[1]):
        prev = prior_costs.get(svc)
        delta = round((cost - prev) / prev * 100, 1) if prev else None
        rows.append({"service": svc, "cost": round(cost, 2), "change_pct": delta})
    columns = [{"key": "service", "label": "Service"}, {"key": "cost", "label": "Cost (USD)"},
               {"key": "change_pct", "label": "MoM Change %"}]
    return {"key": "aws_cost_by_service", "title": f"AWS Cost by Service ({latest})", "kind": "table",
            "columns": columns, "rows": rows}


@builder("aws_utilization")
def _aws_utilization(db: Database, params: dict, user: dict, rd: dict) -> dict:
    rows = list(db.aws_resources.find({}).sort("utilization_pct", 1))
    columns = [{"key": "name", "label": "Resource"}, {"key": "service", "label": "Service"},
               {"key": "region", "label": "Region"}, {"key": "utilization_pct", "label": "Utilization %"},
               {"key": "monthly_cost", "label": "Monthly Cost"}]
    out_rows = [{"name": r["name"], "service": r["service"], "region": r["region"],
                 "utilization_pct": r["utilization_pct"], "monthly_cost": r["monthly_cost"]} for r in rows]
    return {"key": "aws_utilization", "title": "Resource Utilization", "kind": "table",
            "columns": columns, "rows": out_rows}


@builder("aws_resource_health")
def _aws_resource_health(db: Database, params: dict, user: dict, rd: dict) -> dict:
    rows = list(db.aws_resources.find({}))
    columns = [{"key": "name", "label": "Resource"}, {"key": "service", "label": "Service"},
               {"key": "health", "label": "Health"}, {"key": "utilization_pct", "label": "Utilization %"}]
    order = {"critical": 0, "warning": 1, "ok": 2}
    out_rows = sorted(
        [{"name": r["name"], "service": r["service"], "health": r["health"],
          "utilization_pct": r["utilization_pct"]} for r in rows],
        key=lambda r: order.get(r["health"], 3),
    )
    return {"key": "aws_resource_health", "title": "Resource Health & Availability", "kind": "table",
            "columns": columns, "rows": out_rows}


@builder("aws_trends")
def _aws_trends(db: Database, params: dict, user: dict, rd: dict) -> dict:
    _require_aws_billing_access(user, rd)
    by_service: dict[str, dict[str, float]] = {}
    for c in db.aws_costs.find({}):
        by_service.setdefault(c["service"], {})[c["month"]] = c["cost"]
    series = [{"name": svc, "points": [{"t": m, "v": round(v, 2)} for m, v in sorted(months.items())]}
              for svc, months in by_service.items()]
    return {"key": "aws_trends", "title": "Cloud Spending Trends", "kind": "chart", "series": series}


@builder("aws_optimization")
def _aws_optimization(db: Database, params: dict, user: dict, rd: dict) -> dict:
    _require_aws_billing_access(user, rd)
    recs: list[str] = []
    for r in db.aws_resources.find({}):
        if r["utilization_pct"] < 25:
            recs.append(f"Rightsize or terminate {r['name']} ({r['service']}) — "
                        f"utilization only {r['utilization_pct']}%.")
        if r["health"] == "critical":
            recs.append(f"Investigate {r['name']} ({r['service']}) — health status critical.")
    if db.aws_resources.count_documents({"service": "S3"}):
        recs.append("Consider S3 lifecycle policies to move cold data to cheaper storage tiers.")
    if not recs:
        recs.append("No optimization opportunities detected — utilization and health look healthy.")
    return {"key": "aws_optimization", "title": "Cost Optimization Recommendations", "kind": "text",
            "text": "\n".join(f"• {r}" for r in recs)}


@builder("aws_budget_vs_actual")
def _aws_budget_vs_actual(db: Database, params: dict, user: dict, rd: dict) -> dict:
    _require_aws_billing_access(user, rd)
    totals: dict[str, float] = {}
    for c in db.aws_costs.find({}):
        totals[c["month"]] = totals.get(c["month"], 0) + c["cost"]
    budgets = {b["month"]: b["amount"] for b in db.aws_budgets.find({})}
    months = sorted(totals)
    return {"key": "aws_budget_vs_actual", "title": "Budget vs Actual Cloud Spend", "kind": "chart",
            "series": [
                {"name": "Actual", "points": [{"t": m, "v": round(totals[m], 2)} for m in months]},
                {"name": "Budget", "points": [{"t": m, "v": round(budgets.get(m, 0), 2)} for m in months]},
            ]}


# --- Run / AI summary / email / exports ---
def run_report(db: Database, rd: dict, user: dict, triggered_by: str = "manual") -> dict:
    sections = []
    for i, spec in enumerate(rd.get("sections") or []):
        kind = spec.get("kind")
        params = spec.get("params") or {}
        fn = _BUILDERS.get(kind)
        try:
            if fn is None:
                raise ValueError(f"unknown section kind: {kind}")
            section = fn(db, params, user, rd)
        except HTTPException:
            raise  # confidential re-check failures abort the whole run
        except Exception as exc:  # noqa: BLE001 - one bad section shouldn't kill the run
            section = {"key": f"{kind}_{i}", "title": spec.get("title") or kind or "Section",
                       "kind": "text", "text": f"Error generating this section: {exc}"}
        if section.get("rows") and len(section["rows"]) > MAX_ROWS:
            section["rows"] = section["rows"][:MAX_ROWS]
        sections.append(section)

    now = dt.datetime.now(dt.timezone.utc)
    version = db.report_runs.count_documents({"report_id": rd["report_id"]}) + 1
    run = {
        "run_id": "run_" + uuid.uuid4().hex[:8], "report_id": rd["report_id"], "at": now,
        "version": version, "triggered_by": triggered_by, "actor_id": user["user_id"],
        "status": "ok", "sections": sections, "ai_summary": None,
        "recipients": [], "delivery": {"status": "none", "detail": ""},
    }
    db.report_runs.insert_one(run)
    db.report_defs.update_one({"report_id": rd["report_id"]}, {"$inc": {"run_count": 1}})
    run.pop("_id", None)
    return run


def ai_summary(rd: dict, sections: list[dict]) -> str:
    bits = []
    for s in sections:
        if s["kind"] == "stats":
            for st in (s.get("stats") or [])[:5]:
                bits.append(f"{st['label']}: {st['value']}")
        elif s["kind"] == "table":
            bits.append(f"{s['title']}: {len(s.get('rows') or [])} rows")
        elif s["kind"] == "chart":
            bits.append(f"{s['title']}: {len(s.get('series') or [])} series")
    digest = "; ".join(bits) or "no data available"
    system = ("Write a concise 2-3 sentence executive summary of this business report. "
              "Respond as JSON with key 'answer' only.")
    user_msg = f"Report: {rd['name']} ({rd['domain']}). Sections: {digest}"
    try:
        raw = get_provider().complete(system, user_msg)
        return json.loads(raw).get("answer", "")
    except Exception:  # noqa: BLE001 -- summary is optional, never fail the report
        return f"{rd['name']}: {len(sections)} section(s) generated. Review the data below for details."


def render_report_email_html(rd: dict, run: dict) -> str:
    def td(v) -> str:
        return f'<td style="border:1px solid #d9d9d9;padding:6px 10px;font-size:13px;">{html_lib.escape(str(v if v is not None else "—"))}</td>'

    parts = ['<div style="font-family:Segoe UI,Arial,sans-serif;color:#1f1f1f;">',
             f"<p>Hi Team,</p><h3>{html_lib.escape(rd['name'])}</h3>"]
    if run.get("ai_summary"):
        parts.append(f'<p style="color:#374151;">{html_lib.escape(run["ai_summary"])}</p>')
    for s in run.get("sections") or []:
        parts.append(f'<h4 style="margin-bottom:4px;">{html_lib.escape(s["title"])}</h4>')
        if s["kind"] == "table" and s.get("rows"):
            cols = s.get("columns") or [{"key": k, "label": k} for k in s["rows"][0]]
            head = "".join(
                f'<th style="border:1px solid #d9d9d9;padding:6px 10px;background:#157f52;'
                f'color:#fff;font-size:13px;text-align:left;">{html_lib.escape(c["label"])}</th>'
                for c in cols)
            body = "".join(
                "<tr>" + "".join(td(r.get(c["key"])) for c in cols) + "</tr>"
                for r in s["rows"][:10])
            parts.append(f'<table style="border-collapse:collapse;margin-bottom:12px;">'
                         f"<thead><tr>{head}</tr></thead><tbody>{body}</tbody></table>")
        elif s["kind"] == "stats" and s.get("stats"):
            lines = "".join(f"<li>{html_lib.escape(st['label'])}: <b>{html_lib.escape(str(st['value']))}"
                            f"{html_lib.escape(str(st.get('unit') or ''))}</b></li>" for st in s["stats"])
            parts.append(f"<ul>{lines}</ul>")
        elif s["kind"] == "text" and s.get("text"):
            parts.append(f'<p style="white-space:pre-line;">{html_lib.escape(s["text"])}</p>')
    parts.append('<p style="margin-top:12px;color:#6b7280;font-size:12px;">'
                 "Generated by IO — FlyNava Technologies</p></div>")
    return "".join(parts)


def to_csv(run: dict) -> str:
    out = io.StringIO()
    w = csv.writer(out)
    for s in run.get("sections") or []:
        w.writerow([s["title"]])
        if s["kind"] == "table" and s.get("rows"):
            cols = s.get("columns") or [{"key": k, "label": k} for k in s["rows"][0]]
            w.writerow([c["label"] for c in cols])
            for r in s["rows"]:
                w.writerow([r.get(c["key"]) for c in cols])
        elif s["kind"] == "stats" and s.get("stats"):
            for st in s["stats"]:
                w.writerow([st["label"], st["value"]])
        elif s["kind"] == "text" and s.get("text"):
            w.writerow([s["text"]])
        w.writerow([])
    return out.getvalue()


def to_xls_html(run: dict) -> str:
    parts = ['<html><body>']
    for s in run.get("sections") or []:
        parts.append(f"<h3>{html_lib.escape(s['title'])}</h3>")
        if s["kind"] == "table" and s.get("rows"):
            cols = s.get("columns") or [{"key": k, "label": k} for k in s["rows"][0]]
            head = "".join(f"<th>{html_lib.escape(c['label'])}</th>" for c in cols)
            body = "".join(
                "<tr>" + "".join(f"<td>{html_lib.escape(str(r.get(c['key'], '')))}</td>" for c in cols) + "</tr>"
                for r in s["rows"])
            parts.append(f"<table border='1'><thead><tr>{head}</tr></thead><tbody>{body}</tbody></table>")
        elif s["kind"] == "stats" and s.get("stats"):
            rows = "".join(f"<tr><td>{html_lib.escape(st['label'])}</td><td>{html_lib.escape(str(st['value']))}</td></tr>"
                           for st in s["stats"])
            parts.append(f"<table border='1'>{rows}</table>")
        elif s["kind"] == "text" and s.get("text"):
            parts.append(f"<p>{html_lib.escape(s['text'])}</p>")
    parts.append("</body></html>")
    return "".join(parts)


TEMPLATES: list[dict] = [
    {"template_id": "tpl_bug_summary", "name": "Bug Status Summary",
     "description": "Open/closed bug breakdown for a project.", "domain": "development", "type": "tabular",
     "sections": [{"kind": "tasks_table", "params": {"bug_only": True}},
                  {"kind": "tasks_breakdown", "params": {"bug_only": True, "group_by": "status"}}]},
    {"template_id": "tpl_team_progress", "name": "Team Task Progress",
     "description": "Task progress across teams and projects.", "domain": "development", "type": "tabular",
     "sections": [{"kind": "tasks_table", "params": {}}, {"kind": "tasks_breakdown", "params": {"group_by": "status"}}]},
    {"template_id": "tpl_test_execution", "name": "Test Case Execution",
     "description": "Automation test run results and pass rate.", "domain": "qa", "type": "tabular",
     "sections": [{"kind": "test_execution", "params": {}}, {"kind": "test_execution_stats", "params": {}}]},
    {"template_id": "tpl_resource_util", "name": "Resource Utilization",
     "description": "Operations KPI trend and snapshot.", "domain": "operations", "type": "chart",
     "sections": [{"kind": "kpi_stats", "params": {"module": "operations"}},
                  {"kind": "kpi_trend", "params": {"module": "operations"}}]},
    {"template_id": "tpl_campaign_perf", "name": "Campaign Performance",
     "description": "Marketing funnel KPI trend.", "domain": "marketing", "type": "chart",
     "sections": [{"kind": "kpi_trend", "params": {"module": "marketing_sales"}}]},
    {"template_id": "tpl_mkt_funnel", "name": "Marketing Funnel Summary",
     "description": "Leads, conversion, pipeline snapshot.", "domain": "marketing", "type": "summary",
     "sections": [{"kind": "kpi_stats", "params": {"module": "marketing_sales"}}]},
    {"template_id": "tpl_doc_summary", "name": "Document Upload Summary",
     "description": "Document uploads by status and downloads.", "domain": "operations", "type": "tabular",
     "sections": [{"kind": "documents_stats", "params": {}}]},
    {"template_id": "tpl_attendance", "name": "Attendance & Leave Summary",
     "description": "Attendance and leave request snapshot.", "domain": "hr", "type": "summary",
     "sections": [{"kind": "attendance_summary", "params": {"days": 7}}, {"kind": "leaves_summary", "params": {}}]},
    {"template_id": "tpl_payroll", "name": "Payroll Cost Summary",
     "description": "Monthly payroll cost totals (confidential).", "domain": "finance", "type": "tabular",
     "sections": [{"kind": "payroll_summary", "params": {}}]},
    {"template_id": "tpl_budget_actual", "name": "Budget vs Actual",
     "description": "Revenue budget vs actual trend (confidential).", "domain": "finance", "type": "chart",
     "sections": [{"kind": "finance_budget", "params": {"kpi_id": "fin_revenue_mtd"}}]},
    {"template_id": "tpl_aws_monthly", "name": "AWS Monthly Cost",
     "description": "Total AWS spend trend (confidential).", "domain": "infrastructure", "type": "chart",
     "sections": [{"kind": "aws_monthly_cost", "params": {}}]},
    {"template_id": "tpl_aws_services", "name": "AWS Cost by Service",
     "description": "Latest-month spend by AWS service (confidential).", "domain": "infrastructure", "type": "tabular",
     "sections": [{"kind": "aws_cost_by_service", "params": {}}]},
    {"template_id": "tpl_aws_health", "name": "AWS Utilization & Health",
     "description": "Resource utilization and health dashboard.", "domain": "infrastructure", "type": "dashboard",
     "sections": [{"kind": "aws_utilization", "params": {}}, {"kind": "aws_resource_health", "params": {}}]},
    {"template_id": "tpl_aws_optim", "name": "AWS Optimization Recommendations",
     "description": "Cost-saving recommendations (confidential).", "domain": "infrastructure", "type": "summary",
     "sections": [{"kind": "aws_optimization", "params": {}}, {"kind": "aws_budget_vs_actual", "params": {}}]},
]
