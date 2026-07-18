"""HR problem-statement detectors.

Data sources: `attendance` (biometric ERP — name-based join, matching the
convention used across `services/hr.py`/`services/tasks.py`), `leaves`,
`employees`.
"""
from __future__ import annotations

import datetime as dt
from collections import Counter, defaultdict

from pymongo.database import Database

from .engine import detector

LATE_STREAK_HIGH = 3
REPEAT_LATE_THRESHOLD = 3
REPEAT_ABSENT_THRESHOLD = 2


@detector("hr_late_comers", "hr", "Repeat late arrivals")
def _late_comers(db: Database, project: str | None = None) -> dict | None:
    cutoff = (dt.date.today() - dt.timedelta(days=30)).isoformat()
    rows = list(db.attendance.find({"date": {"$gte": cutoff}}, {"name": 1, "date": 1, "status": 1}))
    if not rows:
        return None

    by_name: dict[str, list[dict]] = defaultdict(list)
    for r in rows:
        by_name[r["name"]].append(r)

    late_counts: dict[str, int] = {}
    streaks: dict[str, int] = {}
    weekday_counts: Counter = Counter()
    for name, recs in by_name.items():
        recs_sorted = sorted(recs, key=lambda r: r["date"])
        lates = [r for r in recs_sorted if r["status"] == "Late"]
        if not lates:
            continue
        late_counts[name] = len(lates)
        for r in lates:
            try:
                weekday_counts[dt.date.fromisoformat(r["date"]).strftime("%A")] += 1
            except ValueError:
                pass
        streak = 0
        for r in reversed(recs_sorted):
            if r["status"] != "Late":
                break
            streak += 1
        streaks[name] = streak

    repeat = {n: c for n, c in late_counts.items() if c >= REPEAT_LATE_THRESHOLD}
    if not repeat:
        return None
    worst_day = weekday_counts.most_common(1)[0][0] if weekday_counts else None
    ranked = sorted(repeat.items(), key=lambda kv: -kv[1])
    top_name, top_count = ranked[0]

    problem = f"{top_name} has been late {top_count} time(s) in the last 30 days"
    if streaks.get(top_name, 0) >= 2:
        problem += f", currently on a {streaks[top_name]}-day late streak"
    problem += "."
    if len(ranked) > 1:
        problem += f" {len(ranked)} employee(s) have {REPEAT_LATE_THRESHOLD}+ late arrivals this period."

    metrics = [{"label": "Repeat late arrivals (3+/30d)", "value": len(ranked), "unit": ""},
              {"label": f"{top_name}'s lates", "value": top_count, "unit": ""}]
    if worst_day:
        metrics.append({"label": "Most common late weekday", "value": worst_day, "unit": ""})

    return {
        "severity": "high" if streaks.get(top_name, 0) >= LATE_STREAK_HIGH else "medium",
        "problem": problem,
        "metrics": metrics,
        "entities": [{"kind": "person", "id": n, "label": n,
                      "extra": {"lates": c, "streak": streaks.get(n, 0)}} for n, c in ranked[:8]],
        "evidence": [f"{n} — {c} late day(s), current streak {streaks.get(n, 0)}" for n, c in ranked[:8]],
        "chart": {"kind": "bars", "points": [{"label": n, "value": c} for n, c in ranked[:5]]},
        "action_hint": f"Have {top_name}'s manager follow up on the pattern.",
    }


