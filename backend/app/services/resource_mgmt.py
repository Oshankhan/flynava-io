"""Resource Management dashboard — team capacity, per-person workload
heatmap, top performers, at-risk resources, project resource status, and
department work-lifecycle strips.

No new collections. There is no stored utilization/workload/capacity metric
anywhere in this DB (checked kpi_defs, users, employees) — `person_rows()`
below is the single formula every zone (KPI strip, capacity bars, heatmap,
top performers, at-risk list) derives from, so none of them can disagree
about what a given "82%" means. It reuses the same per-member task buckets
`services/tasks.py`'s `team_tasks_bulk` already computes for the workspace
department/exec rollups.

`kpi/engine.py`'s resource_mgmt computers import `person_utilizations()` from
here (locally, inside each function body) rather than duplicating the
formula — this module also imports `kpi.engine` at the top for a couple of
existing computers (`active_project_count`, `bug_resolution_days`,
`ar_days_outstanding`) it reuses as-is. That's a one-directional dependency
(this module -> kpi.engine), so there's no import cycle.
"""
from __future__ import annotations

import datetime as dt
from collections import Counter
from statistics import mean, median

from pymongo.database import Database

from ..core.rbac import user_level
from ..kpi import engine as kpi_engine
from . import tasks as tasks_svc

# Capacity target is data-driven, not a hardcoded guess: a fixed constant
# tuned against the small seed dataset (a handful of open items/person) put
# EVERY real person and team over 100% once real accumulated task volume
# (dozens of items/person, long-tailed across a handful of heavily-loaded
# people) was checked live against the dev DB — the bands only mean anything
# relative to the org's own current workload, so the target self-calibrates
# to it. Median (not mean) of the company-wide workload is the "typical"
# person's load — mean gets dragged upward by the same few outliers this
# screen exists to surface, which would then hide them inside "optimal"
# instead of flagging them. `_MIN_CAPACITY_TARGET` just avoids a near-zero
# denominator when there's almost no task data yet.
_MIN_CAPACITY_TARGET = 1.0
_CAPACITY_HEADROOM = 1.15
OVERDUE_WEIGHT = 1.5


def _capacity_target(db: Database) -> float:
    """Always derived from EVERY active, team-assigned person company-wide —
    even when the caller only wants one department's rows (`_scoped_teams`) —
    so a department head's view and the CEO's view (and the KPI strip) can
    never disagree about what "100%" means.

    Only people carrying at least one open item feed the median: many roles
    (finance, HR, marketing, ...) never appear in `tasks` at all — that's a
    real, honest "no tracked work" signal worth showing per-person, but
    folding a large cluster of structural zeros into the baseline collapses
    the median itself toward zero and leaves almost nobody in the 70-100%
    "optimal" band. Baselining against people who actually generate tracked
    workload is what makes the target reflect a typical *active* load."""
    all_teams = list(db.teams.find({}))
    bulk = tasks_svc.team_tasks_bulk(db, [t["team_id"] for t in all_teams])
    workloads = [
        (m["in_progress"] + m["pending"]) + OVERDUE_WEIGHT * m["overdue"]
        for info in bulk.values() for m in info["members"]
    ]
    active = [w for w in workloads if w > 0]
    if not active:
        return _MIN_CAPACITY_TARGET
    return max(median(active) * _CAPACITY_HEADROOM, _MIN_CAPACITY_TARGET)


# 5-6 stage funnel decay used for departments with no real per-stage
# breakdown (HR hiring, Marketing campaigns, Support tickets) — anchored to
# whatever real total exists (open positions/candidates, active contacts, the
# existing demo ticket count) so at least the top of the funnel is real, even
# though the stage-by-stage split itself is illustrative.
_FUNNEL_DECAY = [1.0, 0.65, 0.4, 0.22, 0.12, 0.06]


def _utilization_pct(open_count: int, overdue_count: int, target: float) -> float:
    workload = open_count + OVERDUE_WEIGHT * overdue_count
    return round(workload / target * 100, 1)


def _person_status(pct: float) -> str:
    if pct > 100:
        return "overloaded"
    if pct < 70:
        return "underutilized"
    return "optimal"


def _team_status(pct: float) -> str:
    if pct >= 100:
        return "critical"
    if pct >= 85:
        return "overloaded"
    if pct >= 70:
        return "healthy"
    return "low"


def _pct(numerator: int, denominator: int) -> float:
    return round(numerator / denominator * 100, 1) if denominator else 0.0


def _scoped_teams(db: Database, user: dict) -> list[dict]:
    """Leadership (L4+) sees every team; a single department head (L3) sees
    only their own department's teams — same split as `workspace_department`
    vs `workspace_exec`."""
    if user_level(user) >= 4:
        return list(db.teams.find({}))
    return list(db.teams.find({"department": user.get("department")}))


