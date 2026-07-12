"""Hierarchy workspace: org endpoints, my/team tasks, meetings, requests
(approval chain), workspace summary, audit middleware coverage."""
from __future__ import annotations

from tests.conftest import login


def _auth(client, email):
    return {"Authorization": f"Bearer {login(client, email)}"}


# --- Org seed integrity + /org endpoints ---

def test_seed_org_tree_integrity(db):
    # every L1/L2 user has a reports_to that exists; every team lead exists
    users = {u["user_id"]: u for u in db.users.find({})}
    for u in users.values():
        if u.get("level") in (1, 2):
            assert u["reports_to"] in users, f"{u['user_id']} has dangling lead"
    for t in db.teams.find({}):
        assert t["lead_id"] in users


def test_org_me_employee(client, auth_header):
    r = client.get("/api/v1/org/me", headers=auth_header("manas.ankarla@flynava.ai"))
    assert r.status_code == 200
    body = r.json()
    assert body["level"] == 1
    assert body["team"]["team_id"] == "team_python"
    assert body["lead"]["user_id"] == "u_murugan"
    assert body["reports"] == []


def test_org_me_team_lead_has_reports(client, auth_header):
    r = client.get("/api/v1/org/me", headers=auth_header("murugan.p@flynava.ai"))
    body = r.json()
    assert body["level"] == 2
    assert any(m["user_id"] == "u_manas" for m in body["reports"])


def test_auth_me_carries_hierarchy(client, auth_header):
    r = client.get("/api/v1/auth/me", headers=auth_header("manas.ankarla@flynava.ai"))
    u = r.json()["user"]
    assert u["level"] == 1
    assert u["team_id"] == "team_python"
    assert u["reports_to"] == "u_murugan"
    assert u["designation"] == "Python Developer"


# --- Tasks ---

def test_my_tasks_buckets(client, auth_header, db):
    # Dinesh (UI team) has no seed-assigned tasks — insert controlled fixtures
    # so bucket counts don't depend on the synthetic bug generator's RNG output.
    db.tasks.insert_one({"task_id": "fx1", "title": "Done fixture",
                         "assignee_id": "u_dinesh", "status": "Done",
                         "progress": 100, "due_date": "2020-01-01"})
    db.tasks.insert_one({"task_id": "fx2", "title": "Overdue fixture",
                         "assignee_id": "u_dinesh", "status": "In progress",
                         "progress": 30, "due_date": "2020-01-01"})
    r = client.get("/api/v1/tasks/my", headers=auth_header("dinesh.pandia@flynava.ai"))
    assert r.status_code == 200
    body = r.json()
    assert body["buckets"]["total"] == 2
    assert body["buckets"]["completed"] == 1
    assert body["buckets"]["overdue"] == 1


def test_task_creation_requires_l2(client, auth_header):
    # L1 can no longer self-create tasks — task creation is L2+ only
    denied = client.post("/api/v1/tasks", headers=auth_header("manas.ankarla@flynava.ai"),
                         json={"title": "Write unit tests"})
    assert denied.status_code == 403


def test_lead_creates_task_for_self_and_forbidden_outside_team(client, auth_header):
    h = auth_header("murugan.p@flynava.ai")
    ok = client.post("/api/v1/tasks", headers=h, json={"title": "Plan sprint"})
    assert ok.status_code == 200
    assert ok.json()["assignee_id"] == "u_murugan"
    denied = client.post("/api/v1/tasks", headers=h,
                         json={"title": "Nope", "assignee_id": "u_akshaya"})
    assert denied.status_code == 403


def test_lead_assigns_task_to_report_and_notifies(client, auth_header, db):
    h = auth_header("murugan.p@flynava.ai")
    r = client.post("/api/v1/tasks", headers=h,
                    json={"title": "Review PR", "assignee_id": "u_manas"})
    assert r.status_code == 200
    assert db.notifications.find_one({"recipient_id": "u_manas",
                                      "type": "task_assigned"})
    assert db.audit_logs.find_one({"action": "task_created",
                                   "actor_id": "u_murugan"})


