"""Milestone Tracker: the progress formula, the RBAC scoping, and the routes.

The formula tests build their own tiny milestone rather than leaning on the
seed, so they assert exact numbers instead of "roughly what the demo data
happens to produce".
"""
from __future__ import annotations

import datetime as dt

import pytest

from app.services import milestones as svc

CEO = "admin@flynava.ai"
DEPT_HEAD = "harsha.varlani@flynava.ai"      # manager, department eng, L3
TEAM_LEAD = "mushaheed.khan@flynava.ai"      # team_lead, team_ui, L2
EMPLOYEE = "animesh.singh@flynava.ai"        # employee, team_ui, L1


def _today() -> dt.date:
    return dt.datetime.now(dt.timezone.utc).date()


def _make(db, milestone_id="MS-T1", *, owner="u_animesh", manager="u_mushaheed",
          department="eng", team="team_ui", start_offset=-10, due_offset=10,
          status="in_progress", **extra) -> dict:
    today = _today()
    doc = {
        "milestone_id": milestone_id, "name": "Test milestone", "description": "",
        "project_id": None, "department": department, "team_id": team,
        "owner_id": owner, "manager_id": manager, "category": "Delivery",
        "priority": "High", "status": status,
        "start_date": (today + dt.timedelta(days=start_offset)).isoformat(),
        "due_date": (today + dt.timedelta(days=due_offset)).isoformat(),
        "completed_at": None, "progress_pct": 0.0, "completion_criteria": [],
        "dependencies": [], "created_by": owner,
        "created_at": (today + dt.timedelta(days=start_offset)).isoformat(),
        "updated_at": today.isoformat(),
    }
    doc.update(extra)
    db.tracker_milestones.insert_one(dict(doc))
    return doc


def _task(db, milestone_id, task_id, weightage, status="todo", completed_at=None):
    db.milestone_tasks.insert_one({
        "task_id": task_id, "milestone_id": milestone_id, "title": task_id,
        "weightage": weightage, "status": status, "assignee_id": "u_animesh",
        "due_date": None, "completed_at": completed_at, "order": 0,
    })


def _entry(db, milestone_id, task_id, delta, status="approved", date=None,
           user_id="u_animesh"):
    db.milestone_daily_entries.insert_one({
        "entry_id": f"{task_id}-{delta}-{status}-{date}", "milestone_id": milestone_id,
        "task_id": task_id, "user_id": user_id,
        "date": (date or _today()).isoformat(), "hours": 4.0,
        "progress_delta": delta, "note": "", "status": status,
        "approver_id": None, "approved_at": None,
    })


# --------------------------------------------------------------------------
# the formula
# --------------------------------------------------------------------------
def test_progress_is_weightage_weighted(db):
    _make(db, "MS-W1")
    _task(db, "MS-W1", "t_big", 9, status="done", completed_at=_today().isoformat())
    _task(db, "MS-W1", "t_small", 1)
    # 9 of 10 weight complete -> 90%, not the 50% an unweighted count would give.
    assert svc.recompute(db, "MS-W1") == 90.0


def test_only_approved_entries_count(db):
    _make(db, "MS-A1")
    _task(db, "MS-A1", "t1", 1)
    _entry(db, "MS-A1", "t1", 40, status="approved")
    _entry(db, "MS-A1", "t1", 50, status="pending")
    _entry(db, "MS-A1", "t1", 30, status="rejected")
    assert svc.recompute(db, "MS-A1") == 40.0


def test_entry_deltas_accumulate_and_clamp(db):
    _make(db, "MS-A2")
    _task(db, "MS-A2", "t1", 1)
    _entry(db, "MS-A2", "t1", 60, date=_today() - dt.timedelta(days=2))
    _entry(db, "MS-A2", "t1", 70, date=_today() - dt.timedelta(days=1))
    # A task can't be more than finished.
    assert svc.recompute(db, "MS-A2") == 100.0


def test_reaching_100_completes_and_dropping_back_reopens(db):
    _make(db, "MS-C1")
    _task(db, "MS-C1", "t1", 1)
    _entry(db, "MS-C1", "t1", 100)
    svc.recompute(db, "MS-C1")
    assert db.tracker_milestones.find_one({"milestone_id": "MS-C1"})["status"] == "completed"

    db.milestone_daily_entries.update_many({"milestone_id": "MS-C1"},
                                           {"$set": {"status": "rejected"}})
    svc.recompute(db, "MS-C1")
    fresh = db.tracker_milestones.find_one({"milestone_id": "MS-C1"})
    assert fresh["status"] == "in_progress"
    assert fresh["completed_at"] is None