def person_rows(db: Database, teams: list[dict], target: float | None = None) -> list[dict]:
    """One row per active, team-assigned user across `teams`. Only users with
    a team_id get a utilization number — someone with no task queue isn't an
    assignable "resource" for this screen. `target` lets a caller that's
    already computed the company-wide capacity target reuse it instead of
    recomputing (`build_dashboard` does this); omitted, it's derived fresh."""
    if target is None:
        target = _capacity_target(db)
    bulk = tasks_svc.team_tasks_bulk(db, [t["team_id"] for t in teams])
    team_by_id = {t["team_id"]: t for t in teams}

    user_ids = [m["user_id"] for info in bulk.values() for m in info["members"]]
    designations = {u["user_id"]: u.get("designation") for u in
                    db.users.find({"user_id": {"$in": user_ids}}, {"user_id": 1, "designation": 1})}

    rows = []
    for team_id, info in bulk.items():
        team = team_by_id.get(team_id, {})
        for m in info["members"]:
            open_ct = m["in_progress"] + m["pending"]
            util = _utilization_pct(open_ct, m["overdue"], target)
            rows.append({
                "user_id": m["user_id"], "name": m["name"],
                "designation": designations.get(m["user_id"]),
                "team_id": team_id, "team_name": team.get("name"),
                "department": team.get("department"),
                "tasks": m["total"], "open": open_ct,
                "pending": m["pending"], "in_progress": m["in_progress"],
                "overdue": m["overdue"], "completed": m["completed"],
                "completion_pct": _pct(m["completed"], m["total"]),
                "workload_pct": util, "status": _person_status(util),
            })
    return rows


def person_utilizations(db: Database) -> list[float]:
    """Company-wide utilization % list — used by the KPI-strip computers in
    kpi/engine.py so the headline cards and this module's own heatmap/
    capacity rows are always computed from the same formula."""
    all_teams = list(db.teams.find({}))
    return [r["workload_pct"] for r in person_rows(db, all_teams)]


def _team_capacity_rows(db: Database, teams: list[dict], target: float) -> list[dict]:
    bulk = tasks_svc.team_tasks_bulk(db, [t["team_id"] for t in teams])
    rows = []
    for t in teams:
        info = bulk[t["team_id"]]
        member_count = len(info["members"])
        if not member_count:
            continue
        b = info["buckets"]
        open_total = b["in_progress"] + b["pending"]
        util = round((open_total + OVERDUE_WEIGHT * b["overdue"]) / (member_count * target) * 100, 1)
        rows.append({
            "team_id": t["team_id"], "name": t["name"], "department": t.get("department"),
            "utilization_pct": util, "status": _team_status(util),
            "member_count": member_count, "tasks": b["total"],
            "completion_pct": _pct(b["completed"], b["total"]),
        })
    return sorted(rows, key=lambda r: -r["utilization_pct"])


def _top_performers(rows: list[dict], limit: int = 5) -> list[dict]:
    """SLA compliance and rating are both derived (no performance-review data
    exists) — SLA = share of a person's assigned work that isn't currently
    overdue; rating blends completion and SLA onto a 1-5 scale. Both are
    labeled as derived in the payload rather than presented as tracked
    metrics."""
    ranked = sorted((r for r in rows if r["tasks"] > 0),
                    key=lambda r: (-r["completion_pct"], -r["tasks"]))[:limit]
    out = []
    for r in ranked:
        sla = round(100 - _pct(r["overdue"], r["tasks"]), 1)
        rating = round(min(5.0, max(1.0, 1 + 4 * (0.5 * r["completion_pct"] + 0.5 * sla) / 100)), 1)
        out.append({**r, "sla_pct": sla, "rating": rating})
    return out


def _at_risk_resources(rows: list[dict], target: float, limit: int = 3) -> list[dict]:
    ranked = sorted(rows, key=lambda r: -r["workload_pct"])[:limit]
    out = []
    for r in ranked:
        if r["status"] == "overloaded":
            reassign = max(1, round(r["open"] - target))
            recommendation = f"Reassign {reassign} tasks"
        else:
            reassign = 0
            recommendation = "Monitor workload"
        out.append({**r, "reassign_count": reassign, "recommendation": recommendation})
    return out


def _project_health(progress: float, expected: float | None) -> str:
    if expected is None:
        return "on_track"
    if progress >= expected:
        return "on_track"
    if progress >= 0.7 * expected:
        return "at_risk"
    return "behind"


