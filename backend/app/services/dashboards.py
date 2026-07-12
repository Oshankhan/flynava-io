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
from ..kpi import engine

MAX_SERIES = 3

DASHBOARDS: dict[str, dict] = {
    "leadership": {"title": "Leadership",
                   "modules": ["operations", "finance", "hr", "marketing_sales",
                               "product_dev", "compliance", "ai_insights"],
                   "show_projects": True},
    "manager": {"title": "Manager",
                "modules": ["operations", "product_dev", "customer_support"],
                "show_projects": True},
    "hr": {"title": "HR", "modules": ["hr", "recruitment", "compliance", "awards"],
           "show_projects": False},
    "finance": {"title": "Finance", "modules": ["finance"], "show_projects": False},
    "marketing": {"title": "Marketing & Sales", "modules": ["marketing_sales"],
                  "show_projects": False},
    "employee": {"title": "Employee", "modules": ["operations", "awards",
                 "ai_insights"], "show_projects": True},
    "investor": {"title": "Investor",
                 "modules": ["finance", "marketing_sales", "operations",
                             "product_dev", "customer_support"],
                 "show_projects": False},
    "partner": {"title": "Partner",
                "modules": ["operations", "customer_support"],
                "show_projects": True},
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


def _bug_breakdown(db: Database) -> list[dict]:
    counts = Counter(
        t.get("status") or "Unknown"
        for t in db.tasks.find({"wp_type": {"$regex": "bug", "$options": "i"}},
                               {"status": 1}))
    return [{"status": s, "count": n} for s, n in counts.most_common(8)]


def _series(db: Database, kpis: list[dict]) -> list[dict]:
    hist_map = engine.history_bulk(db, [k["kpi_id"] for k in kpis])
    out = []
    for k in kpis:
        hist = hist_map.get(k["kpi_id"], [])
        if len(hist) >= 3:
            out.append({"kpi_id": k["kpi_id"], "name": k["name"],
                        "unit": k.get("unit"), "points": hist})
        if len(out) >= MAX_SERIES:
            break
    return out


def build(db: Database, key: str, user: dict) -> dict:
    spec = DASHBOARDS[key]
    accessible = set(rbac.accessible_modules_for_user(user))
    modules = [m for m in spec["modules"] if m in accessible]
    kpis = engine.latest_snapshot(db, modules) if modules else []

    projects = []
    if spec["show_projects"]:
        for p in db.projects.find({"status": "active"}):
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

    payload = {"key": key, "title": spec["title"], "kpis": kpis,
               "projects": projects, "alerts": alerts,
               "series": _series(db, kpis)}

    if "product_dev" in modules:
        breakdown = _bug_breakdown(db)
        if breakdown:
            payload["bug_breakdown"] = breakdown
    return payload