def test_planned_pct_tracks_elapsed_time(db):
    milestone = _make(db, "MS-P1", start_offset=-10, due_offset=10)
    assert svc.planned_pct(milestone) == 50.0


def test_health_bands_compare_actual_against_planned():
    assert svc.health_of(60, 50) == "good"
    assert svc.health_of(50, 50) == "good"
    assert svc.health_of(40, 50) == "needs_attention"      # 10 point gap
    assert svc.health_of(35, 50) == "needs_attention"      # exactly 15
    assert svc.health_of(30, 50) == "at_risk"              # past the gap


def test_delayed_is_the_gap_and_never_negative(db):
    milestone = _make(db, "MS-D1", start_offset=-10, due_offset=10)
    _task(db, "MS-D1", "t1", 1)
    _entry(db, "MS-D1", "t1", 20)
    svc.recompute(db, "MS-D1")
    row = svc.decorate(db.tracker_milestones.find_one({"milestone_id": "MS-D1"}, {"_id": 0}),
                       svc.ProgressIndex(db, ["MS-D1"]))
    assert row["planned_pct"] == 50.0
    assert row["actual_pct"] == 20.0
    assert row["delayed_pct"] == 30.0
    assert row["health"] == "at_risk"

    _entry(db, "MS-D1", "t1", 60, date=_today())
    svc.recompute(db, "MS-D1")
    ahead = svc.decorate(db.tracker_milestones.find_one({"milestone_id": "MS-D1"}, {"_id": 0}),
                         svc.ProgressIndex(db, ["MS-D1"]))
    assert ahead["delayed_pct"] == 0.0
    assert ahead["health"] == "good"


def test_overdue_ignores_completed_and_rewinds_with_as_of(db):
    yesterday = _today() - dt.timedelta(days=1)
    open_row = _make(db, "MS-O1", due_offset=-1)
    assert svc.is_overdue(open_row) is True

    done_row = _make(db, "MS-O2", due_offset=-5, status="completed",
                     completed_at=yesterday.isoformat())
    assert svc.is_overdue(done_row) is False
    # As of before it was finished, it *was* overdue — that's what makes the
    # month-over-month delta on the Overdue card honest.
    assert svc.is_overdue(done_row, _today() - dt.timedelta(days=3)) is True


def test_unweighted_tasks_fall_back_to_an_equal_split(db):
    _make(db, "MS-U1")
    _task(db, "MS-U1", "t1", 0, status="done", completed_at=_today().isoformat())
    _task(db, "MS-U1", "t2", 0)
    assert svc.recompute(db, "MS-U1") == 50.0


def test_milestone_level_entries_count_even_without_a_task(db):
    """The Daily Success form makes `task_id` optional, so an approved entry
    with no task has to move the number — otherwise approving it does nothing
    visible."""
    _make(db, "MS-L1")
    _entry(db, "MS-L1", None, 25)
    assert svc.recompute(db, "MS-L1") == 25.0

    # And it stacks on top of the weighted task progress rather than replacing it.
    _make(db, "MS-L2")
    _task(db, "MS-L2", "t1", 1)
    _entry(db, "MS-L2", "t1", 50)
    _entry(db, "MS-L2", None, 10)
    assert svc.recompute(db, "MS-L2") == 60.0


def test_milestone_with_no_tasks_keeps_its_recorded_progress(db):
    _make(db, "MS-N1", progress_pct=35.0)
    index = svc.ProgressIndex(db, ["MS-N1"])
    row = db.tracker_milestones.find_one({"milestone_id": "MS-N1"}, {"_id": 0})
    assert index.actual(row) == 35.0


