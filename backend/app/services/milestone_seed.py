"""Deterministic demo data for the Milestone Tracker.

Reads the roster (users/teams/projects) straight out of the database rather
than re-declaring it, so it always lines up with whatever `seed.py` produced
and keeps working if the roster changes.

Writes are **tag-scoped deletes followed by bulk inserts**, not a blanket
`delete_many({})`: every generated document carries `seed_tag="milestone_demo"`,
so a re-seed replaces only what this module created and leaves milestones,
tasks, daily entries and comments submitted through the live app untouched
(see the seed-write rule in CLAUDE.md).

Progress is never written directly — tasks and *approved* daily entries are
generated, then `milestones.recompute()` derives `progress_pct` from them.
That way the demo data can't drift from the formula the screens read.
"""
from __future__ import annotations

import datetime as dt
import random
import uuid

from pymongo import UpdateOne
from pymongo.database import Database

from . import milestones as svc

SEED_TAG = "milestone_demo"
_COLLECTIONS = ("tracker_milestones", "milestone_tasks", "milestone_daily_entries",
                "milestone_comments", "milestone_activity")

CATEGORIES = ["Delivery", "Product", "Quality", "Client", "Process", "Growth",
              "Compliance"]

_NAME_TEMPLATES = [
    "User Dashboard Enhancement", "API Integration Phase 2", "Authentication Module",
    "UI Component Library", "Customer Feedback Analysis", "Server Migration",
    "Sales Strategy Report", "Marketing Campaign Launch", "Payment Gateway Upgrade",
    "Booking Flow Redesign", "Reporting Engine Rewrite", "Data Warehouse Load",
    "Mobile App Release", "Compliance Audit Pack", "Onboarding Automation",
    "Performance Tuning Sprint", "Security Hardening", "Vendor Integration",
    "Quarterly Business Review", "Support SLA Improvement", "Test Automation Suite",
    "Release Readiness Review", "Knowledge Base Refresh", "Cost Optimisation Drive",
]

_TASK_TEMPLATES = [
    "Requirement analysis", "Technical design", "Implementation", "Unit tests",
    "Code review", "Integration testing", "UAT support", "Documentation",
    "Stakeholder sign-off", "Deployment", "Post-release monitoring", "Data migration",
]

_CRITERIA_TEMPLATES = [
    "Design finalized", "All items implemented", "Data integration completed",
    "Testing and bug fixes done", "Deployed to production",
    "Stakeholder sign-off received",
]

_COMMENTS = [
    "Blocked on the client's sandbox credentials — chased again today.",
    "Scope trimmed after review; the reporting piece moves to the next milestone.",
    "Ahead of plan, QA started a week early.",
    "Dependency slipped, expect a few days of drift on the due date.",
    "Great turnaround from the team on the integration fixes.",
    "Needs another round of UAT before we can call this done.",
]

MILESTONES_PER_PERSON = (5, 11)
TASKS_PER_MILESTONE = (3, 8)


def _iso(date: dt.date) -> str:
    return date.isoformat()


def _stamp(date: dt.date) -> str:
    return dt.datetime.combine(date, dt.time(9, 0), dt.timezone.utc).isoformat()


def _owners(db: Database) -> list[dict]:
    """Everyone who can realistically own a milestone: active internal staff.
    Investors/partners (level 0) and people with neither a team nor a
    department are skipped — they'd only produce unassignable rows."""
    out = []
    for user in db.users.find({"status": "active"}, {"_id": 0, "password_hash": 0}):
        if user.get("role") in ("investor", "partner"):
            continue
        if not user.get("department"):
            continue
        out.append(user)
    return sorted(out, key=lambda u: u["user_id"])


def _manager_for(user: dict, teams_by_id: dict[str, dict]) -> str | None:
    if user.get("reports_to"):
        return user["reports_to"]
    team = teams_by_id.get(user.get("team_id") or "")
    if team and team.get("lead_id") != user.get("user_id"):
        return team.get("lead_id")
    return None


