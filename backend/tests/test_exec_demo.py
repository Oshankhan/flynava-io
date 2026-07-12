"""CEO-demo build, Phase 1: seed enrichment (Birbal/UI dept, attendance,
automation scripts), org drill-down (/org/reports, /org/users/{id}/overview),
the L4 exec workspace, and the SSE notification stream.
"""
from __future__ import annotations

import datetime as dt
import json

from tests.conftest import DEMO_PASSWORD


# --- Seed enrichment ---

def test_birbal_ui_chain_seeded(db):
    birbal = db.users.find_one({"user_id": "u_birbal"})
    assert birbal["name"] == "Birbal Singh"
    assert birbal["level"] == 3
    assert birbal["department"] == "ui"
    assert birbal["reports_to"] == "u_admin"

    ui_tl = db.users.find_one({"user_id": "u_tl_ui"})
    assert ui_tl["reports_to"] == "u_birbal"
    assert ui_tl["team_id"] == "team_ui"

    devs = list(db.users.find({"team_id": "team_ui", "level": 1}))
    assert len(devs) == 2
    assert all(d["reports_to"] == "u_tl_ui" for d in devs)

    team = db.teams.find_one({"team_id": "team_ui"})
    assert team["department"] == "ui"
    assert team["lead_id"] == "u_tl_ui"


def test_attendance_seeded_for_every_employee(db):
    n_employees = db.employees.count_documents({})
    n_attendance = db.attendance.count_documents({"upload_id": "seed_history"})
    assert n_attendance == n_employees * 7
    statuses = {r["status"] for r in db.attendance.find({"upload_id": "seed_history"})}
    assert statuses <= {"Present", "Late", "Absent"}


def test_automation_scripts_and_product_docs_seeded(db):
    assert db.automation_scripts.count_documents({}) > 0
    modules = {a["module"] for a in db.automation_scripts.find()}
    assert "Payments" in modules
    assert db.product_docs.count_documents({"status": "pending"}) > 0


# --- Org drill-down ---

def test_org_reports_of_ceo_lists_dept_heads(client, auth_header):
    r = client.get("/api/v1/org/reports/u_admin", headers=auth_header("admin@flynava.ai"))
    assert r.status_code == 200
    body = r.json()
    names = {m["name"] for m in body}
    assert "Birbal Singh" in names
    birbal = next(m for m in body if m["user_id"] == "u_birbal")
    assert birbal["has_reports"] is True
    assert "buckets" in birbal and "late_7d" in birbal and "reopened_count" in birbal


def test_org_reports_access_control(client, auth_header):
    # a team lead may view their own reports
    ok = client.get("/api/v1/org/reports/u_tl_python",
                    headers=auth_header("python.tl@flynava.ai"))
    assert ok.status_code == 200
    assert any(m["user_id"] == "u_emp" for m in ok.json())

    # an unrelated team lead may not view someone else's reports
    denied = client.get("/api/v1/org/reports/u_tl_python",
                        headers=auth_header("qa.tl@flynava.ai"))
    assert denied.status_code == 403

    # an ancestor (dept head) CAN view a report two levels down
    ancestor_ok = client.get("/api/v1/org/reports/u_tl_python",
                             headers=auth_header("manager@flynava.ai"))
    assert ancestor_ok.status_code == 200

    # L4 can view anything
    l4_ok = client.get("/api/v1/org/reports/u_tl_ui", headers=auth_header("admin@flynava.ai"))
    assert l4_ok.status_code == 200


def test_org_user_overview_shape_and_access(client, auth_header):
    r = client.get("/api/v1/org/users/u_emp/overview",
                   headers=auth_header("python.tl@flynava.ai"))
    assert r.status_code == 200
    body = r.json()
    for key in ("user", "team", "lead", "buckets", "tasks", "reopened", "authored",
                "attendance", "leave_balance", "recent_leaves", "pending_docs",
                "meetings", "activity"):
        assert key in body
    assert body["attendance"]["rows"]
    assert body["attendance"]["late_count"] + body["attendance"]["absent_count"] \
        + body["attendance"]["present_count"] == len(body["attendance"]["rows"])

    # unrelated peer cannot view Evan's overview
    denied = client.get("/api/v1/org/users/u_emp/overview",
                        headers=auth_header("qa.eng@flynava.ai"))
    assert denied.status_code == 403

    # self-view always allowed
    self_ok = client.get("/api/v1/org/users/u_emp/overview",
                         headers=auth_header("employee@flynava.ai"))
    assert self_ok.status_code == 200