# --------------------------------------------------------------------------
# scoping / permissions
# --------------------------------------------------------------------------
def test_scope_filter_narrows_by_level(db):
    ceo = db.users.find_one({"user_id": "u_ceo"})
    head = db.users.find_one({"user_id": "u_harsha"})
    lead = db.users.find_one({"user_id": "u_mushaheed"})
    employee = db.users.find_one({"user_id": "u_animesh"})

    assert svc.scope_filter(db, ceo) == {}
    assert svc.scope_filter(db, head) == {"department": "eng"}
    assert "$or" in svc.scope_filter(db, lead)
    assert svc.scope_filter(db, employee)["$or"] == [
        {"owner_id": "u_animesh"}, {"manager_id": "u_animesh"}]


def test_employee_cannot_view_another_departments_milestone(db):
    milestone = _make(db, "MS-S1", owner="u_ceo", manager="u_ceo",
                      department="exec", team=None)
    employee = db.users.find_one({"user_id": "u_animesh"})
    assert svc.can_view(db, employee, milestone) is False
    assert svc.can_view(db, db.users.find_one({"user_id": "u_ceo"}), milestone) is True


def test_self_approval_is_always_refused(db):
    milestone = _make(db, "MS-R1", manager="u_animesh")
    author = db.users.find_one({"user_id": "u_animesh"})
    assert svc.can_approve(author, milestone, {"user_id": "u_animesh"}) is False
    # The CEO outranks everyone, and still can't approve their own entry.
    ceo = db.users.find_one({"user_id": "u_ceo"})
    assert svc.can_approve(ceo, milestone, {"user_id": "u_ceo"}) is False
    assert svc.can_approve(ceo, milestone, {"user_id": "u_animesh"}) is True


# --------------------------------------------------------------------------
# routes
# --------------------------------------------------------------------------
def test_dashboard_shape(client, auth_header):
    r = client.get("/api/v1/milestones/dashboard", headers=auth_header(CEO))
    assert r.status_code == 200
    body = r.json()
    assert {"cards", "status_donut", "trend", "departments", "top_performers",
            "needs_attention", "upcoming_deadlines", "org_health",
            "totals", "generated_at"} <= set(body)
    assert len(body["cards"]) == 6
    assert body["trend"]["points"]
    assert body["departments"]


def test_status_slices_sum_to_the_donut_total(client, auth_header):
    body = client.get("/api/v1/milestones/dashboard", headers=auth_header(CEO)).json()
    donut = body["status_donut"]
    assert sum(s["value"] for s in donut["slices"]) == donut["total"]
    assert donut["total"] == body["totals"]["all"]


def test_org_health_score_is_in_range(client, auth_header):
    health = client.get("/api/v1/milestones/dashboard", headers=auth_header(CEO)).json()["org_health"]
    assert 0 <= health["score"] <= 100
    assert health["band"] in {"Excellent", "Good", "Needs Attention", "At Risk", "No Data"}


def test_employee_is_refused_the_aggregate_dashboard(client, auth_header):
    r = client.get("/api/v1/milestones/dashboard", headers=auth_header(EMPLOYEE))
    assert r.status_code == 403


def test_department_head_sees_only_their_department(client, auth_header):
    body = client.get("/api/v1/milestones?page_size=200",
                      headers=auth_header(DEPT_HEAD)).json()
    assert body["items"]
    assert {row["department"] for row in body["items"]} == {"eng"}


def test_employee_list_is_limited_to_their_own_rows(client, auth_header):
    body = client.get("/api/v1/milestones?page_size=200",
                      headers=auth_header(EMPLOYEE)).json()
    for row in body["items"]:
        assert "u_animesh" in (row["owner_id"], row["manager_id"])


def test_list_pagination_and_filtering(client, auth_header):
    first = client.get("/api/v1/milestones?page=1&page_size=5",
                       headers=auth_header(CEO)).json()
    assert len(first["items"]) == 5
    assert first["total"] > 5
    second = client.get("/api/v1/milestones?page=2&page_size=5",
                        headers=auth_header(CEO)).json()
    assert {r["milestone_id"] for r in first["items"]} & {
        r["milestone_id"] for r in second["items"]} == set()

    filtered = client.get("/api/v1/milestones?status=completed&page_size=200",
                          headers=auth_header(CEO)).json()
    assert filtered["items"]
    assert {r["status"] for r in filtered["items"]} == {"completed"}


def test_health_filter_applies_to_the_derived_value(client, auth_header):
    """`health` is computed per read, never stored — so this filter can't be a
    plain Mongo clause and has to survive the decorate step."""
    body = client.get("/api/v1/milestones?health=at_risk&page_size=200",
                      headers=auth_header(CEO)).json()
    assert body["items"], "seed data should contain at-risk milestones"
    assert {r["health"] for r in body["items"]} == {"at_risk"}