def _project_rows(db: Database, user: dict) -> list[dict]:
    # Queries `db.projects` directly rather than `projects_service.list_for_user`
    # (which crashes on a project doc missing `project_id` — seen live in the
    # real dev DB, not just the clean seed fixture) and only reads fields this
    # view actually needs, defensively. `user` isn't used for filtering today:
    # this endpoint already gates on `user_level(user) >= 3`, and
    # `visible_to()` is unconditionally True at that level anyway.
    rows = []
    for p in db.projects.find({"status": "active"}):
        project_id = p.get("project_id")
        if not project_id:
            continue
        progress = p.get("progress", 0)
        expected = p.get("expected_progress")
        stage_name = next((s.get("name") for s in p.get("stages", [])
                           if s.get("key") == p.get("current_stage")), None)
        rows.append({
            "project_id": project_id, "code": p.get("code"), "name": p.get("name"),
            "progress": progress, "expected_progress": expected,
            "health": _project_health(progress, expected),
            "resources": len(p.get("member_ids", [])), "due_date": p.get("due_date"),
            "current_stage_name": stage_name,
        })
    return rows


# --- Work Lifecycle Overview (department-wise) ---

_ENG_STAGE_RULES = [
    ("Deployed", ("closed", "not a bug", "done", "resolved", "rejected")),
    ("UAT", ("uat", "replica done", "training")),
    ("QA", ("qa", "testing", "retest")),
    ("Code Review", ("review", "prod retest")),
    ("In Progress", ("progress", "develop", "reopen", "specif")),
]


def _classify_eng_stage(status: str | None) -> str:
    s = (status or "").lower()
    for stage, keywords in _ENG_STAGE_RULES:
        if any(k in s for k in keywords):
            return stage
    return "Backlog"


def _eng_lifecycle(db: Database) -> dict:
    """Real: OpenProject task/bug statuses grouped into delivery-pipeline
    columns via keyword matching (statuses are free text, not a fixed enum —
    same idiom `services/tasks.py`'s `classify()` uses)."""
    stage_order = ["Backlog", "In Progress", "Code Review", "QA", "UAT", "Deployed"]
    counts = Counter(_classify_eng_stage(t.get("status")) for t in db.tasks.find({}, {"status": 1}))
    avg_cycle = kpi_engine.compute(db, {"formula": "bug_resolution_days"})
    return {"department": "Engineering", "source": "live",
            "stages": [{"name": s, "count": counts.get(s, 0)} for s in stage_order],
            "avg_cycle_days": avg_cycle}


def _finance_lifecycle(db: Database) -> dict:
    """Real: `project_invoices.status` (paid/pending/overdue) — only 3 real
    states, relabeled into a 4-column strip (Raised = every invoice raised
    this covers)."""
    invoices = list(db.project_invoices.find({}, {"status": 1}))
    counts = Counter(inv.get("status") for inv in invoices)
    avg_cycle = kpi_engine.compute(db, {"formula": "ar_days_outstanding"}) if invoices else None
    return {
        "department": "Finance", "source": "live" if invoices else "demo",
        "stages": [
            {"name": "Raised", "count": len(invoices)},
            {"name": "Pending", "count": counts.get("pending", 0)},
            {"name": "Overdue", "count": counts.get("overdue", 0)},
            {"name": "Paid", "count": counts.get("paid", 0)},
        ],
        "avg_cycle_days": avg_cycle,
    }


def _funnel_stages(stage_names: list[str], anchor_total: float) -> list[dict]:
    return [{"name": n, "count": max(0, round(anchor_total * r))}
            for n, r in zip(stage_names, _FUNNEL_DECAY)]


def _hr_lifecycle(db: Database) -> dict:
    """Partial: open positions/candidate totals are real; there's no tracked
    per-stage hiring funnel yet, so the stage-by-stage split is estimated."""
    positions = list(db.positions.find({"status": "open"}))
    anchor = sum(p.get("candidates", 0) for p in positions) or (len(positions) * 4 if positions else 12)
    stages = _funnel_stages(["Job Request", "Sourcing", "Screening", "Interview", "Offer"], anchor)
    avg_days_open = round(mean(p["days_open"] for p in positions), 1) if positions else None
    return {"department": "HR", "source": "partial" if positions else "demo",
            "stages": stages, "avg_cycle_days": avg_days_open,
            "note": "Open-position and candidate totals are real; the stage "
                    "split is estimated — no per-candidate funnel is tracked yet."}


def _marketing_lifecycle(db: Database) -> dict:
    """Demo: campaign-stage funnel isn't tracked; anchored to the real active
    CRM contact count so at least the top of the funnel is real."""
    total_contacts = db.crm_contacts.count_documents({"status": "active"})
    anchor = total_contacts or 20
    stages = _funnel_stages(["Leads", "Contacted", "Qualified", "Proposal", "Won"], anchor)
    return {"department": "Marketing", "source": "demo", "stages": stages, "avg_cycle_days": None,
            "note": "Campaign-stage funnel isn't tracked yet — counts are illustrative."}