def test_org_users_directory_and_reports_all_include_reports_to(client, auth_header):
    r = client.get("/api/v1/org/reports/u_mgr", headers=auth_header("manager@flynava.ai"))
    assert r.status_code == 200
    assert all("reports_to" in m for m in r.json())


# --- Exec workspace ---

def test_workspace_exec_requires_l4(client, auth_header):
    denied = client.get("/api/v1/workspace/exec", headers=auth_header("manager@flynava.ai"))
    assert denied.status_code == 403


def test_workspace_exec_shape(client, auth_header):
    r = client.get("/api/v1/workspace/exec", headers=auth_header("admin@flynava.ai"))
    assert r.status_code == 200
    body = r.json()
    for key in ("kpis", "projects", "departments", "automation", "pending_docs",
                "attendance_today", "inbox_count", "meetings", "activity"):
        assert key in body

    dept_ids = {d["dept_id"] for d in body["departments"]}
    assert {"eng", "fin", "hr", "mkt", "ui"} <= dept_ids
    ui = next(d for d in body["departments"] if d["dept_id"] == "ui")
    assert ui["head"]["name"] == "Birbal Singh"
    assert ui["teams_count"] == 1
    assert ui["member_count"] >= 4  # Birbal + TL + 2 devs

    assert body["automation"]["pending"] > 0
    assert "Payments" in body["automation"]["by_module"]

    at = body["attendance_today"]
    total_today = at["present"] + at["late"] + at["absent"]
    if dt.date.today().weekday() < 5:  # weekday: attendance is seeded for today
        assert total_today > 0
    else:  # weekend: correctly nothing seeded for today
        assert total_today == 0


# --- Additive-only demo refresh (safe to run against a live/seeded DB) ---

def test_bootstrap_seed_refuses_when_already_seeded(client):
    r = client.post("/api/v1/bootstrap-seed")
    assert r.status_code == 409


def test_refresh_demo_requires_super_admin(client, auth_header):
    r = client.post("/api/v1/bootstrap-seed/refresh-demo",
                    headers=auth_header("employee@flynava.ai"))
    assert r.status_code == 403


def test_refresh_demo_is_additive_and_preserves_real_leaves(client, auth_header, db):
    # a leave the seed never wrote — proves seed_demo_extras doesn't wipe it
    db.leaves.insert_one({"leave_id": "real1", "emp_id": "E9999", "type": "Sick",
                          "from": "2026-07-01", "to": "2026-07-01", "days": 1,
                          "status": "Pending"})
    before_users = db.users.count_documents({})

    r = client.post("/api/v1/bootstrap-seed/refresh-demo",
                    headers=auth_header("admin@flynava.ai"))
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "refreshed"
    assert body["users"] == 4
    assert body["automation_scripts"] > 0
    assert body["product_docs"] > 0

    assert db.users.count_documents({}) == before_users
    assert db.leaves.find_one({"leave_id": "real1"}) is not None


# --- SSE stream ---

def test_notifications_stream_rejects_bad_token(client):
    with client.stream("GET", "/api/v1/notifications/stream?token=garbage") as r:
        assert r.status_code == 401


def test_notifications_stream_pushes_unread_count(client, auth_header, monkeypatch):
    from app.api.v1 import notifications as notif_api
    monkeypatch.setattr(notif_api, "STREAM_INTERVAL_SECONDS", 0.01)
    monkeypatch.setattr(notif_api, "STREAM_MAX_TICKS", 2)

    login = client.post("/api/v1/auth/login",
                        json={"email": "employee@flynava.ai", "password": DEMO_PASSWORD})
    token = login.json()["access_token"]

    with client.stream("GET", f"/api/v1/notifications/stream?token={token}") as r:
        assert r.status_code == 200
        line = next(r.iter_lines())
        assert "count" in line or line.startswith(":")
        if "count" in line:
            payload = json.loads(line.removeprefix("data: "))
            assert isinstance(payload["count"], int)
