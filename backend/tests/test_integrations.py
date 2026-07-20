import httpx
import respx

from app.config import settings
from app.integrations.openproject import OpenProjectConnector
from app.services.ingest import run_connector

BASE = "https://op.test"

PROJECTS = {
    "_embedded": {"elements": [
        {"id": 1, "name": "Apollo", "active": True},
        {"id": 2, "name": "Archived One", "active": False},
    ]}
}
WORK_PACKAGES = {
    "_embedded": {"elements": [
        {"id": 10, "subject": "Build API", "percentageDone": 40, "dueDate": "2026-08-01",
         "_links": {"status": {"title": "In progress"},
                    "assignee": {"title": "Mia"},
                    "project": {"href": "/api/v3/projects/1"}}},
        {"id": 11, "subject": "Write tests", "percentageDone": 100, "dueDate": None,
         "_links": {"status": {"title": "Closed"},
                    "project": {"href": "/api/v3/projects/1"}}},
    ]}
}


def _mock_op():
    respx.get(f"{BASE}/api/v3/projects").mock(
        return_value=httpx.Response(200, json=PROJECTS))
    respx.get(f"{BASE}/api/v3/work_packages").mock(
        return_value=httpx.Response(200, json=WORK_PACKAGES))


@respx.mock
def test_openproject_fetch_and_normalize():
    _mock_op()
    conn = OpenProjectConnector(base_url=BASE, api_key="tok")
    data = conn.fetch()
    assert len(data["projects"]) == 2
    assert data["projects"][1]["status"] == "archived"
    task = data["tasks"][0]
    assert task["source_id"] == "10"
    assert task["progress"] == 40
    assert task["project_source_id"] == "1"
    assert task["assignee"] == "Mia"
    # missing assignee handled
    assert data["tasks"][1]["assignee"] is None


@respx.mock
def test_run_connector_upserts_and_logs(db):
    _mock_op()
    conn = OpenProjectConnector(base_url=BASE, api_key="tok")
    log = run_connector(db, conn)
    assert log["status"] == "ok"
    assert log["records_processed"] == 4  # 2 projects + 2 tasks
    assert db.projects.count_documents({"source_system": "openproject"}) == 2
    assert db.tasks.count_documents({"source_system": "openproject"}) == 2
    assert db.integration_logs.count_documents({"source": "openproject"}) == 1


@respx.mock
def test_run_connector_is_idempotent(db):
    _mock_op()
    conn = OpenProjectConnector(base_url=BASE, api_key="tok")
    run_connector(db, conn)
    run_connector(db, conn)
    assert db.projects.count_documents({"source_system": "openproject"}) == 2  # no dupes


def test_missing_api_key_logs_error_without_crashing(db):
    conn = OpenProjectConnector(base_url=BASE, api_key="")
    log = run_connector(db, conn)
    assert log["status"] == "error"
    assert log["errors"]
    assert db.integration_logs.count_documents({"status": "error"}) == 1


def test_sync_endpoint_requires_super_admin(client, auth_header):
    denied = client.post("/api/v1/integrations/openproject/sync",
                         headers=auth_header("harsha.varlani@flynava.ai"))
    assert denied.status_code == 403


def test_sync_unknown_source_404(client, auth_header):
    r = client.post("/api/v1/integrations/nope/sync",
                    headers=auth_header("admin@flynava.ai"))
    assert r.status_code == 404


def _task(status: str) -> dict:
    return {"source_id": "99", "title": "Track me", "status": status, "progress": 0,
            "due_date": None, "wp_type": "Bug", "priority": "High",
            "assignee": None, "author": None, "project_source_id": None}