def _project_for(user: dict, projects: list[dict], rng: random.Random) -> dict | None:
    if not projects:
        return None
    team_id = user.get("team_id")
    matching = [p for p in projects if team_id and team_id in (p.get("team_ids") or [])]
    return rng.choice(matching or projects)


def _target_progress(start: dt.date, due: dt.date, today: dt.date,
                     rng: random.Random) -> float:
    """Realistic spread: long-past milestones are mostly finished, in-flight
    ones scatter around the planned line (which is what makes the health bands
    and the delayed series show anything at all)."""
    if due < today - dt.timedelta(days=90):
        # Almost everything this old is closed out; the rare survivor is what
        # gives the Overdue card and the at-risk lists something real.
        return 100.0 if rng.random() < 0.97 else round(rng.uniform(55, 95), 1)
    if due < today - dt.timedelta(days=30):
        return 100.0 if rng.random() < 0.9 else round(rng.uniform(55, 95), 1)
    if due < today:
        return 100.0 if rng.random() < 0.55 else round(rng.uniform(40, 95), 1)
    if start > today:
        return 0.0
    span = max((due - start).days, 1)
    planned = min((today - start).days / span, 1.0) * 100
    actual = planned * rng.uniform(0.55, 1.25)
    # An unfinished, not-yet-due milestone must not land on 100 — recompute()
    # would then close it and the "in progress" bucket would empty out.
    return round(min(actual, 98.0), 1)


def _status_for(target: float, start: dt.date, today: dt.date,
                rng: random.Random) -> str:
    if target >= 100:
        return "completed"
    if start > today:
        return "not_started"
    if rng.random() < 0.07:
        return "blocked"
    if target <= 0:
        return "pending"
    if target >= 90 and rng.random() < 0.35:
        return "pending_review"
    return "in_progress"


def _split(amount: float, parts: int, rng: random.Random) -> list[float]:
    """`amount` broken into `parts` positive chunks that sum back exactly."""
    if parts <= 1 or amount <= 0:
        return [round(amount, 1)]
    cuts = sorted(rng.uniform(0, amount) for _ in range(parts - 1))
    chunks, previous = [], 0.0
    for cut in cuts + [amount]:
        chunks.append(round(cut - previous, 1))
        previous = cut
    # Rounding can shave a tenth off; give it back to the largest chunk.
    drift = round(amount - sum(chunks), 1)
    if drift:
        chunks[chunks.index(max(chunks))] = round(max(chunks) + drift, 1)
    return [c for c in chunks if c > 0] or [round(amount, 1)]


def _entry_date(start: dt.date, ceiling: dt.date, rng: random.Random) -> dt.date:
    span = max((ceiling - start).days, 0)
    return start + dt.timedelta(days=rng.randint(0, span) if span else 0)


