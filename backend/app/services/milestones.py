"""Milestone Tracker — company/department/employee milestone health.

Collections are prefixed `tracker_*`/`milestone_*` on purpose: the existing
`milestones` collection belongs to Indicator Of Success (a 4-row company
roadmap strip on the central dashboard, see `services/success.py`) and has a
completely different shape. Nothing here touches it.

Single source of truth for progress
-----------------------------------
`ProgressIndex.actual()` below is the ONLY place a milestone's completion
percentage is derived, and every zone of every screen (KPI cards, status
donut, trend chart, department bars, employee tables, reports) reads through
it — so no two numbers on the same page can disagree about what a given
"76%" means. Same discipline as `services/resource_mgmt.py`'s `person_rows`.

The formula, matching the tracker's stated logic:

    task_completion = 100                      if the task is done
                      clamp(sum of *approved* daily-entry deltas, 0, 100)
    actual_pct      = clamp(sum(weightage * task_completion) / sum(weightage)
                            + approved entries logged against no task)
    planned_pct     = clamp(elapsed / (due - start), 0, 100)   -- time elapsed
    delayed_pct     = max(0, planned_pct - actual_pct)
    health          = good            if actual >= planned
                      needs_attention if planned - actual <= 15
                      at_risk         otherwise

Only *approved* daily entries count — a pending submission moves nothing.

`actual_pct` is cached on the milestone as `progress_pct` and rewritten by
`recompute()` (the only writer) whenever a task or an entry changes, so the
list screen is a plain `find`. `planned_pct`/`delayed_pct`/`health`/`overdue`
are pure functions of the dates and are computed on read instead, because
they drift every day on their own.
"""
from __future__ import annotations

import csv
import datetime as dt
import io
import uuid
from collections import defaultdict

from pymongo.database import Database

from ..core.rbac import user_level
from . import notifications as notif_svc

STATUSES = ["not_started", "pending", "in_progress", "pending_review",
            "completed", "blocked"]
PRIORITIES = ["High", "Medium", "Low"]
HEALTH_ORDER = ["good", "needs_attention", "at_risk"]
ENTRY_STATUSES = ["pending", "approved", "rejected"]

# A milestone whose actual progress trails the planned line by no more than
# this many points is "behind but recoverable"; past it, it's at risk. Tuned
# to one sprint's worth of slip on a typical 6-8 week milestone.
NEEDS_ATTENTION_GAP = 15.0

# Organization Health score weights. Completion carries the most because it's
# the outcome; on-time delivery and the overdue backlog are the leading
# indicators that it will keep holding.
_HEALTH_WEIGHTS = {"completion": 0.5, "on_time": 0.3, "not_overdue": 0.2}

TREND_MONTHS = 6


# --------------------------------------------------------------------------
# small helpers
# --------------------------------------------------------------------------
def _now() -> dt.datetime:
    return dt.datetime.now(dt.timezone.utc)


def _iso_now() -> str:
    return _now().isoformat()


def _today() -> dt.date:
    return _now().date()


def _as_date(value) -> dt.date | None:
    """Dates are stored as ISO strings ("2026-07-29"); tolerate datetimes and
    junk because seed data, API input and OpenProject-imported rows have all
    produced each of those at some point."""
    if isinstance(value, dt.datetime):
        return value.date()
    if isinstance(value, dt.date):
        return value
    if isinstance(value, str) and value:
        try:
            return dt.date.fromisoformat(value[:10])
        except ValueError:
            return None
    return None


def _clamp(value: float, low: float = 0.0, high: float = 100.0) -> float:
    return max(low, min(high, value))


def _pct(numerator: float, denominator: float) -> float:
    return round(numerator / denominator * 100, 1) if denominator else 0.0


def _round(value: float) -> float:
    return round(value, 1)


def _month_key(date: dt.date) -> str:
    return date.strftime("%Y-%m")