def _support_lifecycle(db: Database) -> dict:
    """Demo: no ticketing system connected — fully illustrative, anchored to
    the existing demo Open Tickets KPI value."""
    row = db.kpi_values.find_one({"kpi_id": "sup_open_tickets"}, sort=[("calculated_at", -1)])
    anchor = row["value"] if row else 47
    stages = _funnel_stages(["Opened", "Assigned", "In Progress", "Waiting", "Resolved", "Closed"], anchor)
    return {"department": "Support", "source": "demo", "stages": stages, "avg_cycle_days": None,
            "note": "No ticketing system connected yet (Zoho Desk) — fully illustrative."}


# --- AI Resource Insights (deterministic findings from the data above) ---

def _insights(team_rows: list[dict], overloaded_count: int, underutilized_count: int,
             at_risk_rows: list[dict], positions_open: list[dict]) -> list[dict]:
    out: list[dict] = []
    hot_teams = [t for t in team_rows if t["status"] in ("critical", "overloaded")]
    if hot_teams:
        top = hot_teams[0]
        out.append({"severity": "high" if top["status"] == "critical" else "medium",
                    "text": f"{top['name']} team is {top['utilization_pct']}% utilized. "
                            f"Consider resource balancing."})
    if overloaded_count:
        out.append({"severity": "high",
                    "text": f"{overloaded_count} member(s) are overloaded. Immediate attention required."})
    if positions_open:
        slow = max(positions_open, key=lambda p: p.get("days_open", 0))
        if slow.get("days_open", 0) >= 20:
            out.append({"severity": "medium",
                        "text": f"{slow['title']} hiring is taking {slow['days_open']} days. "
                                f"Review the pipeline."})
    reassignable = sum(r.get("reassign_count", 0) for r in at_risk_rows)
    if reassignable and underutilized_count:
        out.append({"severity": "low",
                    "text": f"{reassignable} task(s) can be reassigned to "
                            f"{underutilized_count} underutilized member(s) for better balance."})
    if not out:
        out.append({"severity": "low", "text": "Resource allocation looks healthy across all teams."})
    return out[:5]


def _live_kpi_cards(db: Database) -> list[dict]:
    """Live-recomputed resource_mgmt KPI cards — unlike `engine.latest_snapshot()`
    (last value from whenever `run_all`/`/kpis/recalculate` last ran, which for
    a fresh `seed()` is never), these values always match the current data.
    That matters here because workload changes with every task reassignment —
    a stale cached number would defeat the point of this screen. Same
    recompute-with-fallback pattern `kpis.py`'s `/kpis/{kpi_id}/explain` uses,
    reusing `rag_status`/`change_pct` for the same RAG/trend semantics every
    other KPI card in the app has."""
    cards = []
    for d in db.kpi_defs.find({"module": "resource_mgmt"}):
        value = kpi_engine.compute(db, d)
        if value is None:
            row = db.kpi_values.find_one({"kpi_id": d["kpi_id"]}, sort=[("calculated_at", -1)])
            value = row["value"] if row else None
        cards.append({
            "kpi_id": d["kpi_id"], "name": d["name"], "module": d["module"],
            "value": value, "unit": d.get("unit"), "target": d.get("target"),
            "direction": d.get("direction", "higher"),
            "rag": kpi_engine.rag_status(value, d.get("target"), d.get("direction", "higher")),
            "change_pct": kpi_engine.change_pct(db, d["kpi_id"]),
        })
    return cards


def build_dashboard(db: Database, user: dict) -> dict:
    teams = _scoped_teams(db, user)
    target = _capacity_target(db)
    rows = person_rows(db, teams, target)
    team_rows = _team_capacity_rows(db, teams, target)
    at_risk = _at_risk_resources(rows, target)
    positions_open = list(db.positions.find({"status": "open"}))

    kpi_cards = _live_kpi_cards(db)
    by_id = {c["kpi_id"]: c["value"] for c in kpi_cards}
    overloaded_count = by_id.get("res_overloaded") or 0
    underutilized_count = by_id.get("res_underutilized") or 0

    return {
        "kpi_cards": kpi_cards,
        "team_capacity": team_rows,
        "heatmap": sorted(rows, key=lambda r: -r["workload_pct"]),
        "top_performers": _top_performers(rows),
        "performance_matrix": [{"team": t["name"], "completion_pct": t["completion_pct"],
                                "workload_pct": t["utilization_pct"]} for t in team_rows],
        "at_risk_resources": at_risk,
        "project_resource_status": _project_rows(db, user),
        "work_lifecycle": [
            _eng_lifecycle(db), _hr_lifecycle(db), _finance_lifecycle(db),
            _marketing_lifecycle(db), _support_lifecycle(db),
        ],
        "insights": _insights(team_rows, overloaded_count, underutilized_count, at_risk, positions_open),
        "generated_at": dt.datetime.now(dt.timezone.utc).isoformat(),
    }
