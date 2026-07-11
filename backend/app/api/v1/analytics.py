"""Org-wide analytics for L4 (super_admin/leadership) — actions/day trend,
action-type breakdown, most active users, activity by department, and
integration sync health. Reads audit_logs, which already captures both
domain events (task_created, request_approved, ...) and every mutating
API call (auto-logged by AuditMiddleware — see core/middleware.py).

Grouping happens in Python rather than a Mongo aggregation pipeline:
mongomock (used in tests) has limited $group support, and audit_logs
volume here is small enough that this is simpler either way.
"""
from __future__ import annotations

import datetime as dt
from collections import Counter

from fastapi import APIRouter, Depends
from pymongo.database import Database

from ..deps import get_db, require_role

router = APIRouter(tags=["analytics"])


@router.get("/analytics/summary")
def summary(days: int = 30,
           _: dict = Depends(require_role("super_admin", "leadership")),
           db: Database = Depends(get_db)) -> dict:
    since = dt.datetime.now(dt.timezone.utc) - dt.timedelta(days=days)
    rows = list(db.audit_logs.find({"created_at": {"$gte": since}}))

    per_day: Counter = Counter()
    by_action: Counter = Counter()
    by_actor: Counter = Counter()
    by_dept: Counter = Counter()
    for r in rows:
        created = r.get("created_at")
        if created:
            per_day[created.strftime("%Y-%m-%d")] += 1
        by_action[r.get("action", "unknown")] += 1
        actor = r.get("actor_id")
        if actor:
            by_actor[actor] += 1
        dept = (r.get("meta") or {}).get("department")
        if dept:
            by_dept[dept] += 1

    names = {u["user_id"]: u["name"] for u in db.users.find({}, {"user_id": 1, "name": 1})}

    integrations = []
    for source in db.integration_logs.distinct("source"):
        log = db.integration_logs.find_one({"source": source}, sort=[("run_at", -1)])
        if log:
            integrations.append({
                "source": source,
                "status": log.get("status"),
                "run_at": log.get("run_at"),
                "records_processed": log.get("records_processed"),
            })

    return {
        "window_days": days,
        "total_actions": len(rows),
        "actions_per_day": [{"date": d, "count": c} for d, c in sorted(per_day.items())],
        "by_action": [{"action": a, "count": c} for a, c in by_action.most_common(10)],
        "top_actors": [{"user_id": uid, "name": names.get(uid, uid), "count": c}
                      for uid, c in by_actor.most_common(10)],
        "by_department": [{"department": d, "count": c} for d, c in by_dept.most_common()],
        "integrations": integrations,
    }
