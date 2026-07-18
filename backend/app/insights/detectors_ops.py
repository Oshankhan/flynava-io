"""Operations / Product Development problem-statement detectors.

Data source: OpenProject (`tasks`/`projects`) — see PRD section 8, module
`operations`/`product_dev`. Reuses the exact bug/status query vocabulary from
`kpi/engine.py` so a detector's numbers always agree with the KPI cards.
"""
from __future__ import annotations

import datetime as dt
from collections import Counter, defaultdict
from statistics import mean, pstdev

from pymongo.database import Database

from ..integrations.openproject import work_package_url
from ..kpi.engine import CLOSED_BUG_STATUSES, _BUG_Q
from ..services.tasks import classify
from .engine import detector
from .impact import classify_impact
from .util import project_names, task_project, who

_PRIORITY_CRITICAL = {"immediate", "high"}

_BUG_FIELDS = {"title": 1, "status": 1, "priority": 1, "assignee": 1, "assignee_id": 1,
               "project_id": 1, "project_source_id": 1, "reopen_count": 1,
               "task_id": 1, "source_id": 1, "created_at": 1}


def _due_date(t: dict) -> dt.date | None:
    due = t.get("due_date")
    if not due:
        return None
    try:
        return dt.date.fromisoformat(str(due)[:10])
    except ValueError:
        return None


def _work_ref(t: dict) -> tuple[str | None, str | None]:
    """(display_id, url) for a task/bug — real OpenProject-synced items get a
    deep link (their `source_id`); seed/demo items just show their internal
    `task_id` with no link, since there's nowhere real for it to point."""
    sid = t.get("source_id")
    if sid:
        return sid, work_package_url(sid)
    return t.get("task_id"), None


def _id_prefix(display_id: str | None) -> str:
    return f"#{display_id} " if display_id else ""


def _task_scope(project: str | None) -> dict:
    """Mongo filter fragment for the `tasks` collection's project FK."""
    return {"project_source_id": project} if project else {}


def _project_scope(project: str | None) -> dict:
    """Mongo filter fragment for the `projects` collection's own id."""
    return {"source_id": project} if project else {}


@detector("ops_reopened_bugs", "operations", "Bugs that keep reopening")
def _reopened_bugs(db: Database, project: str | None = None) -> dict | None:
    q = {**_BUG_Q, "$or": [{"status": {"$regex": "reopen", "$options": "i"}},
                           {"reopen_count": {"$gte": 1}}], **_task_scope(project)}
    bugs = list(db.tasks.find(q, _BUG_FIELDS))
    if not bugs:
        return None

    pnames = project_names(db)
    by_assignee: Counter = Counter()
    by_project: Counter = Counter()
    for b in bugs:
        by_assignee[who(b)] += 1
        by_project[task_project(b, pnames) or "Unknown project"] += 1

    repeat_assignees = [(name, n) for name, n in by_assignee.most_common() if n >= 2]
    high_priority = [b for b in bugs if (b.get("priority") or "") in ("Immediate", "High")]
    top_assignee = by_assignee.most_common(1)[0] if by_assignee else None
    top_project = by_project.most_common(1)[0] if by_project else None

    problem = f"{len(bugs)} bug(s) are currently in a Reopen state"
    if top_project:
        problem += f" — {top_project[1]} in {top_project[0]}"
    if top_assignee:
        problem += f"; {top_assignee[0]} has reopened the most ({top_assignee[1]})."
    else:
        problem += "."

    evidence = [f"{_id_prefix(_work_ref(b)[0])}{b.get('title')} — {b.get('status')}, "
                f"priority {b.get('priority') or 'Normal'}, "
                f"assignee {who(b)}, project {task_project(b, pnames) or 'Unknown'}"
                for b in bugs[:8]]

    return {
        "severity": "high" if (high_priority or repeat_assignees) else "medium",
        "problem": problem,
        "metrics": [{"label": "Reopened bugs", "value": len(bugs), "unit": ""},
                    {"label": "Repeat offenders (assignee, 2+ reopens)",
                     "value": len(repeat_assignees), "unit": ""}],
        "entities": [{"kind": "bug", "id": _work_ref(b)[0], "label": b.get("title"),
                      "url": _work_ref(b)[1],
                      "extra": {"assignee": who(b), "project": task_project(b, pnames)}}
                     for b in bugs[:8]],
        "evidence": evidence,
        "chart": {"kind": "bars",
                  "points": [{"label": n, "value": c} for n, c in by_assignee.most_common(5)]},
        "action_hint": (f"Start a root-cause review with {top_assignee[0]} — "
                        f"{top_assignee[1]} of their bugs keep reopening."
                        if top_assignee else "Review the reopened bugs for a common root cause."),
    }