def test_team_tasks_requires_lead(client, auth_header):
    assert client.get("/api/v1/tasks/team",
                      headers=auth_header("manas.ankarla@flynava.ai")).status_code == 403
    r = client.get("/api/v1/tasks/team", headers=auth_header("murugan.p@flynava.ai"))
    assert r.status_code == 200
    assert any(m["user_id"] == "u_manas" for m in r.json()["members"])


# --- Meetings ---

def test_meeting_create_list_cancel(client, auth_header, db):
    h = auth_header("murugan.p@flynava.ai")
    r = client.post("/api/v1/meetings", headers=h, json={
        "title": "1:1", "start": "2030-01-01T10:00", "end": "2030-01-01T10:30",
        "attendee_ids": ["u_manas"]})
    assert r.status_code == 200
    mid = r.json()["meeting_id"]
    assert db.notifications.find_one({"recipient_id": "u_manas",
                                      "type": "meeting_invite"})
    # attendee sees it
    mine = client.get("/api/v1/meetings/my",
                      headers=auth_header("manas.ankarla@flynava.ai")).json()
    assert any(m["meeting_id"] == mid for m in mine)
    # attendee cannot cancel, organizer can
    assert client.delete(f"/api/v1/meetings/{mid}",
                         headers=auth_header("manas.ankarla@flynava.ai")).status_code == 404
    assert client.delete(f"/api/v1/meetings/{mid}", headers=h).status_code == 200


def test_seeded_meetings_visible(client, auth_header):
    r = client.get("/api/v1/meetings/my", headers=auth_header("manas.ankarla@flynava.ai"))
    assert any(m["title"] == "Python Stand-up" for m in r.json())


# --- Requests / approval chain ---

def test_request_routes_to_direct_lead_and_approve(client, auth_header, db):
    h_emp = auth_header("manas.ankarla@flynava.ai")
    r = client.post("/api/v1/requests", headers=h_emp, json={
        "type": "hr_grievance", "title": "Broken chair", "body": "please fix"})
    assert r.status_code == 200
    req = r.json()
    assert req["approver_id"] == "u_murugan"  # direct lead first
    assert db.notifications.find_one({"recipient_id": "u_murugan",
                                      "type": "approval_request"})

    h_tl = auth_header("murugan.p@flynava.ai")
    inbox = client.get("/api/v1/requests/inbox", headers=h_tl).json()
    assert any(x["req_id"] == req["req_id"] for x in inbox)

    ok = client.post(f"/api/v1/requests/{req['req_id']}/approve", headers=h_tl,
                     json={"comment": "done"})
    assert ok.status_code == 200
    assert ok.json()["status"] == "approved"
    assert db.notifications.find_one({"recipient_id": "u_manas",
                                      "type": "approval_decision"})
    assert db.audit_logs.find_one({"action": "request_approved",
                                   "entity_id": req["req_id"]})


def test_request_forward_moves_up_chain(client, auth_header):
    h_emp = auth_header("manas.ankarla@flynava.ai")
    req = client.post("/api/v1/requests", headers=h_emp, json={
        "type": "reimbursement", "title": "Laptop"}).json()

    h_tl = auth_header("murugan.p@flynava.ai")
    fwd = client.post(f"/api/v1/requests/{req['req_id']}/forward", headers=h_tl,
                      json={"comment": "above my budget"})
    assert fwd.status_code == 200
    assert fwd.json()["approver_id"] == "u_harsha"  # TL's own lead = eng head

    # engineering head can now approve
    h_head = auth_header("harsha.varlani@flynava.ai")
    ok = client.post(f"/api/v1/requests/{req['req_id']}/reject", headers=h_head,
                     json={"comment": "not this quarter"})
    assert ok.status_code == 200
    assert ok.json()["status"] == "rejected"


def test_stranger_cannot_decide(client, auth_header):
    h_emp = auth_header("manas.ankarla@flynava.ai")
    req = client.post("/api/v1/requests", headers=h_emp,
                      json={"type": "general", "title": "X"}).json()
    denied = client.post(f"/api/v1/requests/{req['req_id']}/approve",
                         headers=auth_header("prathima.ds@flynava.ai"), json={})
    assert denied.status_code == 404