def test_literal_paths_are_not_swallowed_by_the_id_route(client, auth_header):
    """`/milestones/export` and friends are declared before
    `/milestones/{milestone_id}`; if that ever flips they 404."""
    header = auth_header(CEO)
    export = client.get("/api/v1/milestones/export", headers=header)
    assert export.status_code == 200
    assert export.headers["content-type"].startswith("text/csv")
    assert export.text.splitlines()[0].startswith("ID,Milestone Name")

    for path in ("/api/v1/milestones/filters", "/api/v1/milestones/reports",
                 "/api/v1/milestones/departments"):
        assert client.get(path, headers=header).status_code == 200


def test_detail_payload_has_every_tab(client, auth_header):
    header = auth_header(CEO)
    milestone_id = client.get("/api/v1/milestones?page_size=1",
                              headers=header).json()["items"][0]["milestone_id"]
    body = client.get(f"/api/v1/milestones/{milestone_id}", headers=header).json()
    assert {"milestone", "tasks", "daily_entries", "dependencies", "documents",
            "comments", "timeline", "trend", "permissions", "counts"} <= set(body)
    assert body["counts"]["tasks"] == len(body["tasks"])


def test_unknown_milestone_404s(client, auth_header):
    r = client.get("/api/v1/milestones/MS-NOPE", headers=auth_header(CEO))
    assert r.status_code == 404


def test_create_update_delete_round_trip(client, auth_header):
    header = auth_header(CEO)
    today = _today()
    created = client.post("/api/v1/milestones", headers=header, json={
        "name": "Round trip", "department": "eng", "priority": "High",
        "start_date": today.isoformat(),
        "due_date": (today + dt.timedelta(days=30)).isoformat(),
    })
    assert created.status_code == 201
    milestone_id = created.json()["milestone_id"]
    assert milestone_id.startswith("MS-")

    patched = client.patch(f"/api/v1/milestones/{milestone_id}", headers=header,
                           json={"priority": "Low", "status": "in_progress"})
    assert patched.status_code == 200
    assert patched.json()["priority"] == "Low"

    assert client.delete(f"/api/v1/milestones/{milestone_id}",
                         headers=header).status_code == 204
    assert client.get(f"/api/v1/milestones/{milestone_id}",
                      headers=header).status_code == 404


def test_deleting_a_milestone_clears_its_children(client, auth_header, db):
    header = auth_header(CEO)
    today = _today()
    milestone_id = client.post("/api/v1/milestones", headers=header, json={
        "name": "With children", "department": "eng",
        "start_date": today.isoformat(),
        "due_date": (today + dt.timedelta(days=30)).isoformat(),
    }).json()["milestone_id"]
    client.post(f"/api/v1/milestones/{milestone_id}/tasks", headers=header,
                json={"title": "Build", "weightage": 3})
    client.post(f"/api/v1/milestones/{milestone_id}/comments", headers=header,
                json={"body": "note"})

    client.delete(f"/api/v1/milestones/{milestone_id}", headers=header)
    assert db.milestone_tasks.count_documents({"milestone_id": milestone_id}) == 0
    assert db.milestone_comments.count_documents({"milestone_id": milestone_id}) == 0


def test_daily_entry_only_moves_progress_once_approved(client, auth_header):
    header = auth_header(CEO)
    today = _today()
    milestone_id = client.post("/api/v1/milestones", headers=header, json={
        "name": "Approval flow", "department": "eng", "owner_id": "u_animesh",
        "manager_id": "u_ceo",
        "start_date": today.isoformat(),
        "due_date": (today + dt.timedelta(days=30)).isoformat(),
    }).json()["milestone_id"]
    task_id = client.post(f"/api/v1/milestones/{milestone_id}/tasks", headers=header,
                          json={"title": "Build", "weightage": 1}).json()["task_id"]

    entry = client.post(f"/api/v1/milestones/{milestone_id}/daily", headers=header,
                        json={"task_id": task_id, "progress_delta": 40}).json()
    assert entry["status"] == "pending"
    detail = client.get(f"/api/v1/milestones/{milestone_id}", headers=header).json()
    assert detail["milestone"]["progress_pct"] == 0.0

    # The CEO logged it, so the CEO cannot approve it.
    refused = client.post(
        f"/api/v1/milestones/{milestone_id}/daily/{entry['entry_id']}/approve",
        headers=header)
    assert refused.status_code == 403

    approved = client.post(
        f"/api/v1/milestones/{milestone_id}/daily/{entry['entry_id']}/approve",
        headers=auth_header(DEPT_HEAD))
    assert approved.status_code == 200
    detail = client.get(f"/api/v1/milestones/{milestone_id}", headers=header).json()
    assert detail["milestone"]["progress_pct"] == 40.0


