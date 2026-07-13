"""Schedule math + background tick loop for automated report distribution.

`compute_next_run` is pure and used both by the `/schedule` endpoint (to set
the initial `next_run_at`) and by `tick` (to advance it after firing). It
always returns a time strictly after `now` — a schedule that was missed
(e.g. the process was asleep) fires once on the next tick and reschedules
from the current time, rather than replaying every missed occurrence.
"""
from __future__ import annotations

import calendar
import datetime as dt


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
