"""Report scheduler: date math (`compute_next_run`) and the tick loop that
fires due schedules, generates a run, and advances `next_run_at`."""
from __future__ import annotations

import datetime as dt

from app.services import report_scheduler


def test_compute_next_run_daily():
    now = dt.datetime(2026, 3, 10, 8, 0, tzinfo=dt.timezone.utc)
    future_today = report_scheduler.compute_next_run({"frequency": "daily", "time": "09:00"}, now)
    assert future_today == dt.datetime(2026, 3, 10, 9, 0, tzinfo=dt.timezone.utc)

    already_passed = report_scheduler.compute_next_run({"frequency": "daily", "time": "07:00"}, now)
    assert already_passed == dt.datetime(2026, 3, 11, 7, 0, tzinfo=dt.timezone.utc)


def test_compute_next_run_weekly_lands_on_requested_weekday():
    now = dt.datetime(2026, 3, 10, 8, 0, tzinfo=dt.timezone.utc)
    nxt = report_scheduler.compute_next_run({"frequency": "weekly", "time": "09:00", "weekday": 4}, now)
    assert nxt.weekday() == 4
    assert nxt > now


def test_compute_next_run_monthly_clamps_to_month_end():
    now = dt.datetime(2026, 1, 31, 10, 0, tzinfo=dt.timezone.utc)  # past 09:00 on the 31st
    nxt = report_scheduler.compute_next_run(
        {"frequency": "monthly", "time": "09:00", "day_of_month": 31}, now)
    assert nxt == dt.datetime(2026, 2, 28, 9, 0, tzinfo=dt.timezone.utc)  # Feb 2026 has 28 days


def test_compute_next_run_quarterly_yearly_custom_always_future():
    now = dt.datetime(2026, 3, 10, 8, 0, tzinfo=dt.timezone.utc)
    quarterly = report_scheduler.compute_next_run(
        {"frequency": "quarterly", "time": "09:00", "day_of_month": 1}, now)
    yearly = report_scheduler.compute_next_run(
        {"frequency": "yearly", "time": "09:00", "day_of_month": 1}, now)
    custom = report_scheduler.compute_next_run(
        {"frequency": "custom", "time": "09:00", "every_n_days": 3}, now)
    assert quarterly > now and quarterly.day == 1
    assert yearly > now and yearly.day == 1
    assert custom > now


def _set_due(db, report_id: str, now: dt.datetime) -> None:
    db.report_defs.update_one({"report_id": report_id}, {"$set": {
        "schedule": {"frequency": "daily", "time": "09:00", "recipients": [],
                    "active": True, "next_run_at": now - dt.timedelta(minutes=1), "last_run_at": None},
    }})


def test_tick_fires_due_schedule_and_advances_next_run(db):
    now = dt.datetime.now(dt.timezone.utc)
    _set_due(db, "rep_test_exec", now)
    runs_before = db.report_runs.count_documents({"report_id": "rep_test_exec"})

    fired = report_scheduler.tick(db, now)
    assert any(f["report_id"] == "rep_test_exec" for f in fired)
    assert db.report_runs.count_documents({"report_id": "rep_test_exec"}) == runs_before + 1

    rd = db.report_defs.find_one({"report_id": "rep_test_exec"})
    assert rd["schedule"]["next_run_at"].replace(tzinfo=dt.timezone.utc) > now
    assert rd["schedule"]["last_run_at"] is not None

    # Second tick at the same "now": schedule already advanced into the future, so it must not fire again.
    fired_again = report_scheduler.tick(db, now)
    assert not any(f["report_id"] == "rep_test_exec" for f in fired_again)


def test_tick_notifies_recipients_and_records_delivery(db):
    now = dt.datetime.now(dt.timezone.utc)
    db.report_defs.update_one({"report_id": "rep_test_exec"}, {"$set": {
        "schedule": {"frequency": "daily", "time": "09:00", "recipients": ["admin@flynava.ai"],
                    "active": True, "next_run_at": now - dt.timedelta(minutes=1), "last_run_at": None},
    }})
    fired = report_scheduler.tick(db, now)
    run = next(f for f in fired if f["report_id"] == "rep_test_exec")
    run_doc = db.report_runs.find_one({"run_id": run["run_id"]})
    assert run_doc["delivery"]["status"] in ("sent", "preview")
    notifs = list(db.notifications.find({"recipient_id": "u_ceo", "type": "report"}))
    assert notifs


def test_tick_one_malformed_def_does_not_block_others(db):
    now = dt.datetime.now(dt.timezone.utc)
    db.report_defs.insert_one({
        "report_id": "rep_broken", "name": "Broken", "description": "", "domain": "development",
        "project_id": None, "type": "summary", "sections": "not-a-list", "visibility": "org",
        "access": {"roles": [], "teams": []}, "confidential": False, "allowed_user_ids": [],
        "shared_with": [], "recipients": [], "owner_id": "u_harsha", "archived": False,
        "downloads": 0, "run_count": 0, "created_at": now, "updated_at": now, "seed": False,
        "schedule": {"frequency": "daily", "time": "09:00", "recipients": [], "active": True,
                    "next_run_at": now - dt.timedelta(minutes=1), "last_run_at": None},
    })
    _set_due(db, "rep_test_exec", now)

    fired = report_scheduler.tick(db, now)
    fired_ids = {f["report_id"] for f in fired}
    assert "rep_test_exec" in fired_ids
    assert "rep_broken" not in fired_ids


def test_scheduler_thread_never_starts_under_pytest():
    # settings.scheduler_enabled is forced False in conftest, and the
    # "pytest" in sys.modules guard is a second independent check.
    report_scheduler.start()
    assert report_scheduler._thread is None or not report_scheduler._thread.is_alive()
