"""CEO-demo build, Phase 1: seed enrichment (UI team under Engineering,
attendance, automation scripts), org drill-down (/org/reports,
/org/users/{id}/overview), the L4 exec workspace, and the SSE notification
stream.
"""
from __future__ import annotations

import datetime as dt
import json

from tests.conftest import DEMO_PASSWORD


# --- Seed enrichment ---

def test_ui_team_under_engineering_with_manager_and_lead(db):
    # UI has no separate department — it's one of Engineering's teams, same
    # as Java/Python/QA — but carries an extra reporting hop: a UI Manager
    # (Birbal) between the eng head and the UI Lead (Mushaheed).
    assert db.departments.find_one({"dept_id": "ui"}) is None

    team = db.teams.find_one({"team_id": "team_ui"})
    assert team["department"] == "eng"
    assert team["lead_id"] == "u_birbal"

    birbal = db.users.find_one({"user_id": "u_birbal"})
    assert birbal["department"] == "eng"
    assert birbal["reports_to"] == "u_harsha"

    mushaheed = db.users.find_one({"user_id": "u_mushaheed"})
    assert mushaheed["department"] == "eng"
    assert mushaheed["reports_to"] == "u_birbal"
    assert mushaheed["team_id"] == "team_ui"

    devs = list(db.users.find({"team_id": "team_ui", "level": 1}))
    assert len(devs) == 6
    assert all(d["reports_to"] == "u_mushaheed" for d in devs)
    assert all(d["department"] == "eng" for d in devs)


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
    r = client.get("/api/v1/org/reports/u_ceo", headers=auth_header("admin@flynava.ai"))
    assert r.status_code == 200
    body = r.json()
    names = {m["name"] for m in body}
    assert "Harsha Varlani" in names
    mgr = next(m for m in body if m["user_id"] == "u_harsha")
    assert mgr["has_reports"] is True
    assert "buckets" in mgr and "late_7d" in mgr and "reopened_count" in mgr


def test_org_reports_access_control(client, auth_header):
    # a team lead may view their own reports
    ok = client.get("/api/v1/org/reports/u_murugan",
                    headers=auth_header("murugan.p@flynava.ai"))
    assert ok.status_code == 200
    assert any(m["user_id"] == "u_manas" for m in ok.json())

    # an unrelated team lead may not view someone else's reports
    denied = client.get("/api/v1/org/reports/u_murugan",
                        headers=auth_header("prathima.ds@flynava.ai"))
    assert denied.status_code == 403

    # an ancestor (dept head) CAN view a report two levels down
    ancestor_ok = client.get("/api/v1/org/reports/u_murugan",
                             headers=auth_header("harsha.varlani@flynava.ai"))
    assert ancestor_ok.status_code == 200

    # L4 can view anything
    l4_ok = client.get("/api/v1/org/reports/u_mushaheed", headers=auth_header("admin@flynava.ai"))
    assert l4_ok.status_code == 200


def test_org_user_overview_shape_and_access(client, auth_header):
    r = client.get("/api/v1/org/users/u_manas/overview",
                   headers=auth_header("murugan.p@flynava.ai"))
    assert r.status_code == 200
    body = r.json()
    for key in ("user", "team", "lead", "buckets", "tasks", "reopened", "authored",
                "attendance", "leave_balance", "recent_leaves", "pending_docs",
                "meetings", "activity"):
        assert key in body
    assert body["attendance"]["rows"]
    assert body["attendance"]["late_count"] + body["attendance"]["absent_count"] \
        + body["attendance"]["present_count"] == len(body["attendance"]["rows"])

    # unrelated peer cannot view Manas's overview
    denied = client.get("/api/v1/org/users/u_manas/overview",
                        headers=auth_header("akshaya.g@flynava.ai"))
    assert denied.status_code == 403

    # self-view always allowed
    self_ok = client.get("/api/v1/org/users/u_manas/overview",
                         headers=auth_header("manas.ankarla@flynava.ai"))
    assert self_ok.status_code == 200


def test_org_users_directory_and_reports_all_include_reports_to(client, auth_header):
    r = client.get("/api/v1/org/reports/u_harsha", headers=auth_header("harsha.varlani@flynava.ai"))
    assert r.status_code == 200
    assert all("reports_to" in m for m in r.json())


# --- Exec workspace ---

def test_workspace_exec_requires_l4(client, auth_header):
    denied = client.get("/api/v1/workspace/exec", headers=auth_header("harsha.varlani@flynava.ai"))
    assert denied.status_code == 403


def test_workspace_exec_shape(client, auth_header):
    r = client.get("/api/v1/workspace/exec", headers=auth_header("admin@flynava.ai"))
    assert r.status_code == 200
    body = r.json()
    for key in ("kpis", "projects", "departments", "automation", "pending_docs",
                "attendance_today", "inbox_count", "meetings", "activity"):
        assert key in body

    dept_ids = {d["dept_id"] for d in body["departments"]}
    assert {"eng", "fin", "hr"} <= dept_ids
    assert "ui" not in dept_ids
    eng = next(d for d in body["departments"] if d["dept_id"] == "eng")
    assert eng["head"]["name"] == "Harsha Varlani"
    assert eng["teams_count"] == 5  # devops, java, python, qa, ui

    # Meghna is multi-role (manager + marketing) — she heads Product (her
    # primary department) AND Marketing (via her extra role). Rather than two
    # identical-head cards, they're merged into one combined "Product &
    # Marketing" card, and Meghna appears exactly once across all dept cards.
    head_names = [d["head"]["name"] for d in body["departments"] if d.get("head")]
    assert head_names.count("Meghna Mehra") == 1
    meghna_card = next(d for d in body["departments"]
                       if d.get("head") and d["head"]["name"] == "Meghna Mehra")
    assert "Product" in meghna_card["name"] and "Marketing" in meghna_card["name"]
    assert eng["member_count"] >= 20

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
                    headers=auth_header("manas.ankarla@flynava.ai"))
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
    assert body["users"] == before_users
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
                        json={"email": "manas.ankarla@flynava.ai", "password": DEMO_PASSWORD})
    token = login.json()["access_token"]

    with client.stream("GET", f"/api/v1/notifications/stream?token={token}") as r:
        assert r.status_code == 200
        line = next(r.iter_lines())
        assert "count" in line or line.startswith(":")
        if "count" in line:
            payload = json.loads(line.removeprefix("data: "))
            assert isinstance(payload["count"], int)