def seed_milestones(db: Database, now: dt.datetime | None = None) -> dict:
    now = now or dt.datetime.now(dt.timezone.utc)
    today = now.date()
    rng = random.Random(20260728)

    owners = _owners(db)
    if not owners:
        return {"milestones": 0, "tasks": 0, "daily_entries": 0}
    teams_by_id = {t["team_id"]: t for t in db.teams.find({}, {"_id": 0})}
    projects = list(db.projects.find({}, {"_id": 0, "project_id": 1, "name": 1,
                                          "team_ids": 1}))

    for name in _COLLECTIONS:
        db[name].delete_many({"seed_tag": SEED_TAG})

    milestones: list[dict] = []
    tasks: list[dict] = []
    entries: list[dict] = []
    comments: list[dict] = []
    activity: list[dict] = []
    counter = 1000
    all_ids_by_dept: dict[str, list[str]] = {}

    for owner in owners:
        for _ in range(rng.randint(*MILESTONES_PER_PERSON)):
            counter += 1
            milestone_id = f"MS-{counter}"
            duration = rng.choice([21, 30, 45, 60, 75, 90])
            due = today + dt.timedelta(days=rng.randint(-210, 100))
            start = due - dt.timedelta(days=duration)
            target = _target_progress(start, due, today, rng)
            status = _status_for(target, start, today, rng)
            project = _project_for(owner, projects, rng)
            completed_on = None
            if status == "completed":
                # Some land late — that's what makes the on-time rate (and so
                # the Organization Health score) mean something.
                drift = rng.randint(-7, 12)
                completed_on = min(due + dt.timedelta(days=drift), today)

            criteria_count = rng.randint(4, len(_CRITERIA_TEMPLATES))
            criteria = [
                {"label": label,
                 "done": (index + 1) / criteria_count * 100 <= target}
                for index, label in enumerate(_CRITERIA_TEMPLATES[:criteria_count])
            ]

            milestones.append({
                "milestone_id": milestone_id,
                "name": f"{rng.choice(_NAME_TEMPLATES)}",
                "description": (
                    f"{rng.choice(_NAME_TEMPLATES)} workstream for "
                    f"{project['name'] if project else 'internal delivery'}. "
                    "Tracked against weighted tasks and approved daily success entries."
                ),
                "project_id": project["project_id"] if project else None,
                "department": owner.get("department"),
                "team_id": owner.get("team_id"),
                "owner_id": owner["user_id"],
                "manager_id": _manager_for(owner, teams_by_id) or owner["user_id"],
                "category": rng.choice(CATEGORIES),
                "priority": rng.choices(svc.PRIORITIES, weights=[35, 40, 25])[0],
                "status": status,
                "start_date": _iso(start),
                "due_date": _iso(due),
                "completed_at": _iso(completed_on) if completed_on else None,
                "progress_pct": 0.0,  # rewritten by recompute() below
                "completion_criteria": criteria,
                "dependencies": [],
                "created_by": owner["user_id"],
                "created_at": _stamp(start),
                "updated_at": _stamp(min(due, today)),
                "seed_tag": SEED_TAG,
            })
            all_ids_by_dept.setdefault(owner.get("department") or "", []).append(milestone_id)

            # --- tasks + the approved entries that give them their progress ---
            task_count = rng.randint(*TASKS_PER_MILESTONE)
            titles = rng.sample(_TASK_TEMPLATES, k=min(task_count, len(_TASK_TEMPLATES)))
            weights = [rng.randint(1, 5) for _ in titles]
            weight_total = sum(weights)
            remaining = target / 100 * weight_total
            ceiling = min(today, completed_on or today)

            for order, (title, weight) in enumerate(zip(titles, weights)):
                task_id = uuid.uuid4().hex
                if remaining >= weight:
                    completion = 100.0
                    remaining -= weight
                elif remaining > 0:
                    completion = round(remaining / weight * 100, 1)
                    remaining = 0.0
                else:
                    completion = 0.0
                done = completion >= 100
                tasks.append({
                    "task_id": task_id,
                    "milestone_id": milestone_id,
                    "title": title,
                    "weightage": weight,
                    "status": "done" if done else ("in_progress" if completion else "todo"),
                    "assignee_id": owner["user_id"],
                    "due_date": _iso(start + dt.timedelta(
                        days=int(duration * (order + 1) / len(titles)))),
                    "completed_at": _iso(_entry_date(start, ceiling, rng)) if done else None,
                    "order": order,
                    "created_at": _stamp(start),
                    "seed_tag": SEED_TAG,
                })
                if completion <= 0:
                    continue
                # Every point of progress is backed by an approved daily entry,
                # including on finished tasks — the entries are meant to be the
                # record progress is derived from, not a decoration on top of a
                # separately-invented number.
                for chunk in _split(completion, rng.randint(1, 3), rng):
                    entry_on = _entry_date(start, ceiling, rng)
                    entries.append({
                        "entry_id": uuid.uuid4().hex,
                        "milestone_id": milestone_id,
                        "task_id": task_id,
                        "user_id": owner["user_id"],
                        "date": _iso(entry_on),
                        "hours": round(rng.uniform(1, 8), 1),
                        "progress_delta": chunk,
                        "note": f"{title} — {chunk}% completed.",
                        "status": "approved",
                        "approver_id": _manager_for(owner, teams_by_id),
                        "approved_at": _stamp(entry_on),
                        "created_at": _stamp(entry_on),
                        "seed_tag": SEED_TAG,
                    })

            # A pending submission on some in-flight milestones, so the
            # approve/reject controls have something real to act on. Pending
            # entries contribute nothing to progress by design.
            if status in ("in_progress", "pending_review") and rng.random() < 0.35:
                entries.append({
                    "entry_id": uuid.uuid4().hex,
                    "milestone_id": milestone_id,
                    "task_id": None,
                    "user_id": owner["user_id"],
                    "date": _iso(today - dt.timedelta(days=rng.randint(0, 3))),
                    "hours": round(rng.uniform(1, 8), 1),
                    "progress_delta": round(rng.uniform(2, 12), 1),
                    "note": "Daily progress submitted for approval.",
                    "status": "pending",
                    "approver_id": None,
                    "approved_at": None,
                    "created_at": _stamp(today),
                    "seed_tag": SEED_TAG,
                })

            if rng.random() < 0.25:
                for body in rng.sample(_COMMENTS, k=rng.randint(1, 2)):
                    commented_on = _entry_date(start, ceiling, rng)
                    comments.append({
                        "comment_id": uuid.uuid4().hex,
                        "milestone_id": milestone_id,
                        "user_id": _manager_for(owner, teams_by_id) or owner["user_id"],
                        "body": body,
                        "created_at": _stamp(commented_on),
                        "seed_tag": SEED_TAG,
                    })

            activity.append({
                "event_id": uuid.uuid4().hex,
                "milestone_id": milestone_id,
                "actor_id": owner["user_id"],
                "type": "created",
                "detail": "Milestone created",
                "at": _stamp(start),
                "seed_tag": SEED_TAG,
            })
            if completed_on:
                activity.append({
                    "event_id": uuid.uuid4().hex,
                    "milestone_id": milestone_id,
                    "actor_id": owner["user_id"],
                    "type": "completed",
                    "detail": "Milestone completed",
                    "at": _stamp(completed_on),
                    "seed_tag": SEED_TAG,
                })

    # Dependencies: point at another milestone in the same department so the
    # Dependencies tab shows something the viewer is allowed to open.
    for milestone in milestones:
        siblings = all_ids_by_dept.get(milestone.get("department") or "", [])
        if len(siblings) > 3 and rng.random() < 0.18:
            picks = [m for m in rng.sample(siblings, k=min(2, len(siblings)))
                     if m != milestone["milestone_id"]]
            milestone["dependencies"] = picks

    db.tracker_milestones.insert_many(milestones)
    if tasks:
        db.milestone_tasks.insert_many(tasks)
    if entries:
        db.milestone_daily_entries.insert_many(entries)
    if comments:
        db.milestone_comments.insert_many(comments)
    if activity:
        db.milestone_activity.insert_many(activity)

    # Derive progress through the same `ProgressIndex.actual` the screens read,
    # but batched: calling `recompute()` per milestone would be four round
    # trips each, which is minutes against a remote Atlas cluster.
    index = svc.ProgressIndex(db, [m["milestone_id"] for m in milestones])
    updates = []
    for milestone in milestones:
        actual = index.actual(milestone)
        change: dict = {"progress_pct": actual}
        if actual >= 100 and milestone["status"] != "completed":
            change["status"] = "completed"
            change["completed_at"] = _iso(today)
        elif actual < 100 and milestone["status"] == "completed":
            change["status"] = "in_progress"
            change["completed_at"] = None
        updates.append(UpdateOne({"milestone_id": milestone["milestone_id"]},
                                 {"$set": change}))
    db.tracker_milestones.bulk_write(updates)

    return {"milestones": len(milestones), "tasks": len(tasks),
            "daily_entries": len(entries), "comments": len(comments)}