@detector("ops_overburdened", "operations", "Overburdened team members")
def _overburdened(db: Database, project: str | None = None) -> dict | None:
    today = dt.date.today()
    rows = list(db.tasks.find(
        _task_scope(project),
        {"assignee": 1, "assignee_id": 1, "status": 1, "due_date": 1, "progress": 1}))

    per_person: dict[str, dict[str, int]] = defaultdict(lambda: {"open": 0, "overdue": 0, "due_soon": 0})
    for t in rows:
        if classify(t.get("status")) == "completed" or t.get("progress") == 100:
            continue
        name = who(t)
        if name == "Unassigned":
            continue
        stats = per_person[name]
        stats["open"] += 1
        due = _due_date(t)
        if due and due < today:
            stats["overdue"] += 1
        elif due and due <= today + dt.timedelta(days=3):
            stats["due_soon"] += 1

    if len(per_person) < 2:
        return None
    counts = [s["open"] for s in per_person.values()]
    threshold = mean(counts) + 1.5 * pstdev(counts)
    outliers = sorted(
        ((name, s) for name, s in per_person.items() if s["open"] >= 5 and s["open"] > threshold),
        key=lambda kv: -kv[1]["open"])
    if not outliers:
        return None

    top_name, top_stats = outliers[0]
    problem = (f"{top_name} is carrying {top_stats['open']} open task(s) — well above the "
               f"team average of {round(mean(counts), 1)}.")
    if len(outliers) > 1:
        problem += f" {len(outliers)} team member(s) are overloaded in total."

    return {
        "severity": "high" if top_stats["overdue"] > 0 else "medium",
        "problem": problem,
        "metrics": [{"label": "Overloaded people", "value": len(outliers), "unit": ""},
                    {"label": f"{top_name}'s open tasks", "value": top_stats["open"], "unit": ""},
                    {"label": f"{top_name}'s overdue tasks", "value": top_stats["overdue"], "unit": ""}],
        "entities": [{"kind": "person", "id": name, "label": name, "extra": s}
                     for name, s in outliers[:8]],
        "evidence": [f"{name} — {s['open']} open, {s['overdue']} overdue, {s['due_soon']} due in 3 days"
                    for name, s in outliers[:8]],
        "chart": {"kind": "bars", "points": [{"label": n, "value": s["open"]} for n, s in outliers[:5]]},
        "action_hint": f"Rebalance {top_name}'s workload across the team, starting with the "
                       f"{top_stats['overdue']} overdue item(s)." if top_stats["overdue"] else
                       f"Rebalance {top_name}'s workload across the team.",
    }