def test_status_transition_tracked_on_change(db):
    conn = OpenProjectConnector(base_url=BASE, api_key="tok")

    conn.upsert(db, {"projects": [], "tasks": [_task("Open")]})
    doc = db.tasks.find_one({"source_system": "openproject", "source_id": "99"})
    assert "status_history" not in doc  # first-ever sync: nothing to transition from

    conn.upsert(db, {"projects": [], "tasks": [_task("Reopen")]})
    doc = db.tasks.find_one({"source_system": "openproject", "source_id": "99"})
    assert len(doc["status_history"]) == 1
    assert doc["status_history"][0] == {"from": "Open", "to": "Reopen",
                                        "at": doc["status_history"][0]["at"]}
    assert doc["reopen_count"] == 1

    # unchanged status on the next sync -> no new history entry, no double count
    conn.upsert(db, {"projects": [], "tasks": [_task("Reopen")]})
    doc = db.tasks.find_one({"source_system": "openproject", "source_id": "99"})
    assert len(doc["status_history"]) == 1
    assert doc["reopen_count"] == 1

    # a further transition away from Reopen doesn't touch reopen_count
    conn.upsert(db, {"projects": [], "tasks": [_task("Closed")]})
    doc = db.tasks.find_one({"source_system": "openproject", "source_id": "99"})
    assert len(doc["status_history"]) == 2
    assert doc["reopen_count"] == 1


# --- Comment/journal ingestion (Activity API) ---
# Sample below mirrors the REAL op.flynava.ai response for work package #6973
# (captured 2026-07-19): a bug that went New -> Developed -> Retest -> Closed
# -> Developed — i.e. reopened by landing back on "Developed", not a status
# literally named "Reopen". `_links.user` is href-only (no embedded title),
# which is why a separate /api/v3/users/{id} lookup is required.
JOURNAL_WP = {
    "id": 20, "subject": "Track journal bug", "percentageDone": 0, "dueDate": None,
    "createdAt": "2025-09-18T06:43:46Z", "updatedAt": "2025-11-14T09:39:59Z",
    "_links": {"status": {"title": "Developed"}, "type": {"title": "Bug"},
              "project": {"href": "/api/v3/projects/1"}},
}
ACTIVITIES_REOPENED = {"_embedded": {"elements": [
    {"id": 1, "createdAt": "2025-09-18T06:43:46Z", "comment": {"raw": ""},
     "details": [{"raw": "Status set to New"}], "_links": {"user": {"href": "/api/v3/users/130"}}},
    {"id": 2, "createdAt": "2025-11-07T09:33:35Z", "comment": {"raw": ""},
     "details": [{"raw": "Status changed from New \nto Developed"}],
     "_links": {"user": {"href": "/api/v3/users/130"}}},
    {"id": 3, "createdAt": "2025-11-07T12:28:28Z", "comment": {"raw": ""},
     "details": [{"raw": "Status changed from Developed \nto Retest"}],
     "_links": {"user": {"href": "/api/v3/users/130"}}},
    {"id": 4, "createdAt": "2025-11-09T16:09:04Z",
     "comment": {"raw": "Verified in staging, looks good."},
     "details": [{"raw": "Status changed from Retest \nto Closed"}],
     "_links": {"user": {"href": "/api/v3/users/14"}}},
    {"id": 5, "createdAt": "2025-11-14T09:39:59Z", "comment": {"raw": ""},
     "details": [{"raw": "Status changed from Closed \nto Developed"}],
     "_links": {"user": {"href": "/api/v3/users/130"}}},
]}}
USERS = {130: "Anjitha Muthukumar", 14: "Alice Reviewer"}


def _mock_journal_wp(wp_id: int = 20, activities: dict = ACTIVITIES_REOPENED,
                     users: dict = USERS) -> None:
    respx.get(f"{BASE}/api/v3/projects").mock(
        return_value=httpx.Response(200, json=PROJECTS))
    respx.get(f"{BASE}/api/v3/work_packages").mock(
        return_value=httpx.Response(200, json={"_embedded": {"elements": [JOURNAL_WP]}}))
    respx.get(f"{BASE}/api/v3/work_packages/{wp_id}/activities").mock(
        return_value=httpx.Response(200, json=activities))
    for uid, name in users.items():
        respx.get(f"{BASE}/api/v3/users/{uid}").mock(
            return_value=httpx.Response(200, json={"name": name}))


