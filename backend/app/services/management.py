"""Management Overview — Project Bugs Tracker + Project Report.

Fully live-derived from the real `tasks`/`projects`/`project_invoices`
collections — no seeded data, no new collections (unlike Indicator Of
Success / Financial Forecaster). Reuses the terminal-status vocabulary and
bug query from `kpi/engine.py` so these numbers agree with the KPI cards,
`insights/util.py`'s project/assignee helpers, and `services/projects.py`'s
project detail builder for the report header/stages/tasks.
"""
from __future__ import annotations

import datetime as dt
import re
from collections import Counter

from fastapi import HTTPException, status
from pymongo.database import Database

from ..insights.util import project_names, task_project, who
from ..kpi.engine import CLOSED_BUG_STATUSES, _BUG_Q, _as_datetime
from . import projects as projects_service

_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
_PRESETS = {"week", "month", "3m"}
_PRIORITY_SEVERITY = {"Immediate": "Critical", "High": "High", "Normal": "Medium", "Low": "Low"}


class Window:
    __slots__ = ("date_from", "date_to")

    def __init__(self, date_from: dt.date, date_to: dt.date):
        self.date_from, self.date_to = date_from, date_to

    @property
    def days(self) -> int:
        return (self.date_to - self.date_from).days + 1

    def contains(self, d: dt.date | None) -> bool:
        return d is not None and self.date_from <= d <= self.date_to


def resolve_window(preset: str | None, date_from: str | None, date_to: str | None) -> Window:
    today = dt.date.today()
    if date_from or date_to:
        if not (date_from and date_to):
            raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY,
                                "both from and to are required for a custom range")
        if not (_DATE_RE.match(date_from) and _DATE_RE.match(date_to)):
            raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "from/to must be YYYY-MM-DD")
        d_from, d_to = dt.date.fromisoformat(date_from), dt.date.fromisoformat(date_to)
        if d_from > d_to:
            raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "from must be <= to")
        return Window(d_from, d_to)
    p = preset or "week"
    if p not in _PRESETS:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "preset must be week, month, or 3m")
    if p == "month":
        return Window(today.replace(day=1), today)
    if p == "3m":
        return Window(today - dt.timedelta(days=89), today)
    return Window(today - dt.timedelta(days=today.weekday()), today)  # week: Mon -> today


def _prev_window(w: Window) -> Window:
    length = w.days
    return Window(w.date_from - dt.timedelta(days=length), w.date_from - dt.timedelta(days=1))


def _delta(cur: float | None, prev: float | None) -> float | None:
    if cur is None or prev is None or prev == 0:
        return None
    return round((cur - prev) / abs(prev) * 100, 1)


def _card(card_id: str, label: str, value, unit: str, prev_value,
         higher_is_better: bool = True) -> dict:
    delta = _delta(value, prev_value)
    direction = good = None
    if delta is not None:
        direction = "up" if delta > 0 else ("down" if delta < 0 else "flat")
        good = True if delta == 0 else (delta > 0) == higher_is_better
    return {"id": card_id, "label": label, "value": value, "unit": unit,
           "delta_pct": delta, "delta_direction": direction, "good": good}


def _bug_scope(project: str | None) -> dict:
    q = dict(_BUG_Q)
    if project:
        q["$or"] = [{"project_id": project}, {"project_source_id": project}]
    return q


def _bug_id(t: dict) -> str | None:
    return t.get("task_id") or t.get("source_id")


def _module_of(title: str | None) -> str:
    m = re.match(r"^\[([^\]]+)\]", title or "")
    return m.group(1) if m else "Other"


def _severity_of(priority: str | None) -> str:
    return _PRIORITY_SEVERITY.get(priority or "", "Medium")


def known_project(db: Database, project: str) -> bool:
    return bool(db.projects.find_one({"$or": [{"project_id": project}, {"source_id": project}]}))


def list_bug_projects(db: Database) -> list[dict]:
    """Projects that actually have at least one bug — for the tracker's
    selector. Handles both seed (`project_id`) and OpenProject
    (`project_source_id`) keying, like `services/dashboards.py` does."""
    pnames = project_names(db)
    seen: dict[str, str] = {}
    for pid in db.tasks.distinct("project_id", _BUG_Q):
        if pid:
            seen[str(pid)] = pnames.get(str(pid), str(pid))
    for sid in db.tasks.distinct("project_source_id", _BUG_Q):
        if sid:
            seen[str(sid)] = pnames.get(str(sid), str(sid))
    return [{"project": k, "name": v} for k, v in seen.items()]