def test_employee_view_is_self_or_authorised(client, auth_header):
    assert client.get("/api/v1/milestones/employees/u_animesh",
                      headers=auth_header(EMPLOYEE)).status_code == 200
    assert client.get("/api/v1/milestones/employees/u_ceo",
                      headers=auth_header(EMPLOYEE)).status_code == 403
    assert client.get("/api/v1/milestones/employees/u_animesh",
                      headers=auth_header(CEO)).status_code == 200


def test_employee_view_stats_add_up(client, auth_header):
    body = client.get("/api/v1/milestones/employees/u_animesh",
                      headers=auth_header(CEO)).json()
    stats = body["stats"]
    assert stats["total"] == len(body["active"]) + len(body["completed"])
    assert stats["completed"] == len(body["completed"])


def test_department_view_requires_dept_head_and_matching_department(client, auth_header):
    assert client.get("/api/v1/milestones/departments/eng",
                      headers=auth_header(DEPT_HEAD)).status_code == 200
    assert client.get("/api/v1/milestones/departments/fin",
                      headers=auth_header(DEPT_HEAD)).status_code == 403
    assert client.get("/api/v1/milestones/departments/fin",
                      headers=auth_header(CEO)).status_code == 200
    assert client.get("/api/v1/milestones/departments/eng",
                      headers=auth_header(TEAM_LEAD)).status_code == 403


def test_department_view_only_contains_that_department(client, auth_header):
    body = client.get("/api/v1/milestones/departments/eng",
                      headers=auth_header(CEO)).json()
    assert body["department"]["dept_id"] == "eng"
    assert sum(s["value"] for s in body["priority_donut"]["slices"]) == body["stats"]["total"]


@pytest.mark.parametrize("key", [
    "milestone_status", "employee_performance", "department_performance",
    "overdue_milestones", "milestone_progress", "upcoming_deadlines",
])
def test_every_predefined_report_runs(client, auth_header, key):
    r = client.get(f"/api/v1/milestones/reports/{key}", headers=auth_header(CEO))
    assert r.status_code == 200
    body = r.json()
    assert body["columns"]
    assert body["row_count"] == len(body["rows"])
    if body["rows"]:
        assert set(body["rows"][0]) == {c["key"] for c in body["columns"]}


def test_report_csv_export(client, auth_header):
    r = client.get("/api/v1/milestones/reports/overdue_milestones?format=csv",
                   headers=auth_header(CEO))
    assert r.status_code == 200
    assert r.headers["content-type"].startswith("text/csv")


def test_unknown_report_404s(client, auth_header):
    assert client.get("/api/v1/milestones/reports/nope",
                      headers=auth_header(CEO)).status_code == 404


def test_custom_report_groups(client, auth_header):
    r = client.post("/api/v1/milestones/reports/custom", headers=auth_header(CEO),
                    json={"columns": ["milestone_id", "name"], "group_by": "department_name"})
    assert r.status_code == 200
    body = r.json()
    assert {c["key"] for c in body["columns"]} == {"group", "count", "completed",
                                                   "overdue", "avg_progress"}
    assert body["rows"]


def test_dependencies_drop_self_and_unknown_ids(client, auth_header, db):
    header = auth_header(CEO)
    ids = [r["milestone_id"] for r in client.get(
        "/api/v1/milestones?page_size=2", headers=header).json()["items"]]
    target, other = ids[0], ids[1]
    r = client.put(f"/api/v1/milestones/{target}/dependencies", headers=header,
                   json={"dependencies": [other, target, "MS-GHOST"]})
    assert r.status_code == 200
    assert r.json()["dependencies"] == [other]