@detector("ops_projects_at_risk", "operations", "Projects at risk of delay")
def _projects_at_risk(db: Database, project: str | None = None) -> dict | None:
    today = dt.date.today()
    flagged = []
    for p in db.projects.find({"status": "active", **_project_scope(project)}):
        expected = p.get("expected_progress")
        progress = p.get("progress", 0)
        if not expected or progress >= 0.7 * expected:
            continue
        predicted = None
        start, due = p.get("start_date"), p.get("due_date")
        if start and progress > 0:
            try:
                s = dt.date.fromisoformat(str(start)[:10])
                elapsed = (today - s).days
                if elapsed > 0:
                    rate = progress / elapsed
                    if rate > 0:
                        predicted = (today + dt.timedelta(days=round((100 - progress) / rate))).isoformat()
            except ValueError:
                pass
        flagged.append({**p, "_predicted": predicted})

    if not flagged:
        return None
    severe = [p for p in flagged if p.get("progress", 0) < 0.5 * p["expected_progress"]]
    evidence = []
    for p in flagged[:8]:
        line = (f"{p.get('name')} — {p.get('progress', 0)}% complete vs "
                f"{p['expected_progress']}% expected")
        line += f", predicted completion {p['_predicted']}" if p["_predicted"] else \
            " (no predicted date — insufficient timeline data)"
        evidence.append(line)

    return {
        "severity": "high" if severe else "medium",
        "problem": f"{len(flagged)} active project(s) are behind their expected timeline "
                  f"(progress below 70% of expected).",
        "metrics": [{"label": "At-risk projects", "value": len(flagged), "unit": ""},
                    {"label": "Severely behind (<50% of expected)", "value": len(severe), "unit": ""}],
        "entities": [{"kind": "project", "id": p.get("project_id") or p.get("source_id"),
                      "label": p.get("name"),
                      "extra": {"progress": p.get("progress", 0),
                                "expected_progress": p.get("expected_progress"),
                                "predicted_completion": p["_predicted"]}}
                     for p in flagged[:8]],
        "evidence": evidence,
        "chart": None,
        "action_hint": f"Review {flagged[0].get('name')} first — it has the least buffer "
                       f"against its expected timeline.",
    }


@detector("ops_stale_tasks", "operations", "Tasks aging past due")
def _stale_tasks(db: Database, project: str | None = None) -> dict | None:
    today = dt.date.today()
    rows = list(db.tasks.find(
        {"due_date": {"$ne": None}, "progress": {"$lt": 100}, **_task_scope(project)},
        {"title": 1, "due_date": 1, "assignee": 1, "assignee_id": 1, "status": 1,
         "project_id": 1, "project_source_id": 1, "task_id": 1, "source_id": 1}))

    buckets: dict[str, list[tuple[dict, int]]] = {"1-3": [], "4-7": [], "8-14": [], "15+": []}
    for t in rows:
        due = _due_date(t)
        if not due or due >= today:
            continue
        days_over = (today - due).days
        key = "1-3" if days_over <= 3 else "4-7" if days_over <= 7 else "8-14" if days_over <= 14 else "15+"
        buckets[key].append((t, days_over))

    total = sum(len(v) for v in buckets.values())
    if total == 0:
        return None
    severity = "high" if buckets["15+"] else "medium" if buckets["8-14"] else "low"
    pnames = project_names(db)
    worst = sorted((tv for bucket in buckets.values() for tv in bucket), key=lambda tv: -tv[1])[:8]

    problem = f"{total} task(s) are overdue"
    if buckets["15+"]:
        problem += f", {len(buckets['15+'])} of them by more than 15 days"
    problem += "."

    return {
        "severity": severity,
        "problem": problem,
        "metrics": [{"label": f"{k} days overdue", "value": len(v), "unit": ""}
                   for k, v in buckets.items()],
        "entities": [{"kind": "task", "id": _work_ref(t)[0], "label": t.get("title"),
                      "url": _work_ref(t)[1],
                      "extra": {"days_overdue": days, "assignee": who(t),
                                "project": task_project(t, pnames)}}
                     for t, days in worst],
        "evidence": [f"{_id_prefix(_work_ref(t)[0])}{t.get('title')} — {days}d overdue, "
                    f"assignee {who(t)}, project {task_project(t, pnames) or 'Unknown'}"
                    for t, days in worst],
        "chart": {"kind": "bars", "points": [{"label": k, "value": len(v)} for k, v in buckets.items()]},
        "action_hint": "Escalate the tasks overdue by more than 15 days to their managers first."
                      if buckets["15+"] else "Clear the oldest overdue tasks first.",
    }