@respx.mock
def test_journal_sync_derives_status_history_and_journal_grounded_reopen(db):
    _mock_journal_wp()
    conn = OpenProjectConnector(base_url=BASE, api_key="tok")
    run_connector(db, conn)

    doc = db.tasks.find_one({"source_system": "openproject", "source_id": "20"})
    assert doc["journal_synced_updated_at"] == "2025-11-14T09:39:59Z"
    assert len(doc["status_history"]) == 5
    # Closed -> Developed is a real reopen even though "Developed" isn't
    # literally named "Reopen" — this is exactly what sync-diffing alone
    # would have missed (only the literal-name check).
    assert doc["reopen_count"] == 1
    # closed_at/closed_by reflect the LATEST transition into a terminal
    # status (Retest -> Closed), regardless of the later reopen.
    assert doc["closed_at"] == "2025-11-09T16:09:04Z"
    assert doc["closed_by"] == "Alice Reviewer"


@respx.mock
def test_journal_sync_resolves_and_caches_activity_users(db):
    _mock_journal_wp()
    conn = OpenProjectConnector(base_url=BASE, api_key="tok")
    run_connector(db, conn)

    doc = db.tasks.find_one({"source_system": "openproject", "source_id": "20"})
    # 4 of the 5 activities are by user 130 (Anjitha) -> only ONE HTTP call
    # to /api/v3/users/130 despite appearing 4 times (cached across the run).
    assert doc["status_history"][0]["by"] == "Anjitha Muthukumar"
    calls_to_user_130 = [c for c in respx.calls if "/users/130" in str(c.request.url)]
    assert len(calls_to_user_130) == 1


@respx.mock
def test_journal_sync_records_comments_for_rag(db):
    _mock_journal_wp()
    conn = OpenProjectConnector(base_url=BASE, api_key="tok")
    run_connector(db, conn)

    rows = list(db.task_journals.find({"wp_source_id": "20"}))
    assert len(rows) == 1  # only activity #4 has a non-empty comment
    assert rows[0]["kind"] == "comment"
    assert rows[0]["comment"] == "Verified in staging, looks good."
    assert rows[0]["user"] == "Alice Reviewer"
    assert rows[0]["source_id"] == "20:4"


@respx.mock
def test_journal_sync_is_incremental_across_runs(db):
    _mock_journal_wp()
    conn = OpenProjectConnector(base_url=BASE, api_key="tok")
    run_connector(db, conn)
    activities_calls_after_first = len(
        [c for c in respx.calls if "/activities" in str(c.request.url)])
    assert activities_calls_after_first == 1

    # second sync, work package unchanged (same updatedAt) -> no re-fetch
    run_connector(db, conn)
    activities_calls_after_second = len(
        [c for c in respx.calls if "/activities" in str(c.request.url)])
    assert activities_calls_after_second == 1  # unchanged


@respx.mock
def test_journal_fetch_failure_for_one_wp_does_not_fail_sync(db):
    respx.get(f"{BASE}/api/v3/projects").mock(
        return_value=httpx.Response(200, json=PROJECTS))
    respx.get(f"{BASE}/api/v3/work_packages").mock(
        return_value=httpx.Response(200, json={"_embedded": {"elements": [JOURNAL_WP]}}))
    respx.get(f"{BASE}/api/v3/work_packages/20/activities").mock(
        return_value=httpx.Response(500))

    conn = OpenProjectConnector(base_url=BASE, api_key="tok")
    log = run_connector(db, conn)
    assert log["status"] == "ok"  # the core sync still succeeds
    doc = db.tasks.find_one({"source_system": "openproject", "source_id": "20"})
    assert doc is not None
    assert "journal_synced_updated_at" not in doc  # journal enrichment just didn't happen


@respx.mock
def test_journal_batch_cap_limits_work_packages_per_sync(db, monkeypatch):
    monkeypatch.setattr(settings, "openproject_journal_batch", 0)
    _mock_journal_wp()
    conn = OpenProjectConnector(base_url=BASE, api_key="tok")
    run_connector(db, conn)

    activities_calls = [c for c in respx.calls if "/activities" in str(c.request.url)]
    assert len(activities_calls) == 0
    doc = db.tasks.find_one({"source_system": "openproject", "source_id": "20"})
    assert "journal_synced_updated_at" not in doc
