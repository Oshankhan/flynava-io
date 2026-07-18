"""Assemble per-dashboard payloads from KPI snapshots + supporting widgets.

Each of the 8 role dashboards maps to a set of modules. The KPI list returned is
the intersection of the dashboard's modules and the caller's RBAC-accessible
modules, so the same endpoint is safe for every role. Payload extras:
`series` (12-month KPI trends for line charts) and `bug_breakdown` (bug counts
by status from OpenProject, for the donut chart).
"""
from __future__ import annotations

from collections import Counter

from pymongo.database import Database

from ..core import rbac
from ..insights.engine import DEPT_MODULE as INSIGHT_DEPT_MODULE
from ..kpi import engine

MAX_SERIES = 3

DASHBOARDS: dict[str, dict] = {
    "leadership": {"title": "Leadership",
                   "modules": ["operations", "finance", "hr", "marketing_sales",
                               "product_dev", "compliance", "ai_insights"],
                   "show_projects": True,
                   "insight_depts": ["operations", "finance", "hr", "marketing"]},
    "manager": {"title": "Manager",
                "modules": ["operations", "product_dev", "customer_support"],
                "show_projects": True, "insight_depts": ["operations"]},
    "hr": {"title": "HR", "modules": ["hr", "recruitment", "compliance", "awards"],
           "show_projects": False, "insight_depts": ["hr"]},
    "finance": {"title": "Finance", "modules": ["finance"], "show_projects": False,
                "insight_depts": ["finance"]},
    "marketing": {"title": "Marketing & Sales", "modules": ["marketing_sales"],
                  "show_projects": False, "insight_depts": ["marketing"]},
    "employee": {"title": "Employee", "modules": ["operations", "awards",
                 "ai_insights"], "show_projects": True, "insight_depts": []},
    "investor": {"title": "Investor",
                 "modules": ["finance", "marketing_sales", "operations",
                             "product_dev", "customer_support"],
                 "show_projects": False, "insight_depts": ["finance", "operations"]},
    "partner": {"title": "Partner",
                "modules": ["operations", "customer_support"],
                "show_projects": True, "insight_depts": []},
}


def _project_rag(progress: float, expected: float | None) -> str:
    if not expected:
        return "grey"
    if progress >= expected:
        return "green"
    return "amber" if progress >= 0.7 * expected else "red"


# Which roles may OPEN each dashboard (screen visibility). super_admin +
# leadership see everything; every other role sees its own view (+ the shared
# personal "employee" view for internal staff). This gates the sidebar and the
# GET /dashboards/{key} endpoint. KPI-level filtering in build() is defence in
# depth on top of this.
_ALL = {"super_admin", "leadership"}
DASHBOARD_ROLES: dict[str, set[str]] = {
    "leadership": _ALL,
    "manager": _ALL | {"manager", "team_lead"},
    "hr": _ALL | {"hr"},
    "finance": _ALL | {"investor"},
    "marketing": _ALL | {"marketing"},
    "employee": _ALL | {"manager", "hr", "employee", "marketing", "team_lead"},
    "investor": _ALL | {"investor"},
    "partner": _ALL | {"partner"},
}


def can_view(user: dict, key: str) -> bool:
    allowed = DASHBOARD_ROLES.get(key, set())
    return any(r in allowed for r in rbac.user_roles(user))


# Modules whose KPIs are computed from OpenProject-shaped data (`tasks`/
# `projects` carrying `project_source_id`/`source_id`) — the only ones a
# project scope can actually apply to. Finance/HR/marketing KPIs aren't
# project-shaped and stay global regardless of the selector.
PROJECT_SCOPABLE_MODULES = {"operations", "product_dev"}


def _bug_breakdown(db: Database, project: str | None = None) -> list[dict]:
    q = {"wp_type": {"$regex": "bug", "$options": "i"}}
    if project:
        q["project_source_id"] = project
    counts = Counter(t.get("status") or "Unknown" for t in db.tasks.find(q, {"status": 1}))
    return [{"status": s, "count": n} for s, n in counts.most_common(8)]


def _series(kpis: list[dict], hist_map: dict[str, list[dict]],
           scoped_kpi_ids: set[str]) -> list[dict]:
    """The (capped) trend-chart series — only the first few KPIs with enough
    history, for the big line charts below the KPI grid. KPIs whose headline
    value is project-scoped are skipped: their history is global, so pairing
    it with a scoped number would be misleading."""
    out = []
    for k in kpis:
        if k["kpi_id"] in scoped_kpi_ids:
            continue
        hist = hist_map.get(k["kpi_id"], [])
        if len(hist) >= 3:
            out.append({"kpi_id": k["kpi_id"], "name": k["name"],
                        "unit": k.get("unit"), "points": hist})
        if len(out) >= MAX_SERIES:
            break
    return out


def build(db: Database, key: str, user: dict, project: str | None = None) -> dict:
    spec = DASHBOARDS[key]
    accessible = set(rbac.accessible_modules_for_user(user))
    modules = [m for m in spec["modules"] if m in accessible]
    kpis = engine.latest_snapshot(db, modules) if modules else []

    # One batched history read, reused for both per-card sparklines (all KPIs)
    # and the capped trend-chart series (a few KPIs).
    hist_map = engine.history_bulk(db, [k["kpi_id"] for k in kpis])
    for k in kpis:
        pts = hist_map.get(k["kpi_id"], [])
        if len(pts) >= 3:
            k["spark"] = pts

    # Project scope: recompute operations/product_dev KPIs live, filtered to
    # one OpenProject project, instead of reading their (necessarily global)
    # stored kpi_values. No history exists for a one-off scoped number, so
    # these drop their change arrow and sparkline rather than show a stale
    # unscoped one next to a scoped headline value.
    scoped_kpi_ids: set[str] = set()
    if project:
        defs_by_id = {d["kpi_id"]: d for d in
                     db.kpi_defs.find({"kpi_id": {"$in": [k["kpi_id"] for k in kpis]}})}
        for k in kpis:
            d = defs_by_id.get(k["kpi_id"])
            if not d or d["module"] not in PROJECT_SCOPABLE_MODULES:
                continue
            value = engine.compute(db, d, project)
            k["value"] = value
            k["rag"] = engine.rag_status(value, d.get("target"), d.get("direction", "higher"))
            k["change_pct"] = None
            k.pop("spark", None)
            scoped_kpi_ids.add(k["kpi_id"])

    projects = []
    if spec["show_projects"]:
        proj_q = {"status": "active", **({"source_id": project} if project else {})}
        for p in db.projects.find(proj_q):
            projects.append({
                "project_id": p.get("project_id") or p.get("source_id"),
                "name": p.get("name"),
                "progress": p.get("progress", 0),
                "expected_progress": p.get("expected_progress"),
                "rag": _project_rag(p.get("progress", 0), p.get("expected_progress")),
            })

    alerts = []
    for a in db.alerts.find({"status": "open"}).sort("created_at", -1).limit(10):
        a["_id"] = str(a["_id"])
        alerts.append(a)

    insight_depts = [d for d in spec.get("insight_depts", [])
                     if INSIGHT_DEPT_MODULE.get(d) in accessible]

    payload = {"key": key, "title": spec["title"], "kpis": kpis,
               "projects": projects, "alerts": alerts, "project": project,
               "series": _series(kpis, hist_map, scoped_kpi_ids),
               "insight_depts": insight_depts}

    if "product_dev" in modules:
        breakdown = _bug_breakdown(db, project)
        if breakdown:
            payload["bug_breakdown"] = breakdown
    return payload