def build_bugs(db: Database, window: Window, project: str | None = None) -> dict:
    if project and not known_project(db, project):
        raise HTTPException(status.HTTP_404_NOT_FOUND, "unknown project")

    scope = _bug_scope(project)
    prev_window = _prev_window(window)
    all_bugs = list(db.tasks.find(scope))

    unresolved_now = sum(1 for b in all_bugs if b.get("status") not in CLOSED_BUG_STATUSES)

    created = resolved = prev_created = prev_resolved = 0
    durations: list[float] = []
    prev_durations: list[float] = []
    created_by_day: Counter = Counter()
    resolved_by_day: Counter = Counter()
    resolution_by_day: dict[str, list[float]] = {}

    for b in all_bugs:
        created_at = _as_datetime(b.get("created_at"))
        c_date = created_at.date() if created_at else None
        if window.contains(c_date):
            created += 1
            created_by_day[c_date.isoformat()] += 1
        elif prev_window.contains(c_date):
            prev_created += 1

        if b.get("status") in CLOSED_BUG_STATUSES:
            updated_at = _as_datetime(b.get("updated_at"))
            u_date = updated_at.date() if updated_at else None
            duration = None
            if created_at and updated_at and updated_at >= created_at:
                duration = (updated_at - created_at).total_seconds() / 86400
            if window.contains(u_date):
                resolved += 1
                resolved_by_day[u_date.isoformat()] += 1
                if duration is not None:
                    durations.append(duration)
                    resolution_by_day.setdefault(u_date.isoformat(), []).append(duration)
            elif prev_window.contains(u_date):
                prev_resolved += 1
                if duration is not None:
                    prev_durations.append(duration)

    avg_resolution = round(sum(durations) / len(durations), 1) if durations else None
    prev_avg_resolution = round(sum(prev_durations) / len(prev_durations), 1) if prev_durations else None
    resolution_rate = round(resolved / created * 100, 1) if created else None
    prev_resolution_rate = round(prev_resolved / prev_created * 100, 1) if prev_created else None

    cards = [
        # Point-in-time snapshot — no real prior-window count exists to
        # diff against (unlike created/resolved, which are window events),
        # so this card intentionally carries no delta rather than a
        # fabricated one.
        _card("unresolved", "Total Unresolved Bugs", unresolved_now, "count", None),
        _card("avg_resolution", "Average Resolution Time", avg_resolution, "days",
             prev_avg_resolution, higher_is_better=False),
        _card("created", "Issues Created", created, "count", prev_created, higher_is_better=False),
        _card("resolved", "Issues Resolved", resolved, "count", prev_resolved),
        _card("resolution_rate", "Resolution Rate", resolution_rate, "pct", prev_resolution_rate),
    ]

    by_status = Counter(b.get("status") or "Unknown" for b in all_bugs)
    by_severity = Counter(_severity_of(b.get("priority")) for b in all_bugs)
    by_module = Counter(_module_of(b.get("title")) for b in all_bugs)
    total_bugs = len(all_bugs)

    days = [window.date_from + dt.timedelta(days=i) for i in range(window.days)]
    creation_trend = [{"t": d.isoformat(), "created": created_by_day.get(d.isoformat(), 0),
                       "resolved": resolved_by_day.get(d.isoformat(), 0)} for d in days]
    resolution_time_trend = [
        {"t": d.isoformat(), "v": round(sum(vals) / len(vals), 1)}
        for d in days for vals in [resolution_by_day.get(d.isoformat())] if vals
    ]

    pnames = project_names(db)
    unresolved_sorted = sorted(
        (b for b in all_bugs if b.get("status") not in CLOSED_BUG_STATUSES),
        key=lambda b: _as_datetime(b.get("created_at")) or dt.datetime.min.replace(tzinfo=dt.timezone.utc),
        reverse=True,
    )
    recent_unresolved = []
    for b in unresolved_sorted[:10]:
        created_at = _as_datetime(b.get("created_at"))
        age = (dt.datetime.now(dt.timezone.utc) - created_at).days if created_at else None
        recent_unresolved.append({
            "bug_id": _bug_id(b), "project": task_project(b, pnames), "title": b.get("title"),
            "severity": _severity_of(b.get("priority")), "status": b.get("status"),
            "assignee": who(b),
            "reported_on": created_at.date().isoformat() if created_at else None,
            "age_days": age,
        })

    recent_activity = []
    for b in all_bugs:
        bug_id, proj_label = _bug_id(b), task_project(b, pnames)
        created_at = _as_datetime(b.get("created_at"))
        if created_at:
            recent_activity.append({"kind": "created", "bug_id": bug_id, "project": proj_label,
                                    "detail": f"Bug created: {b.get('title')}",
                                    "at": created_at.isoformat()})
        for h in b.get("status_history") or []:
            at = _as_datetime(h.get("at"))
            if at:
                recent_activity.append({
                    "kind": "status_change", "bug_id": bug_id, "project": proj_label,
                    "detail": f"Status changed from {h.get('from')} to {h.get('to')}",
                    "at": at.isoformat(),
                })
    recent_activity.sort(key=lambda r: r["at"], reverse=True)

    return {
        "window": {"from": window.date_from.isoformat(), "to": window.date_to.isoformat()},
        "projects": list_bug_projects(db),
        "cards": cards,
        "charts": {
            "creation_trend": {"points": creation_trend},
            "by_status": {"slices": [{"label": s, "value": n} for s, n in by_status.items()]},
            "by_severity": {"slices": [{"label": s, "value": n} for s, n in by_severity.items()]},
            "resolution_time_trend": {"points": resolution_time_trend},
        },
        "tables": {
            "by_status": [{"status": s, "count": n,
                          "pct": round(n / total_bugs * 100, 1) if total_bugs else 0}
                         for s, n in by_status.most_common()],
            "by_module": [{"module": m, "count": n,
                          "pct": round(n / total_bugs * 100, 1) if total_bugs else 0}
                         for m, n in by_module.most_common(5)],
            "recent_unresolved": recent_unresolved,
            "recent_activity": recent_activity[:10],
        },
        "last_updated": dt.datetime.now(dt.timezone.utc).isoformat(),
    }