def _month_end(year: int, month: int) -> dt.date:
    return (dt.date(year + month // 12, month % 12 + 1, 1) - dt.timedelta(days=1))


def _recent_month_ends(today: dt.date, count: int) -> list[dt.date]:
    """Month-end dates for the trailing `count` months, oldest first. The
    current month uses *today* rather than its true end so the last trend
    point is "where we actually are", not a projection into the future."""
    ends: list[dt.date] = []
    year, month = today.year, today.month
    for _ in range(count):
        end = _month_end(year, month)
        ends.append(min(end, today))
        month -= 1
        if month == 0:
            year, month = year - 1, 12
    return list(reversed(ends))


# --------------------------------------------------------------------------
# the formula
# --------------------------------------------------------------------------
class ProgressIndex:
    """Bulk-loaded tasks + approved daily entries for a set of milestones.

    Built once per request and shared by every zone of the payload, so the
    dashboard makes two extra queries total no matter how many milestones are
    in scope — and, more importantly, so the cards, the donut, the trend and
    the tables all read the same numbers.
    """

    def __init__(self, db: Database, milestone_ids: list[str]):
        self.tasks_by_ms: dict[str, list[dict]] = defaultdict(list)
        self.entries_by_task: dict[str, list[dict]] = defaultdict(list)
        if not milestone_ids:
            return
        for task in db.milestone_tasks.find({"milestone_id": {"$in": milestone_ids}}, {"_id": 0}):
            self.tasks_by_ms[task["milestone_id"]].append(task)
        for entry in db.milestone_daily_entries.find(
            {"milestone_id": {"$in": milestone_ids}, "status": "approved"}, {"_id": 0}
        ):
            key = entry.get("task_id") or entry["milestone_id"]
            self.entries_by_task[key].append(entry)

    def task_completion(self, task: dict, as_of: dt.date | None = None) -> float:
        """Completion of one task, optionally rewound to `as_of`."""
        done_on = _as_date(task.get("completed_at"))
        if task.get("status") == "done" and (as_of is None or (done_on and done_on <= as_of)):
            return 100.0
        total = 0.0
        for entry in self.entries_by_task.get(task["task_id"], ()):
            if as_of is not None:
                entry_on = _as_date(entry.get("date"))
                if entry_on is None or entry_on > as_of:
                    continue
            total += float(entry.get("progress_delta") or 0)
        return _clamp(total)

    def milestone_level(self, milestone_id: str, as_of: dt.date | None = None) -> float:
        """Approved entries logged against the milestone rather than a specific
        task. The UI offers that (`task_id` is optional on a Daily Success
        submission), so these have to count for something — otherwise an
        approved entry would visibly change nothing."""
        total = 0.0
        for entry in self.entries_by_task.get(milestone_id, ()):
            if as_of is not None:
                entry_on = _as_date(entry.get("date"))
                if entry_on is None or entry_on > as_of:
                    continue
            total += float(entry.get("progress_delta") or 0)
        return total

    def actual(self, milestone: dict, as_of: dt.date | None = None) -> float:
        """Weightage-weighted completion across the milestone's tasks, plus any
        progress logged against the milestone as a whole.

        A milestone with no tasks yet (freshly created through the UI) has no
        weightage to distribute, so milestone-level entries are all there is —
        falling back, when there are none of those either, to whatever progress
        was recorded on the document (and, when rewound, to a binary
        completed/not-completed, since there's no history to replay).
        """
        milestone_id = milestone["milestone_id"]
        loose = self.milestone_level(milestone_id, as_of)
        tasks = self.tasks_by_ms.get(milestone_id, [])
        if not tasks:
            if loose:
                return _round(_clamp(loose))
            if as_of is None:
                return _clamp(float(milestone.get("progress_pct") or 0))
            done_on = _as_date(milestone.get("completed_at"))
            return 100.0 if done_on and done_on <= as_of else 0.0
        weight_total = sum(max(int(t.get("weightage") or 0), 0) for t in tasks)
        if weight_total <= 0:  # every task unweighted -> treat them as equal
            from_tasks = sum(self.task_completion(t, as_of) for t in tasks) / len(tasks)
        else:
            from_tasks = sum(
                max(int(t.get("weightage") or 0), 0) * self.task_completion(t, as_of)
                for t in tasks
            ) / weight_total
        return _round(_clamp(from_tasks + loose))


def planned_pct(milestone: dict, as_of: dt.date | None = None) -> float:
    """Share of the milestone's calendar that has elapsed. Health compares
    actual progress against this line — that's the "progress vs time elapsed"
    rule the tracker is specified with."""
    start = _as_date(milestone.get("start_date"))
    due = _as_date(milestone.get("due_date"))
    today = as_of or _today()
    if not start or not due or due <= start:
        return 100.0 if due and today >= due else 0.0
    return _round(_clamp((today - start).days / (due - start).days * 100))


def health_of(actual: float, planned: float) -> str:
    if actual >= planned:
        return "good"
    return "needs_attention" if planned - actual <= NEEDS_ATTENTION_GAP else "at_risk"


def is_overdue(milestone: dict, as_of: dt.date | None = None) -> bool:
    """`as_of` rewinds the answer: `status` on the document is always today's
    status, so a historical comparison has to go by `completed_at` instead —
    otherwise last month's overdue count silently absorbs everything finished
    since, and the month-over-month delta on the Overdue card is meaningless."""
    due = _as_date(milestone.get("due_date"))
    if not due:
        return False
    when = as_of or _today()
    done = _as_date(milestone.get("completed_at"))
    if done and done <= when:
        return False
    if as_of is None and milestone.get("status") == "completed":
        return False
    return due < when


def overdue_days(milestone: dict, as_of: dt.date | None = None) -> int:
    due = _as_date(milestone.get("due_date"))
    if not due or not is_overdue(milestone, as_of):
        return 0
    return ((as_of or _today()) - due).days


def decorate(milestone: dict, index: ProgressIndex, as_of: dt.date | None = None) -> dict:
    """Milestone document + every derived field the UI renders."""
    actual = index.actual(milestone, as_of)
    planned = planned_pct(milestone, as_of)
    due = _as_date(milestone.get("due_date"))
    today = as_of or _today()
    out = dict(milestone)
    out.pop("_id", None)
    out.update({
        "progress_pct": actual,
        "actual_pct": actual,
        "planned_pct": planned,
        "delayed_pct": _round(max(0.0, planned - actual)),
        "health": "good" if actual >= 100 else health_of(actual, planned),
        "overdue": is_overdue(milestone, today),
        "overdue_days": overdue_days(milestone, today),
        "days_left": (due - today).days if due else None,
    })
    return out


def recompute(db: Database, milestone_id: str) -> float:
    """Recalculate and persist `progress_pct`. The only writer of that field —
    call it after any task or daily-entry change."""
    milestone = db.tracker_milestones.find_one({"milestone_id": milestone_id}, {"_id": 0})
    if not milestone:
        return 0.0
    index = ProgressIndex(db, [milestone_id])
    actual = index.actual(milestone)
    update: dict = {"progress_pct": actual, "updated_at": _iso_now()}
    # Reaching 100% closes the milestone; dropping back below reopens it, so a
    # rejected entry can't leave a milestone stuck on "completed".
    if actual >= 100 and milestone.get("status") != "completed":
        update["status"] = "completed"
        update["completed_at"] = _today().isoformat()
    elif actual < 100 and milestone.get("status") == "completed":
        update["status"] = "in_progress"
        update["completed_at"] = None
    db.tracker_milestones.update_one({"milestone_id": milestone_id}, {"$set": update})
    return actual


# --------------------------------------------------------------------------
# scoping / permissions
# --------------------------------------------------------------------------
def scope_filter(db: Database, user: dict) -> dict:
    """Row-level scope by org level, mirroring `resource_mgmt._scoped_teams`:
    L4 sees the company, L3 their department, L2 their team (plus anything
    they personally own), L1 and external roles only their own milestones."""
    level = user_level(user)
    if level >= 4:
        return {}
    if level == 3:
        return {"department": user.get("department")}
    if level == 2:
        return {"$or": [{"team_id": user.get("team_id")},
                        {"owner_id": user.get("user_id")},
                        {"manager_id": user.get("user_id")}]}
    return {"$or": [{"owner_id": user.get("user_id")},
                    {"manager_id": user.get("user_id")}]}


def can_view(db: Database, user: dict, milestone: dict) -> bool:
    level = user_level(user)
    if level >= 4:
        return True
    if level == 3:
        return milestone.get("department") == user.get("department")
    uid = user.get("user_id")
    if uid in (milestone.get("owner_id"), milestone.get("manager_id")):
        return True
    return level == 2 and milestone.get("team_id") == user.get("team_id")


def can_manage(user: dict, milestone: dict | None) -> bool:
    """Create/edit/delete. Department heads and above, the milestone's own
    owner or manager, or the lead of the team it sits in."""
    level = user_level(user)
    if level >= 3:
        return True
    if milestone is None:
        return level >= 2
    uid = user.get("user_id")
    if uid in (milestone.get("owner_id"), milestone.get("manager_id")):
        return True
    return level == 2 and milestone.get("team_id") == user.get("team_id")


def can_approve(user: dict, milestone: dict, entry: dict) -> bool:
    """Approving your own daily entry would make the "approved activities"
    rule meaningless, so it is refused regardless of level."""
    if entry.get("user_id") == user.get("user_id"):
        return False
    level = user_level(user)
    if level >= 3:
        return True
    if user.get("user_id") == milestone.get("manager_id"):
        return True
    return level == 2 and milestone.get("team_id") == user.get("team_id")


# --------------------------------------------------------------------------
# query building
# --------------------------------------------------------------------------
def build_query(db: Database, user: dict, filters: dict | None = None) -> dict:
    """Scope + UI filters. `date_from`/`date_to` bound the *due date* — the
    dashboard's date-range control is "what's landing in this window"."""
    filters = filters or {}
    query: dict = dict(scope_filter(db, user))
    simple = {
        "department": filters.get("department"),
        "team_id": filters.get("team"),
        "project_id": filters.get("project"),
        "category": filters.get("category"),
        "manager_id": filters.get("manager"),
        "owner_id": filters.get("owner"),
        "status": filters.get("status"),
        "priority": filters.get("priority"),
        "health": filters.get("health"),
    }
    for field, value in simple.items():
        if value and value != "all":
            # `health` isn't stored (it's derived per read) — filtered later.
            if field != "health":
                query[field] = value
    due: dict = {}
    if filters.get("date_from"):
        due["$gte"] = filters["date_from"]
    if filters.get("date_to"):
        due["$lte"] = filters["date_to"]
    if due:
        query["due_date"] = due
    if filters.get("q"):
        term = str(filters["q"]).strip()
        if term:
            rx = {"$regex": term, "$options": "i"}
            clause = [{"name": rx}, {"milestone_id": rx}, {"description": rx}]
            # `scope_filter` may already own the top-level $or; nest both under
            # $and so the search can't widen the caller's visibility.
            if "$or" in query:
                query = {"$and": [{"$or": query.pop("$or")}, {"$or": clause}], **query}
            else:
                query["$or"] = clause
    return query


def _load(db: Database, query: dict) -> list[dict]:
    return list(db.tracker_milestones.find(query, {"_id": 0}))


def _decorate_all(rows: list[dict], index: ProgressIndex,
                  as_of: dt.date | None = None) -> list[dict]:
    return [decorate(r, index, as_of) for r in rows]


def _apply_health_filter(rows: list[dict], health: str | None) -> list[dict]:
    if not health or health == "all":
        return rows
    return [r for r in rows if r.get("health") == health]


# --------------------------------------------------------------------------
# lookup maps
# --------------------------------------------------------------------------
def _user_map(db: Database) -> dict[str, dict]:
    return {u["user_id"]: u for u in db.users.find(
        {}, {"_id": 0, "user_id": 1, "name": 1, "department": 1, "designation": 1,
             "team_id": 1, "role": 1, "level": 1, "status": 1})}


def _dept_map(db: Database) -> dict[str, str]:
    return {d["dept_id"]: d.get("name", d["dept_id"]) for d in db.departments.find({}, {"_id": 0})}


def _team_map(db: Database) -> dict[str, str]:
    return {t["team_id"]: t.get("name", t["team_id"]) for t in db.teams.find({}, {"_id": 0})}


def _project_map(db: Database) -> dict[str, str]:
    return {p["project_id"]: p.get("name", p["project_id"])
            for p in db.projects.find({}, {"_id": 0, "project_id": 1, "name": 1})}


def _label(rows: list[dict], users: dict, depts: dict, teams: dict,
           projects: dict) -> list[dict]:
    """Attach the display names every table in the UI shows next to the ids."""
    for row in rows:
        row["owner_name"] = users.get(row.get("owner_id"), {}).get("name")
        row["manager_name"] = users.get(row.get("manager_id"), {}).get("name")
        row["department_name"] = depts.get(row.get("department"), row.get("department"))
        row["team_name"] = teams.get(row.get("team_id"))
        row["project_name"] = projects.get(row.get("project_id"))
    return rows


# --------------------------------------------------------------------------
# Screen 1 — Dashboard (Overview)
# --------------------------------------------------------------------------
def _card(card_id: str, label: str, value: float, unit: str, previous: float | None,
          higher_is_better: bool = True, sub: str | None = None) -> dict:
    """Shaped like `SuccessCard` so the frontend reuses MiniStatCard."""
    delta_pct = None
    direction = "flat"
    good = True
    if previous:
        delta_pct = _round((value - previous) / abs(previous) * 100)
        if delta_pct > 0:
            direction = "up"
        elif delta_pct < 0:
            direction = "down"
        good = (delta_pct >= 0) if higher_is_better else (delta_pct <= 0)
    return {"id": card_id, "label": label, "value": value, "unit": unit,
            "delta_pct": delta_pct, "delta_direction": direction, "good": good,
            "sub": sub}


def _status_slices(rows: list[dict]) -> list[dict]:
    """Mutually exclusive so the slices actually sum to the donut total: an
    overdue milestone is counted as Overdue rather than twice."""
    labels = {"completed": "Completed", "in_progress": "In Progress",
              "pending": "Pending", "pending_review": "Pending Review",
              "not_started": "Not Started", "blocked": "Blocked"}
    counts: dict[str, int] = defaultdict(int)
    for row in rows:
        if row.get("overdue"):
            counts["Overdue"] += 1
        else:
            counts[labels.get(row.get("status"), "Pending")] += 1
    order = ["Completed", "In Progress", "Pending", "Pending Review",
             "Not Started", "Blocked", "Overdue"]
    return [{"label": name, "value": counts[name]} for name in order if counts[name]]


def _trend(rows: list[dict], index: ProgressIndex, today: dt.date) -> dict:
    points = []
    for end in _recent_month_ends(today, TREND_MONTHS):
        live = [r for r in rows if (_as_date(r.get("created_at")) or end) <= end]
        if live:
            actual = _round(sum(index.actual(r, end) for r in live) / len(live))
            planned = _round(sum(planned_pct(r, end) for r in live) / len(live))
        else:
            actual = planned = 0.0
        points.append({
            "t": end.strftime("%b"), "month": _month_key(end),
            "planned": planned, "actual": actual,
            "delayed": _round(max(0.0, planned - actual)),
        })
    return {"granularity": "monthly", "points": points}


def _department_overview(rows: list[dict], depts: dict) -> list[dict]:
    buckets: dict[str, list[dict]] = defaultdict(list)
    for row in rows:
        buckets[row.get("department") or "unassigned"].append(row)
    out = []
    for dept_id, items in buckets.items():
        progress = _round(sum(r["progress_pct"] for r in items) / len(items))
        planned = _round(sum(r["planned_pct"] for r in items) / len(items))
        out.append({
            "dept_id": dept_id, "name": depts.get(dept_id, dept_id),
            "progress_pct": progress, "planned_pct": planned,
            "total": len(items),
            "completed": sum(1 for r in items if r.get("status") == "completed"),
            "overdue": sum(1 for r in items if r.get("overdue")),
            "health": health_of(progress, planned),
        })
    return sorted(out, key=lambda d: d["progress_pct"], reverse=True)


def _performer_rows(rows: list[dict], users: dict, depts: dict,
                    month: str) -> tuple[list[dict], list[dict]]:
    """Top Performers + Employees Needing Attention, from one pass over the
    same per-owner buckets so the two tables can't contradict each other."""
    by_owner: dict[str, list[dict]] = defaultdict(list)
    for row in rows:
        if row.get("owner_id"):
            by_owner[row["owner_id"]].append(row)

    performers, attention = [], []
    for owner_id, items in by_owner.items():
        person = users.get(owner_id, {})
        dept = depts.get(person.get("department"), person.get("department"))
        completed_month = [
            r for r in items
            if r.get("status") == "completed"
            and str(r.get("completed_at") or "")[:7] == month
        ]
        completed_total = sum(1 for r in items if r.get("status") == "completed")
        completion = _pct(completed_total, len(items))
        on_time = [r for r in items if r.get("status") == "completed"
                   and not _late(r)]
        on_time_rate = _pct(len(on_time), completed_total) if completed_total else 0.0
        # Volume is capped so someone holding 30 tiny milestones can't outrank
        # a person who actually finished theirs.
        volume = min(len(completed_month) / 5, 1.0) * 100
        score = round(completion * 0.6 + on_time_rate * 0.3 + volume * 0.1)
        if completed_month:
            performers.append({
                "user_id": owner_id, "name": person.get("name", owner_id),
                "department": dept, "designation": person.get("designation"),
                "completed": len(completed_month), "total": len(items),
                "completion_pct": completion, "score": score,
            })

        overdue_items = [r for r in items if r.get("overdue")]
        if overdue_items:
            worst = max(r["overdue_days"] for r in overdue_items)
            attention.append({
                "user_id": owner_id, "name": person.get("name", owner_id),
                "department": dept, "designation": person.get("designation"),
                "overdue_milestones": len(overdue_items), "overdue_days": worst,
                "risk": _risk(len(overdue_items), worst),
            })

    performers.sort(key=lambda p: (-p["score"], -p["completed"], p["name"]))
    for rank, row in enumerate(performers, start=1):
        row["rank"] = rank
    attention.sort(key=lambda a: (-a["overdue_milestones"], -a["overdue_days"], a["name"]))
    return performers, attention


def _late(milestone: dict) -> bool:
    done = _as_date(milestone.get("completed_at"))
    due = _as_date(milestone.get("due_date"))
    return bool(done and due and done > due)


def _risk(count: int, days: int) -> str:
    if count >= 3 or days >= 7:
        return "High"
    if count >= 2 or days >= 4:
        return "Medium"
    return "Low"


def _upcoming(rows: list[dict], limit: int = 8) -> list[dict]:
    live = [r for r in rows
            if r.get("status") != "completed" and r.get("days_left") is not None
            and r["days_left"] >= 0]
    live.sort(key=lambda r: (r["days_left"], r.get("name") or ""))
    return [{"milestone_id": r["milestone_id"], "name": r.get("name"),
             "due_date": r.get("due_date"), "priority": r.get("priority"),
             "days_left": r["days_left"], "owner_name": r.get("owner_name"),
             "project_name": r.get("project_name")}
            for r in live[:limit]]


def _org_health(rows: list[dict]) -> dict:
    if not rows:
        return {"score": 0, "band": "No Data"}
    completion = sum(r["progress_pct"] for r in rows) / len(rows)
    finished = [r for r in rows if r.get("status") == "completed"]
    on_time = _pct(sum(1 for r in finished if not _late(r)), len(finished)) if finished else completion
    not_overdue = 100 - _pct(sum(1 for r in rows if r.get("overdue")), len(rows))
    score = round(
        completion * _HEALTH_WEIGHTS["completion"]
        + on_time * _HEALTH_WEIGHTS["on_time"]
        + not_overdue * _HEALTH_WEIGHTS["not_overdue"]
    )
    if score >= 80:
        band = "Excellent"
    elif score >= 65:
        band = "Good"
    elif score >= 50:
        band = "Needs Attention"
    else:
        band = "At Risk"
    return {"score": score, "band": band, "completion_pct": _round(completion),
            "on_time_pct": _round(on_time)}


def filter_options(db: Database, user: dict) -> dict:
    """Only the values that actually appear inside the caller's scope — a team
    lead shouldn't be offered a department filter they can never see rows for."""
    rows = _load(db, scope_filter(db, user))
    depts, teams, projects = _dept_map(db), _team_map(db), _project_map(db)
    users = _user_map(db)

    def uniq(field: str) -> list[str]:
        return sorted({r.get(field) for r in rows if r.get(field)})

    return {
        "departments": [{"value": d, "label": depts.get(d, d)} for d in uniq("department")],
        "teams": [{"value": t, "label": teams.get(t, t)} for t in uniq("team_id")],
        "projects": [{"value": p, "label": projects.get(p, p)} for p in uniq("project_id")],
        "categories": [{"value": c, "label": c} for c in uniq("category")],
        "managers": [{"value": m, "label": users.get(m, {}).get("name", m)}
                     for m in uniq("manager_id")],
        "owners": [{"value": o, "label": users.get(o, {}).get("name", o)}
                   for o in uniq("owner_id")],
        "statuses": STATUSES,
        "priorities": PRIORITIES,
    }


def build_dashboard(db: Database, user: dict, filters: dict | None = None) -> dict:
    today = _today()
    rows_raw = _load(db, build_query(db, user, filters))
    index = ProgressIndex(db, [r["milestone_id"] for r in rows_raw])
    rows = _apply_health_filter(_decorate_all(rows_raw, index, today),
                                (filters or {}).get("health"))
    users, depts, teams, projects = (_user_map(db), _dept_map(db),
                                     _team_map(db), _project_map(db))
    _label(rows, users, depts, teams, projects)

    month = _month_key(today)
    prev_end = _recent_month_ends(today, 2)[0]
    prev_month = _month_key(prev_end)
    prev = _decorate_all(
        [r for r in rows_raw if (_as_date(r.get("created_at")) or prev_end) <= prev_end],
        index, prev_end)

    def _open_at(row: dict, when: dt.date) -> bool:
        """`status` on the document is today's status, so a month-over-month
        comparison has to rewind it: a milestone was open at `when` unless it
        had already been completed by then."""
        done = _as_date(row.get("completed_at"))
        return not (done and done <= when)

    active = [r for r in rows if r.get("status") != "completed"]
    prev_active = [r for r in prev if _open_at(r, prev_end)]
    completed_month = [r for r in rows if str(r.get("completed_at") or "")[:7] == month]
    completed_prev = [r for r in rows if str(r.get("completed_at") or "")[:7] == prev_month]
    overdue = [r for r in rows if r.get("overdue")]
    prev_overdue = [r for r in prev if r.get("overdue")]
    owners = {r["owner_id"] for r in rows if r.get("owner_id")}
    prev_owners = {r["owner_id"] for r in prev if r.get("owner_id")}
    completion = _round(sum(r["progress_pct"] for r in rows) / len(rows)) if rows else 0.0
    prev_completion = _round(sum(r["progress_pct"] for r in prev) / len(prev)) if prev else 0.0
    health = _org_health(rows)

    performers, attention = _performer_rows(rows, users, depts, month)

    return {
        "generated_at": _iso_now(),
        "period": {"month": month, "from": (filters or {}).get("date_from"),
                   "to": (filters or {}).get("date_to")},
        "cards": [
            _card("total_employees", "Total Employees", len(owners), "count", len(prev_owners)),
            _card("active_milestones", "Active Milestones", len(active), "count", len(prev_active)),
            _card("completed_month", "Completed This Month", len(completed_month),
                  "count", len(completed_prev)),
            _card("overdue", "Overdue Milestones", len(overdue), "count",
                  len(prev_overdue), higher_is_better=False),
            _card("company_completion", "Company Completion", completion, "pct",
                  prev_completion),
            _card("org_health", "Organization Health", health["score"], "score", None,
                  sub=f"Score {health['score']}/100"),
        ],
        "org_health": health,
        "status_donut": {"total": len(rows), "slices": _status_slices(rows)},
        "trend": _trend(rows, index, today),
        "departments": _department_overview(rows, depts),
        "top_performers": performers[:5],
        "needs_attention": attention[:5],
        "upcoming_deadlines": _upcoming(rows),
        "totals": {"all": len(rows), "active": len(active),
                   "completed": len(rows) - len(active), "overdue": len(overdue)},
    }


# --------------------------------------------------------------------------
# Screen 2 — Milestone List
# --------------------------------------------------------------------------
_SORTABLE = {"milestone_id", "name", "due_date", "progress_pct", "priority",
             "status", "department", "health"}


def list_milestones(db: Database, user: dict, filters: dict | None = None, *,
                    page: int = 1, page_size: int = 20,
                    sort: str = "due_date", order: str = "asc") -> dict:
    """Paged after decoration, not in Mongo: `health`, `overdue` and the
    rewound progress only exist once the formula has run, and the list screen
    filters and sorts on exactly those."""
    rows_raw = _load(db, build_query(db, user, filters))
    index = ProgressIndex(db, [r["milestone_id"] for r in rows_raw])
    rows = _apply_health_filter(_decorate_all(rows_raw, index),
                                (filters or {}).get("health"))
    _label(rows, _user_map(db), _dept_map(db), _team_map(db), _project_map(db))

    key = sort if sort in _SORTABLE else "due_date"
    if key == "health":
        rows.sort(key=lambda r: HEALTH_ORDER.index(r.get("health", "good")),
                  reverse=order == "desc")
    elif key == "priority":
        rows.sort(key=lambda r: PRIORITIES.index(r["priority"])
                  if r.get("priority") in PRIORITIES else len(PRIORITIES),
                  reverse=order == "desc")
    else:
        rows.sort(key=lambda r: (r.get(key) is None, r.get(key) or ""),
                  reverse=order == "desc")

    page = max(1, int(page))
    page_size = max(1, min(int(page_size), 200))
    start = (page - 1) * page_size
    return {"items": rows[start:start + page_size], "total": len(rows),
            "page": page, "page_size": page_size,
            "generated_at": _iso_now()}


# --------------------------------------------------------------------------
# Screen 3 — Milestone Details
# --------------------------------------------------------------------------
def get_detail(db: Database, user: dict, milestone_id: str) -> dict | None:
    milestone = db.tracker_milestones.find_one({"milestone_id": milestone_id}, {"_id": 0})
    if not milestone or not can_view(db, user, milestone):
        return None
    index = ProgressIndex(db, [milestone_id])
    row = decorate(milestone, index)
    users, depts, teams, projects = (_user_map(db), _dept_map(db),
                                     _team_map(db), _project_map(db))
    _label([row], users, depts, teams, projects)

    tasks = sorted(index.tasks_by_ms.get(milestone_id, []),
                   key=lambda t: t.get("order", 0))
    for task in tasks:
        task["completion_pct"] = index.task_completion(task)
        task["assignee_name"] = users.get(task.get("assignee_id"), {}).get("name")

    entries = list(db.milestone_daily_entries.find(
        {"milestone_id": milestone_id}, {"_id": 0}).sort("date", -1))
    task_titles = {t["task_id"]: t.get("title") for t in tasks}
    for entry in entries:
        entry["user_name"] = users.get(entry.get("user_id"), {}).get("name")
        entry["task_title"] = task_titles.get(entry.get("task_id"))
        entry["approver_name"] = users.get(entry.get("approver_id"), {}).get("name")

    dep_ids = milestone.get("dependencies") or []
    deps = []
    if dep_ids:
        dep_docs = _load(db, {"milestone_id": {"$in": dep_ids}})
        dep_index = ProgressIndex(db, dep_ids)
        deps = _label(_decorate_all(dep_docs, dep_index), users, depts, teams, projects)

    documents = list(db.documents.find({"milestone_id": milestone_id}, {"_id": 0}))
    comments = list(db.milestone_comments.find(
        {"milestone_id": milestone_id}, {"_id": 0}).sort("created_at", 1))
    for comment in comments:
        comment["user_name"] = users.get(comment.get("user_id"), {}).get("name")
    activity = list(db.milestone_activity.find(
        {"milestone_id": milestone_id}, {"_id": 0}).sort("at", -1).limit(100))
    for event in activity:
        event["actor_name"] = users.get(event.get("actor_id"), {}).get("name")

    return {
        "milestone": row,
        "tasks": tasks,
        "daily_entries": entries,
        "dependencies": deps,
        "documents": documents,
        "comments": comments,
        "timeline": activity,
        "trend": _detail_trend(row, index),
        "permissions": {"can_manage": can_manage(user, milestone),
                        "can_approve": can_approve(user, milestone, {})},
        "counts": {"tasks": len(tasks), "daily_entries": len(entries),
                   "dependencies": len(deps), "documents": len(documents),
                   "comments": len(comments)},
        "generated_at": _iso_now(),
    }


def _detail_trend(milestone: dict, index: ProgressIndex) -> dict:
    """Per-milestone planned/actual/delayed replayed month by month over its
    own lifespan (falls back to the trailing 6 months for open-ended rows)."""
    start = _as_date(milestone.get("start_date")) or _today()
    today = _today()
    ends: list[dt.date] = []
    year, month = start.year, start.month
    while dt.date(year, month, 1) <= today.replace(day=1):
        ends.append(min(_month_end(year, month), today))
        month += 1
        if month == 13:
            year, month = year + 1, 1
    if not ends:
        ends = _recent_month_ends(today, TREND_MONTHS)
    points = []
    for end in ends[-12:]:
        actual = index.actual(milestone, end)
        planned = planned_pct(milestone, end)
        points.append({"t": end.strftime("%b"), "month": _month_key(end),
                       "planned": planned, "actual": actual,
                       "delayed": _round(max(0.0, planned - actual))})
    return {"granularity": "monthly", "points": points}


# --------------------------------------------------------------------------
# Screen 4 — Employee Milestones
# --------------------------------------------------------------------------
def _reports_to_chain(db: Database, user_id: str) -> set[str]:
    """Everyone above `user_id` in the reports_to chain — used to let a lead
    open a report's milestones without granting them the whole department."""
    chain: set[str] = set()
    current = db.users.find_one({"user_id": user_id}, {"_id": 0, "reports_to": 1})
    seen = 0
    while current and current.get("reports_to") and seen < 10:
        boss = current["reports_to"]
        chain.add(boss)
        current = db.users.find_one({"user_id": boss}, {"_id": 0, "reports_to": 1})
        seen += 1
    return chain


def can_view_employee(db: Database, user: dict, target_id: str) -> bool:
    if user.get("user_id") == target_id:
        return True
    level = user_level(user)
    if level >= 4:
        return True
    target = db.users.find_one({"user_id": target_id}, {"_id": 0})
    if not target:
        return False
    if level == 3 and target.get("department") == user.get("department"):
        return True
    if level >= 2 and user.get("user_id") in _reports_to_chain(db, target_id):
        return True
    return False


def employee_view(db: Database, user: dict, target_id: str) -> dict | None:
    if not can_view_employee(db, user, target_id):
        return None
    person = db.users.find_one({"user_id": target_id}, {"_id": 0, "password_hash": 0})
    if not person:
        return None
    rows_raw = _load(db, {"owner_id": target_id})
    index = ProgressIndex(db, [r["milestone_id"] for r in rows_raw])
    rows = _decorate_all(rows_raw, index)
    users, depts, teams, projects = (_user_map(db), _dept_map(db),
                                     _team_map(db), _project_map(db))
    _label(rows, users, depts, teams, projects)

    completed = [r for r in rows if r.get("status") == "completed"]
    active = [r for r in rows if r.get("status") != "completed"]
    in_progress = [r for r in active if r.get("status") == "in_progress"]
    overdue = [r for r in rows if r.get("overdue")]
    return {
        "employee": {
            "user_id": target_id, "name": person.get("name"),
            "designation": person.get("designation"),
            "department": person.get("department"),
            "department_name": depts.get(person.get("department")),
            "team_name": teams.get(person.get("team_id")),
            "email": person.get("email"),
        },
        "stats": {
            "total": len(rows), "completed": len(completed),
            "in_progress": len(in_progress), "overdue": len(overdue),
            "completion_pct": _pct(len(completed), len(rows)),
            "avg_progress_pct": _round(sum(r["progress_pct"] for r in rows) / len(rows))
            if rows else 0.0,
        },
        "active": sorted(active, key=lambda r: (r.get("due_date") or "")),
        "completed": sorted(completed, key=lambda r: (r.get("completed_at") or ""),
                            reverse=True),
        "generated_at": _iso_now(),
    }


# --------------------------------------------------------------------------
# Screen 5 — Department Dashboard
# --------------------------------------------------------------------------
def department_view(db: Database, user: dict, dept_id: str,
                    filters: dict | None = None) -> dict | None:
    level = user_level(user)
    if level < 3 or (level == 3 and user.get("department") != dept_id):
        return None
    merged = dict(filters or {})
    merged["department"] = dept_id
    today = _today()
    rows_raw = _load(db, build_query(db, user, merged))
    index = ProgressIndex(db, [r["milestone_id"] for r in rows_raw])
    rows = _decorate_all(rows_raw, index, today)
    users, depts, teams, projects = (_user_map(db), _dept_map(db),
                                     _team_map(db), _project_map(db))
    _label(rows, users, depts, teams, projects)

    completed = [r for r in rows if r.get("status") == "completed"]
    in_progress = [r for r in rows if r.get("status") == "in_progress"]
    overdue = [r for r in rows if r.get("overdue")]
    priority_counts: dict[str, int] = defaultdict(int)
    for row in rows:
        priority_counts[row.get("priority") or "Unset"] += 1

    performers, attention = _performer_rows(rows, users, depts, _month_key(today))
    return {
        "department": {"dept_id": dept_id, "name": depts.get(dept_id, dept_id)},
        "stats": {
            "total": len(rows), "completed": len(completed),
            "in_progress": len(in_progress), "overdue": len(overdue),
            "completion_pct": _pct(len(completed), len(rows)),
            "avg_progress_pct": _round(sum(r["progress_pct"] for r in rows) / len(rows))
            if rows else 0.0,
        },
        "trend": _trend(rows, index, today),
        "priority_donut": {
            "total": len(rows),
            "slices": [{"label": p, "value": priority_counts[p]}
                       for p in PRIORITIES + ["Unset"] if priority_counts[p]],
        },
        "status_donut": {"total": len(rows), "slices": _status_slices(rows)},
        "teams": _team_breakdown(rows, teams),
        "top_performers": performers[:5],
        "needs_attention": attention[:5],
        "upcoming_deadlines": _upcoming(rows),
        "generated_at": _iso_now(),
    }


def _team_breakdown(rows: list[dict], teams: dict) -> list[dict]:
    buckets: dict[str, list[dict]] = defaultdict(list)
    for row in rows:
        buckets[row.get("team_id") or "unassigned"].append(row)
    out = []
    for team_id, items in buckets.items():
        progress = _round(sum(r["progress_pct"] for r in items) / len(items))
        planned = _round(sum(r["planned_pct"] for r in items) / len(items))
        out.append({"team_id": team_id, "name": teams.get(team_id, "Unassigned"),
                    "total": len(items), "progress_pct": progress,
                    "overdue": sum(1 for r in items if r.get("overdue")),
                    "health": health_of(progress, planned)})
    return sorted(out, key=lambda t: t["progress_pct"], reverse=True)


def department_summaries(db: Database, user: dict) -> list[dict]:
    """Department picker for screen 5 — only departments the caller may open."""
    level = user_level(user)
    depts = _dept_map(db)
    if level >= 4:
        allowed = sorted(depts)
    elif level == 3 and user.get("department"):
        allowed = [user["department"]]
    else:
        allowed = []
    return [{"dept_id": d, "name": depts.get(d, d)} for d in allowed]


# --------------------------------------------------------------------------
# Screen 6 — Reports & Analytics
# --------------------------------------------------------------------------
REPORTS = [
    {"key": "milestone_status", "title": "Milestone Status Report",
     "description": "Summary of milestone status across the organization."},
    {"key": "employee_performance", "title": "Employee Performance Report",
     "description": "Milestone completion and performance of employees."},
    {"key": "department_performance", "title": "Department Performance Report",
     "description": "Department-wise milestone performance and trends."},
    {"key": "overdue_milestones", "title": "Overdue Milestones Report",
     "description": "List of overdue milestones with details."},
    {"key": "milestone_progress", "title": "Milestone Progress Report",
     "description": "Milestone progress over a time period."},
    {"key": "upcoming_deadlines", "title": "Upcoming Deadlines Report",
     "description": "Milestones due in upcoming days/weeks."},
]

_COLUMN_LIBRARY = [
    {"key": "milestone_id", "title": "ID"},
    {"key": "name", "title": "Milestone Name"},
    {"key": "project_name", "title": "Project"},
    {"key": "owner_name", "title": "Owner"},
    {"key": "manager_name", "title": "Manager"},
    {"key": "department_name", "title": "Department"},
    {"key": "team_name", "title": "Team"},
    {"key": "category", "title": "Category"},
    {"key": "status", "title": "Status"},
    {"key": "priority", "title": "Priority"},
    {"key": "progress_pct", "title": "Progress %"},
    {"key": "planned_pct", "title": "Planned %"},
    {"key": "delayed_pct", "title": "Delayed %"},
    {"key": "health", "title": "Health"},
    {"key": "start_date", "title": "Start Date"},
    {"key": "due_date", "title": "Due Date"},
    {"key": "completed_at", "title": "Completed On"},
    {"key": "overdue_days", "title": "Overdue Days"},
]


def report_catalog() -> dict:
    return {"predefined": REPORTS, "columns": _COLUMN_LIBRARY,
            "statuses": STATUSES, "priorities": PRIORITIES,
            "healths": HEALTH_ORDER}


def _cols(*keys: str) -> list[dict]:
    lookup = {c["key"]: c for c in _COLUMN_LIBRARY}
    return [lookup[k] for k in keys if k in lookup]


def run_report(db: Database, user: dict, key: str,
               filters: dict | None = None) -> dict | None:
    today = _today()
    rows_raw = _load(db, build_query(db, user, filters))
    index = ProgressIndex(db, [r["milestone_id"] for r in rows_raw])
    rows = _apply_health_filter(_decorate_all(rows_raw, index, today),
                                (filters or {}).get("health"))
    users, depts, teams, projects = (_user_map(db), _dept_map(db),
                                     _team_map(db), _project_map(db))
    _label(rows, users, depts, teams, projects)
    meta = next((r for r in REPORTS if r["key"] == key), None)
    if not meta:
        return None

    if key == "milestone_status":
        columns = _cols("milestone_id", "name", "project_name", "owner_name",
                        "department_name", "status", "progress_pct", "due_date", "health")
        data = rows
    elif key == "overdue_milestones":
        columns = _cols("milestone_id", "name", "owner_name", "department_name",
                        "due_date", "overdue_days", "progress_pct", "priority")
        data = sorted([r for r in rows if r.get("overdue")],
                      key=lambda r: -r["overdue_days"])
    elif key == "milestone_progress":
        columns = _cols("milestone_id", "name", "planned_pct", "progress_pct",
                        "delayed_pct", "health", "start_date", "due_date")
        data = sorted(rows, key=lambda r: -r["delayed_pct"])
    elif key == "upcoming_deadlines":
        columns = _cols("milestone_id", "name", "owner_name", "project_name",
                        "due_date", "priority", "progress_pct")
        data = [r for r in rows if r.get("status") != "completed"
                and (r.get("days_left") or -1) >= 0]
        data.sort(key=lambda r: r["days_left"])
    elif key == "employee_performance":
        performers, _ = _performer_rows(rows, users, depts, _month_key(today))
        columns = [{"key": "rank", "title": "Rank"}, {"key": "name", "title": "Employee"},
                   {"key": "department", "title": "Department"},
                   {"key": "total", "title": "Total"},
                   {"key": "completed", "title": "Completed This Month"},
                   {"key": "completion_pct", "title": "Completion %"},
                   {"key": "score", "title": "Score"}]
        data = performers
    else:  # department_performance
        columns = [{"key": "name", "title": "Department"},
                   {"key": "total", "title": "Total"},
                   {"key": "completed", "title": "Completed"},
                   {"key": "overdue", "title": "Overdue"},
                   {"key": "progress_pct", "title": "Progress %"},
                   {"key": "planned_pct", "title": "Planned %"},
                   {"key": "health", "title": "Health"}]
        data = _department_overview(rows, depts)

    return {**meta, "columns": columns,
            "rows": [{c["key"]: row.get(c["key"]) for c in columns} for row in data],
            "row_count": len(data), "generated_at": _iso_now()}


def run_custom_report(db: Database, user: dict, *, columns: list[str],
                      filters: dict | None = None, group_by: str | None = None,
                      title: str = "Custom Report") -> dict:
    today = _today()
    rows_raw = _load(db, build_query(db, user, filters))
    index = ProgressIndex(db, [r["milestone_id"] for r in rows_raw])
    rows = _apply_health_filter(_decorate_all(rows_raw, index, today),
                                (filters or {}).get("health"))
    _label(rows, _user_map(db), _dept_map(db), _team_map(db), _project_map(db))

    picked = _cols(*columns) or _cols("milestone_id", "name", "status", "progress_pct")
    if group_by and group_by in {c["key"] for c in _COLUMN_LIBRARY}:
        buckets: dict[str, list[dict]] = defaultdict(list)
        for row in rows:
            buckets[str(row.get(group_by) or "Unassigned")].append(row)
        out_columns = [{"key": "group", "title": next(
            (c["title"] for c in _COLUMN_LIBRARY if c["key"] == group_by), group_by)},
            {"key": "count", "title": "Milestones"},
            {"key": "completed", "title": "Completed"},
            {"key": "overdue", "title": "Overdue"},
            {"key": "avg_progress", "title": "Avg Progress %"}]
        data = [{
            "group": name,
            "count": len(items),
            "completed": sum(1 for r in items if r.get("status") == "completed"),
            "overdue": sum(1 for r in items if r.get("overdue")),
            "avg_progress": _round(sum(r["progress_pct"] for r in items) / len(items)),
        } for name, items in sorted(buckets.items())]
        return {"key": "custom", "title": title, "columns": out_columns,
                "rows": data, "row_count": len(data), "generated_at": _iso_now()}

    return {"key": "custom", "title": title, "columns": picked,
            "rows": [{c["key"]: r.get(c["key"]) for c in picked} for r in rows],
            "row_count": len(rows), "generated_at": _iso_now()}


def to_csv(columns: list[dict], rows: list[dict]) -> str:
    buffer = io.StringIO()
    writer = csv.writer(buffer, lineterminator="\n")
    writer.writerow([c["title"] for c in columns])
    for row in rows:
        writer.writerow(["" if row.get(c["key"]) is None else row[c["key"]]
                         for c in columns])
    return buffer.getvalue()


LIST_EXPORT_COLUMNS = _cols("milestone_id", "name", "project_name", "owner_name",
                            "department_name", "status", "priority",
                            "progress_pct", "due_date", "health")


# --------------------------------------------------------------------------
# mutations
# --------------------------------------------------------------------------
def log_activity(db: Database, milestone_id: str, *, actor_id: str, type: str,
                 detail: str = "") -> dict:
    event = {"event_id": uuid.uuid4().hex, "milestone_id": milestone_id,
             "actor_id": actor_id, "type": type, "detail": detail,
             "at": _iso_now()}
    db.milestone_activity.insert_one(dict(event))
    return event


def next_milestone_id(db: Database) -> str:
    """Human-facing sequential ids (MS-1258) — the UI shows them verbatim, so
    they can't be uuids."""
    last = db.tracker_milestones.find_one(
        {"milestone_id": {"$regex": r"^MS-\d+$"}}, {"_id": 0, "milestone_id": 1},
        sort=[("milestone_id", -1)])
    start = int(last["milestone_id"].split("-")[1]) if last else 1000
    return f"MS-{start + 1}"


def create_milestone(db: Database, user: dict, payload: dict) -> dict:
    now = _iso_now()
    milestone = {
        "milestone_id": payload.get("milestone_id") or next_milestone_id(db),
        "name": payload.get("name", "Untitled milestone"),
        "description": payload.get("description", ""),
        "project_id": payload.get("project_id"),
        "department": payload.get("department") or user.get("department"),
        "team_id": payload.get("team_id"),
        "owner_id": payload.get("owner_id") or user.get("user_id"),
        "manager_id": payload.get("manager_id") or user.get("user_id"),
        "category": payload.get("category") or "General",
        "priority": payload.get("priority") if payload.get("priority") in PRIORITIES else "Medium",
        "status": payload.get("status") if payload.get("status") in STATUSES else "not_started",
        "start_date": payload.get("start_date") or _today().isoformat(),
        "due_date": payload.get("due_date"),
        "completed_at": None,
        "progress_pct": 0.0,
        "completion_criteria": payload.get("completion_criteria") or [],
        "dependencies": payload.get("dependencies") or [],
        "created_by": user.get("user_id"),
        "created_at": now,
        "updated_at": now,
    }
    db.tracker_milestones.insert_one(dict(milestone))
    log_activity(db, milestone["milestone_id"], actor_id=user.get("user_id"),
                 type="created", detail=milestone["name"])
    owner = milestone.get("owner_id")
    if owner and owner != user.get("user_id"):
        notif_svc.create(
            db, recipient_id=owner, type="milestone",
            title="New milestone assigned",
            body=f"{milestone['name']} is due {milestone.get('due_date') or 'TBD'}",
            action_link=f"/milestones/detail/{milestone['milestone_id']}")
    return milestone


_EDITABLE = {"name", "description", "project_id", "department", "team_id",
             "owner_id", "manager_id", "category", "priority", "status",
             "start_date", "due_date", "completion_criteria", "dependencies"}


def update_milestone(db: Database, user: dict, milestone_id: str,
                     payload: dict) -> dict | None:
    milestone = db.tracker_milestones.find_one({"milestone_id": milestone_id}, {"_id": 0})
    if not milestone:
        return None
    update = {k: v for k, v in payload.items() if k in _EDITABLE}
    if not update:
        return decorate(milestone, ProgressIndex(db, [milestone_id]))
    if update.get("status") == "completed" and not milestone.get("completed_at"):
        update["completed_at"] = _today().isoformat()
    if update.get("status") and update["status"] != "completed":
        update["completed_at"] = None
    update["updated_at"] = _iso_now()
    db.tracker_milestones.update_one({"milestone_id": milestone_id}, {"$set": update})
    log_activity(db, milestone_id, actor_id=user.get("user_id"), type="updated",
                 detail=", ".join(sorted(k for k in update if k != "updated_at")))
    fresh = db.tracker_milestones.find_one({"milestone_id": milestone_id}, {"_id": 0})
    return decorate(fresh, ProgressIndex(db, [milestone_id]))


def delete_milestone(db: Database, milestone_id: str) -> bool:
    result = db.tracker_milestones.delete_one({"milestone_id": milestone_id})
    if result.deleted_count:
        db.milestone_tasks.delete_many({"milestone_id": milestone_id})
        db.milestone_daily_entries.delete_many({"milestone_id": milestone_id})
        db.milestone_comments.delete_many({"milestone_id": milestone_id})
        db.milestone_activity.delete_many({"milestone_id": milestone_id})
        # Leave no dangling dependency pointers behind.
        db.tracker_milestones.update_many(
            {"dependencies": milestone_id},
            {"$pull": {"dependencies": milestone_id}})
    return bool(result.deleted_count)


def add_task(db: Database, user: dict, milestone_id: str, payload: dict) -> dict:
    order = db.milestone_tasks.count_documents({"milestone_id": milestone_id})
    task = {
        "task_id": uuid.uuid4().hex,
        "milestone_id": milestone_id,
        "title": payload.get("title", "Untitled task"),
        "weightage": max(int(payload.get("weightage") or 1), 0),
        "status": payload.get("status") or "todo",
        "assignee_id": payload.get("assignee_id"),
        "due_date": payload.get("due_date"),
        "completed_at": _today().isoformat() if payload.get("status") == "done" else None,
        "order": order,
        "created_at": _iso_now(),
    }
    db.milestone_tasks.insert_one(dict(task))
    recompute(db, milestone_id)
    log_activity(db, milestone_id, actor_id=user.get("user_id"), type="task_added",
                 detail=task["title"])
    return task


def update_task(db: Database, user: dict, milestone_id: str, task_id: str,
                payload: dict) -> dict | None:
    task = db.milestone_tasks.find_one({"task_id": task_id, "milestone_id": milestone_id},
                                       {"_id": 0})
    if not task:
        return None
    update = {k: v for k, v in payload.items()
              if k in {"title", "weightage", "status", "assignee_id", "due_date", "order"}}
    if "weightage" in update:
        update["weightage"] = max(int(update["weightage"] or 0), 0)
    if update.get("status") == "done":
        update["completed_at"] = _today().isoformat()
    elif "status" in update:
        update["completed_at"] = None
    db.milestone_tasks.update_one({"task_id": task_id}, {"$set": update})
    recompute(db, milestone_id)
    log_activity(db, milestone_id, actor_id=user.get("user_id"), type="task_updated",
                 detail=task.get("title", ""))
    return db.milestone_tasks.find_one({"task_id": task_id}, {"_id": 0})


def delete_task(db: Database, user: dict, milestone_id: str, task_id: str) -> bool:
    result = db.milestone_tasks.delete_one({"task_id": task_id, "milestone_id": milestone_id})
    if result.deleted_count:
        db.milestone_daily_entries.delete_many({"task_id": task_id})
        recompute(db, milestone_id)
        log_activity(db, milestone_id, actor_id=user.get("user_id"),
                     type="task_deleted", detail=task_id)
    return bool(result.deleted_count)


def add_daily_entry(db: Database, user: dict, milestone_id: str, payload: dict) -> dict:
    """A Daily Success Tracker submission. Lands as `pending` and contributes
    nothing to progress until somebody with approval rights approves it."""
    entry = {
        "entry_id": uuid.uuid4().hex,
        "milestone_id": milestone_id,
        "task_id": payload.get("task_id"),
        "user_id": payload.get("user_id") or user.get("user_id"),
        "date": payload.get("date") or _today().isoformat(),
        "hours": float(payload.get("hours") or 0),
        "progress_delta": _clamp(float(payload.get("progress_delta") or 0)),
        "note": payload.get("note", ""),
        "status": "pending",
        "approver_id": None,
        "approved_at": None,
        "created_at": _iso_now(),
    }
    db.milestone_daily_entries.insert_one(dict(entry))
    log_activity(db, milestone_id, actor_id=entry["user_id"], type="daily_logged",
                 detail=f"{entry['progress_delta']}% on {entry['date']}")
    milestone = db.tracker_milestones.find_one({"milestone_id": milestone_id}, {"_id": 0})
    approver = (milestone or {}).get("manager_id")
    if approver and approver != entry["user_id"]:
        notif_svc.create(
            db, recipient_id=approver, type="milestone",
            title="Daily success entry awaiting approval",
            body=f"{entry['progress_delta']}% logged on {(milestone or {}).get('name', '')}",
            action_link=f"/milestones/detail/{milestone_id}")
    return entry


def set_entry_status(db: Database, user: dict, milestone_id: str, entry_id: str,
                     status: str) -> dict | None:
    if status not in ("approved", "rejected"):
        return None
    entry = db.milestone_daily_entries.find_one(
        {"entry_id": entry_id, "milestone_id": milestone_id}, {"_id": 0})
    if not entry:
        return None
    db.milestone_daily_entries.update_one({"entry_id": entry_id}, {"$set": {
        "status": status, "approver_id": user.get("user_id"),
        "approved_at": _iso_now()}})
    recompute(db, milestone_id)
    log_activity(db, milestone_id, actor_id=user.get("user_id"),
                 type=f"daily_{status}", detail=entry.get("note", ""))
    if entry.get("user_id"):
        notif_svc.create(
            db, recipient_id=entry["user_id"], type="milestone",
            title=f"Daily entry {status}",
            body=f"Your {entry['date']} entry was {status}.",
            action_link=f"/milestones/detail/{milestone_id}")
    return db.milestone_daily_entries.find_one({"entry_id": entry_id}, {"_id": 0})


def set_dependencies(db: Database, user: dict, milestone_id: str,
                     dependency_ids: list[str]) -> list[str]:
    """Self-references and unknown ids are dropped rather than rejected — the
    picker can go stale between load and save."""
    known = {m["milestone_id"] for m in db.tracker_milestones.find(
        {"milestone_id": {"$in": dependency_ids}}, {"_id": 0, "milestone_id": 1})}
    cleaned = [d for d in dict.fromkeys(dependency_ids)
               if d in known and d != milestone_id]
    db.tracker_milestones.update_one({"milestone_id": milestone_id},
                                     {"$set": {"dependencies": cleaned,
                                               "updated_at": _iso_now()}})
    log_activity(db, milestone_id, actor_id=user.get("user_id"),
                 type="dependencies_updated", detail=", ".join(cleaned))
    return cleaned


def add_comment(db: Database, user: dict, milestone_id: str, body: str) -> dict:
    comment = {"comment_id": uuid.uuid4().hex, "milestone_id": milestone_id,
               "user_id": user.get("user_id"), "body": body,
               "created_at": _iso_now()}
    db.milestone_comments.insert_one(dict(comment))
    log_activity(db, milestone_id, actor_id=user.get("user_id"), type="commented",
                 detail=body[:120])
    comment["user_name"] = user.get("name")
    return comment


def link_document(db: Database, user: dict, milestone_id: str, payload: dict) -> dict:
    """Reuses the existing `documents` collection (tagged with `milestone_id`)
    rather than introducing a parallel attachment store."""
    doc = {
        "doc_id": payload.get("doc_id") or uuid.uuid4().hex,
        "milestone_id": milestone_id,
        "name": payload.get("name", "Document"),
        "url": payload.get("url", ""),
        "kind": payload.get("kind", "link"),
        "uploaded_by": user.get("user_id"),
        "uploaded_at": _iso_now(),
    }
    db.documents.update_one({"doc_id": doc["doc_id"]}, {"$set": doc}, upsert=True)
    log_activity(db, milestone_id, actor_id=user.get("user_id"),
                 type="document_linked", detail=doc["name"])
    return doc