def test_bad_request_type_rejected(client, auth_header):
    r = client.post("/api/v1/requests", headers=auth_header("manas.ankarla@flynava.ai"),
                    json={"type": "party", "title": "X"})
    assert r.status_code == 400


# --- Workspace summary + activity ---

def test_workspace_me_shape(client, auth_header):
    r = client.get("/api/v1/workspace/me", headers=auth_header("manas.ankarla@flynava.ai"))
    assert r.status_code == 200
    body = r.json()
    assert body["user"]["name"] == "Manas Ankarla"
    assert body["user"]["team_id"] == "team_python"
    assert body["team"]["name"] == "Python Team"
    assert body["lead"]["name"] == "Murugan P"
    for key in ("buckets", "tasks", "reopened", "meetings", "my_requests",
                "inbox_count", "unread_notifications", "activity"):
        assert key in body


def test_activity_scoped_to_self_for_l1(client, auth_header):
    h_emp = auth_header("manas.ankarla@flynava.ai")
    h_qa = auth_header("akshaya.g@flynava.ai")
    client.post("/api/v1/requests", headers=h_emp,
                json={"type": "general", "title": "Mine"})
    client.post("/api/v1/requests", headers=h_qa,
                json={"type": "general", "title": "Theirs"})
    acts = client.get("/api/v1/activity/recent", headers=h_emp).json()
    assert acts, "expected own activity"
    assert all(a["actor_id"] == "u_manas" for a in acts)


def test_audit_middleware_records_mutations(client, auth_header, db):
    client.post("/api/v1/tasks", headers=auth_header("murugan.p@flynava.ai"),
                json={"title": "Audit me"})
    row = db.audit_logs.find_one({"action": "api_call",
                                  "meta.path": "/api/v1/tasks"})
    assert row is not None
    assert row["actor_id"] == "u_murugan"
    assert row["meta"]["status_code"] == 200
    assert row["meta"]["method"] == "POST"


# --- Phase C: department-head workspace ---

def test_workspace_department_requires_l3(client, auth_header):
    denied = client.get("/api/v1/workspace/department",
                        headers=auth_header("murugan.p@flynava.ai"))
    assert denied.status_code == 403


def test_workspace_department_eng_rollup(client, auth_header):
    r = client.get("/api/v1/workspace/department",
                   headers=auth_header("harsha.varlani@flynava.ai"))
    assert r.status_code == 200
    body = r.json()
    assert body["department"] == "eng"
    team_ids = {t["team_id"] for t in body["teams"]}
    assert {"team_java", "team_python", "team_qa"} <= team_ids
    python_team = next(t for t in body["teams"] if t["team_id"] == "team_python")
    assert python_team["lead_name"] == "Murugan P"
    assert python_team["member_count"] >= 1
    assert "buckets" in python_team
    kpi_modules = {k["module"] for k in body["dept_kpis"]}
    assert kpi_modules <= {"operations", "product_dev"}
    assert len(body["dept_kpis"]) > 0


def test_workspace_department_positions_filtered(client, auth_header):
    r = client.get("/api/v1/workspace/department",
                   headers=auth_header("harsha.varlani@flynava.ai"))
    positions = r.json()["positions"]
    assert len(positions) > 0
    assert all(p["dept"] == "eng" for p in positions)


def test_workspace_department_hr(client, auth_header):
    r = client.get("/api/v1/workspace/department", headers=auth_header("hr@flynava.ai"))
    assert r.status_code == 200
    body = r.json()
    assert body["department"] == "hr"
    assert {t["team_id"] for t in body["teams"]} == {"team_hr"}
    kpi_modules = {k["module"] for k in body["dept_kpis"]}
    assert kpi_modules <= {"hr", "recruitment"}


def test_org_users_directory_includes_reports_to(client, auth_header):
    r = client.get("/api/v1/org/users", headers=auth_header("manas.ankarla@flynava.ai"))
    assert r.status_code == 200
    manas = next(u for u in r.json() if u["user_id"] == "u_manas")
    assert manas["reports_to"] == "u_murugan"
