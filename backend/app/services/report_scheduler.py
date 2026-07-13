"""Schedule math + background tick loop for automated report distribution.

`compute_next_run` is pure and used both by the `/schedule` endpoint (to set
the initial `next_run_at`) and by `tick` (to advance it after firing). It
always returns a time strictly after `now` — a schedule that was missed
(e.g. the process was asleep) fires once on the next tick and reschedules
from the current time, rather than replaying every missed occurrence.

`tick` is a plain, directly-testable function; `start`/`stop` wrap it in a
daemon thread. The thread never starts under pytest (three independent
guards below) so the test suite never races a background loop against its
own mongomock fixtures.
"""
from __future__ import annotations

import calendar
import datetime as dt
import logging
import sys
import threading

from pymongo.database import Database

from ..config import settings
from ..core import audit
from . import notifications as notif
from . import report_engine as engine
from . import reports as reports_svc

log = logging.getLogger("io.report_scheduler")
_thread: threading.Thread | None = None
_stop_event = threading.Event()


def compute_next_run(schedule: dict, now: dt.datetime | None = None) -> dt.datetime:
    now = now or dt.datetime.now(dt.timezone.utc)
    freq = schedule.get("frequency", "monthly")
    hh_str, mm_str = (schedule.get("time") or "09:00").split(":")
    hh, mm = int(hh_str), int(mm_str)

    def at_time(d: dt.date) -> dt.datetime:
        return dt.datetime(d.year, d.month, d.day, hh, mm, tzinfo=dt.timezone.utc)

    if freq == "daily":
        candidate = at_time(now.date())
        if candidate <= now:
            candidate += dt.timedelta(days=1)
        return candidate

    if freq == "weekly":
        weekday = schedule.get("weekday") or 0
        days_ahead = (weekday - now.weekday()) % 7
        candidate = at_time(now.date() + dt.timedelta(days=days_ahead))
        if candidate <= now:
            candidate = at_time(now.date() + dt.timedelta(days=days_ahead + 7))
        return candidate

    if freq in ("monthly", "quarterly", "yearly"):
        step = {"monthly": 1, "quarterly": 3, "yearly": 12}[freq]
        day = schedule.get("day_of_month") or 1
        y, m = now.year, now.month
        while True:
            last_day = calendar.monthrange(y, m)[1]
            candidate = at_time(dt.date(y, m, min(day, last_day)))
            if candidate > now:
                return candidate
            m += step
            while m > 12:
                m -= 12
                y += 1

    if freq == "custom":
        every = schedule.get("every_n_days") or 1
        candidate = at_time(now.date())
        while candidate <= now:
            candidate += dt.timedelta(days=every)
        return candidate

    return now + dt.timedelta(days=1)


def _aware(d: dt.datetime) -> dt.datetime:
    # Mongo (real or mongomock) round-trips datetimes as naive UTC.
    return d if d.tzinfo else d.replace(tzinfo=dt.timezone.utc)


def tick(db: Database, now: dt.datetime | None = None) -> list[dict]:
    """Fire every due, active schedule: generate a run, email/notify its
    recipients, and advance `next_run_at`. Whole-def try/except so one bad
    report def can't prevent the rest of the tick from firing. Returns the
    runs it created (used directly by tests; the background loop ignores it).
    """
    now = now or dt.datetime.now(dt.timezone.utc)
    fired: list[dict] = []
    for rd in db.report_defs.find({"schedule.active": True}):
        schedule = rd.get("schedule") or {}
        next_run = schedule.get("next_run_at")
        if not next_run or _aware(next_run) > now:
            continue
        try:
            owner = db.users.find_one({"user_id": rd["owner_id"]})
            if not owner:
                continue
            run = engine.run_report(db, rd, owner, triggered_by="schedule")
            html = engine.render_report_email_html(rd, run)
            recipients = schedule.get("recipients") or rd.get("recipients") or []
            result = reports_svc.send_email(f"{rd['name']} — Scheduled Report", html, recipients)
            for email in recipients:
                recipient = db.users.find_one({"email": email.lower()})
                if recipient:
                    notif.create(db, recipient_id=recipient["user_id"], type="report",
                                title=f"Scheduled report: {rd['name']}", body=result["detail"],
                                action_link="/reports")
            db.report_runs.update_one({"run_id": run["run_id"]}, {"$set": {
                "recipients": recipients,
                "delivery": {"status": result["status"], "detail": result["detail"]},
            }})
            audit.record(db, actor_id=rd["owner_id"], action="report_scheduled_run",
                        entity_type="report", entity_id=rd["report_id"], meta={"run_id": run["run_id"]})
            new_next = compute_next_run(schedule, now)
            db.report_defs.update_one({"report_id": rd["report_id"]}, {"$set": {
                "schedule.next_run_at": new_next, "schedule.last_run_at": now,
            }})
            fired.append(run)
        except Exception:  # noqa: BLE001 -- one bad schedule must not kill the tick
            log.exception("scheduled report run failed for %s", rd.get("report_id"))
    return fired


def start() -> None:
    """Start the background tick thread. No-ops under pytest or when
    `settings.scheduler_enabled` is off (see `tests/conftest.py`), so the
    test suite never races a live thread against its mongomock fixtures.
    """
    global _thread
    if "pytest" in sys.modules or not settings.scheduler_enabled:
        return
    if _thread and _thread.is_alive():
        return
    _stop_event.clear()

    def _loop() -> None:
        from ..db import get_db

        while not _stop_event.wait(settings.scheduler_interval_sec):
            try:
                tick(get_db())
            except Exception:  # noqa: BLE001 -- the loop must never die
                log.exception("report scheduler tick failed")

    _thread = threading.Thread(target=_loop, name="report-scheduler", daemon=True)
    _thread.start()


def stop() -> None:
    _stop_event.set()