@detector("hr_absenteeism", "hr", "Absenteeism concentration")
def _absenteeism(db: Database, project: str | None = None) -> dict | None:
    cutoff = (dt.date.today() - dt.timedelta(days=30)).isoformat()
    rows = list(db.attendance.find({"date": {"$gte": cutoff}}, {"name": 1, "status": 1}))
    if not rows:
        return None

    emp_dept = {e["name"]: e.get("department") for e in
               db.employees.find({}, {"name": 1, "department": 1})}
    total_by_dept: Counter = Counter()
    absent_by_dept: Counter = Counter()
    absent_by_person: Counter = Counter()
    for r in rows:
        dept = emp_dept.get(r["name"], "unknown")
        total_by_dept[dept] += 1
        if r["status"] == "Absent":
            absent_by_dept[dept] += 1
            absent_by_person[r["name"]] += 1

    overall_rate = sum(absent_by_dept.values()) / len(rows)
    dept_rates = {d: absent_by_dept[d] / total_by_dept[d] for d in total_by_dept if total_by_dept[d] > 0}
    flagged_depts = {d: r for d, r in dept_rates.items()
                     if r > overall_rate * 1.5 and absent_by_dept[d] >= 2}
    repeat_people = {n: c for n, c in absent_by_person.items() if c >= REPEAT_ABSENT_THRESHOLD}
    if not flagged_depts and not repeat_people:
        return None

    lines = []
    if flagged_depts:
        worst_dept = max(flagged_depts, key=flagged_depts.get)
        lines.append(f"{worst_dept} department's absence rate is {flagged_depts[worst_dept] * 100:.0f}% "
                    f"vs a {overall_rate * 100:.0f}% company average.")
    if repeat_people:
        top_person = max(repeat_people, key=repeat_people.get)
        lines.append(f"{top_person} has been absent {repeat_people[top_person]} time(s) in the last 30 days.")

    metrics = [{"label": "Company absence rate", "value": round(overall_rate * 100, 1), "unit": "%"}]
    metrics += [{"label": f"{d} absence rate", "value": round(r * 100, 1), "unit": "%"}
               for d, r in flagged_depts.items()]

    return {
        "severity": "high" if repeat_people and max(repeat_people.values()) >= 4 else "medium",
        "problem": " ".join(lines),
        "metrics": metrics,
        "entities": [{"kind": "person", "id": n, "label": n, "extra": {"absences": c}}
                     for n, c in repeat_people.items()],
        "evidence": ([f"{d} dept — {absent_by_dept[d]} absence(s) / {total_by_dept[d]} record(s)"
                     for d in flagged_depts]
                    + [f"{n} — {c} absence(s) in 30 days"
                       for n, c in sorted(repeat_people.items(), key=lambda kv: -kv[1])[:5]]),
        "chart": {"kind": "bars", "points": [{"label": d, "value": round(r * 100, 1)}
                                             for d, r in flagged_depts.items()]},
        "action_hint": "HR to check in with repeat-absence employees and flagged departments.",
    }


@detector("hr_leave_collision", "hr", "Overlapping leave creates capacity risk")
def _leave_collision(db: Database, project: str | None = None) -> dict | None:
    leaves = list(db.leaves.find({"status": "Approved"}))
    if len(leaves) < 2:
        return None

    emp_dept = {e["emp_id"]: e.get("department") for e in db.employees.find({}, {"emp_id": 1, "department": 1})}
    emp_name = {e["emp_id"]: e.get("name") for e in db.employees.find({}, {"emp_id": 1, "name": 1})}
    dept_headcount = Counter(e.get("department") for e in db.employees.find({}, {"department": 1}))

    by_dept: dict[str, list[dict]] = defaultdict(list)
    for lv in leaves:
        by_dept[emp_dept.get(lv["emp_id"], "unknown")].append(lv)

    def _range(lv: dict) -> tuple[dt.date, dt.date] | None:
        try:
            return (dt.date.fromisoformat(str(lv["from"])[:10]),
                    dt.date.fromisoformat(str(lv["to"])[:10]))
        except (ValueError, KeyError):
            return None

    collisions = []
    for dept, lvs in by_dept.items():
        overlapping: set[str] = set()
        for i in range(len(lvs)):
            a = _range(lvs[i])
            if not a:
                continue
            for j in range(i + 1, len(lvs)):
                b = _range(lvs[j])
                if not b:
                    continue
                if a[0] <= b[1] and b[0] <= a[1]:
                    overlapping.add(lvs[i]["emp_id"])
                    overlapping.add(lvs[j]["emp_id"])
        if len(overlapping) >= 2:
            headcount = dept_headcount.get(dept, 0)
            pct = round(len(overlapping) / headcount * 100, 1) if headcount else None
            collisions.append((dept, overlapping, pct))

    if not collisions:
        return None
    collisions.sort(key=lambda c: -(c[2] or 0))
    top_dept, top_people, top_pct = collisions[0]
    names = [emp_name.get(eid, eid) for eid in top_people]

    problem = (f"{len(top_people)} people in {top_dept} have overlapping approved leave"
              + (f" ({top_pct}% of the department)" if top_pct else "") + f": {', '.join(names[:5])}.")

    return {
        "severity": "high" if top_pct and top_pct >= 30 else "medium",
        "problem": problem,
        "metrics": [{"label": "Departments with leave collisions", "value": len(collisions), "unit": ""},
                    {"label": f"{top_dept} overlapping people", "value": len(top_people), "unit": ""}],
        "entities": [{"kind": "person", "id": eid, "label": emp_name.get(eid, eid),
                      "extra": {"department": top_dept}} for eid in list(top_people)[:8]],
        "evidence": [f"{dept}: {len(people)} overlapping — "
                    f"{', '.join(emp_name.get(e, e) for e in list(people)[:5])}"
                    for dept, people, _ in collisions[:8]],
        "chart": None,
        "action_hint": f"Confirm {top_dept} has coverage during the overlapping leave window.",
    }