def build_report(db: Database, project_id: str) -> dict:
    detail = projects_service.detail(db, project_id)
    if not detail:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "unknown project")

    tasks, bugs = detail.pop("tasks"), detail.pop("bugs")
    task_done = sum(1 for t in tasks if t.get("status") in CLOSED_BUG_STATUSES or t.get("progress") == 100)
    bug_open = sum(1 for b in bugs if b.get("status") not in CLOSED_BUG_STATUSES)
    bug_critical = sum(1 for b in bugs if b.get("status") not in CLOSED_BUG_STATUSES
                      and _severity_of(b.get("priority")) == "Critical")
    bug_closed = len(bugs) - bug_open

    expected = detail.get("expected_progress")
    progress = detail.get("progress", 0)
    rag = "grey"
    if expected:
        rag = "green" if progress >= expected else ("amber" if progress >= 0.7 * expected else "red")

    invoices = list(db.project_invoices.find({"project_id": project_id}, {"_id": 0}).sort("date", 1))
    paid = sum(i.get("amount", 0) for i in invoices if i.get("status") == "paid")
    pending = sum(i.get("amount", 0) for i in invoices if i.get("status") == "pending")
    overdue = sum(i.get("amount", 0) for i in invoices if i.get("status") == "overdue")

    return {
        "project": {
            "project_id": detail["project_id"], "code": detail["code"], "name": detail["name"],
            "client": detail.get("client"), "status": detail["status"],
            "engagement": detail.get("engagement"), "priority": detail.get("priority"),
            "start_date": detail.get("start_date"), "due_date": detail.get("due_date"),
            "project_manager": detail.get("project_manager"),
            "progress": progress, "expected_progress": expected, "rag": rag,
            "member_count": len(detail.get("members", [])),
        },
        "stages": detail.get("stages", []),
        "stats": {
            "tasks_total": len(tasks), "tasks_done": task_done,
            "task_completion_pct": round(task_done / len(tasks) * 100, 1) if tasks else None,
            "bugs_total": len(bugs), "bugs_open": bug_open, "bugs_critical": bug_critical,
            "bug_resolution_pct": round(bug_closed / len(bugs) * 100, 1) if bugs else None,
        },
        "invoices": {
            "paid": paid, "pending": pending, "overdue": overdue,
            "rows": invoices,
        },
        "last_updated": dt.datetime.now(dt.timezone.utc).isoformat(),
    }


def list_projects_for_selector(db: Database) -> list[dict]:
    return [{"project_id": p["project_id"], "name": p["name"]}
           for p in db.projects.find({}, {"project_id": 1, "name": 1}) if p.get("project_id")]
