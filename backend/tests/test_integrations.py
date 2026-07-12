import httpx
import respx

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