@detector("ops_critical_bug_aging", "operations", "Critical bugs aging in the backlog")
def _critical_bug_aging(db: Database, project: str | None = None) -> dict | None:
    """"Critical" = priority Immediate/High OR the title matches a
    critical-area keyword (`insights/impact.py`) — priority alone is a human
    judgment call (a demo tomorrow makes a logo color "High"), not a reliable
    signal of real impact. A low/normal-priority bug whose title says
    "payment"/"checkout"/"login"/etc. shows up here too, flagged as
    under-labeled, instead of silently aging outside anyone's critical view."""
    q = {**_BUG_Q, "status": {"$nin": CLOSED_BUG_STATUSES}, **_task_scope(project)}
    open_bugs = list(db.tasks.find(q, _BUG_FIELDS))
    if not open_bugs:
        return None

    for b in open_bugs:
        b["_impact"] = classify_impact(b.get("title"))
        b["_priority_critical"] = (b.get("priority") or "").lower() in _PRIORITY_CRITICAL

    bugs = [b for b in open_bugs if b["_priority_critical"] or b["_impact"] == "high"]
    if not bugs:
        return None
    under_labeled = [b for b in bugs if b["_impact"] == "high" and not b["_priority_critical"]]

    now = dt.datetime.now(dt.timezone.utc)
    aged: list[tuple[dict, int]] = []
    unknown_age = 0
    for b in bugs:
        created = b.get("created_at")
        if not created:
            unknown_age += 1
            continue
        try:
            created_dt = (dt.datetime.fromisoformat(str(created).replace("Z", "+00:00"))
                         if isinstance(created, str) else created)
            if created_dt.tzinfo is None:
                created_dt = created_dt.replace(tzinfo=dt.timezone.utc)
            aged.append((b, (now - created_dt).days))
        except ValueError:
            unknown_age += 1

    if not aged and not unknown_age:
        return None
    aged.sort(key=lambda bd: -bd[1])
    over_14 = [bd for bd in aged if bd[1] >= 14]

    problem = f"{len(bugs)} critical bug(s) are open (by priority or by touching a critical area)"
    if under_labeled:
        names = "; ".join(f'"{b.get("title")}"' for b in under_labeled[:3])
        problem += (f". {len(under_labeled)} of them are marked "
                   f"{'/'.join(sorted({b.get('priority') or 'Normal' for b in under_labeled}))} "
                   f"priority but look critical by title — likely under-labeled: {names}")
    if aged:
        problem += f"; the oldest has been open {aged[0][1]} day(s)"
    if unknown_age:
        problem += f" ({unknown_age} have no recorded creation date)"
    problem += "."

    evidence = [f"{_id_prefix(_work_ref(b)[0])}{b.get('title')} — open {days}d, "
               f"priority {b.get('priority')}{' (UNDER-LABELED — critical by title)' if b['_impact'] == 'high' and not b['_priority_critical'] else ''}"
               f", assignee {who(b)}"
               for b, days in aged[:8]]
    if not evidence and unknown_age:
        evidence = [f"{unknown_age} critical bug(s) have no creation date on record."]

    return {
        "severity": "high" if (over_14 or under_labeled) else "medium",
        "problem": problem,
        "metrics": [{"label": "Open critical bugs", "value": len(bugs), "unit": ""},
                    {"label": "Aged 14+ days", "value": len(over_14), "unit": ""},
                    {"label": "Under-labeled (low priority, high real impact)",
                     "value": len(under_labeled), "unit": ""}],
        "entities": [{"kind": "bug", "id": _work_ref(b)[0], "label": b.get("title"),
                      "url": _work_ref(b)[1],
                      "extra": {"age_days": days, "priority": b.get("priority"),
                                "under_labeled": b["_impact"] == "high" and not b["_priority_critical"]}}
                     for b, days in aged[:8]],
        "evidence": evidence,
        "chart": None,
        "action_hint": (f'Re-prioritize "{under_labeled[0].get("title")}" — labeled '
                        f'{under_labeled[0].get("priority") or "Normal"} but touches a critical area.'
                        if under_labeled else
                        f"Prioritize \"{aged[0][0].get('title')}\" — open {aged[0][1]} days."
                        if aged else "Confirm creation dates for critical bugs so aging can be tracked."),
    }
