"""Phase B — role-exclusive dept panels: authored tasks, compliance items,
open positions, KPI history, HR Pending Leaves queue, team_lead access to
Bug Reports.
"""
from __future__ import annotations


# --- /tasks/my.authored ---

def test_my_tasks_includes_authored_key(client, auth_header):
    r = client.get("/api/v1/tasks/my", headers=auth_header("manas.ankarla@flynava.ai"))
    assert r.status_code == 200
    body = r.json()
    assert "authored" in body
    assert isinstance(body["authored"], list)


def test_authored_matches_openproject_author_field(client, auth_header, db):
    db.tasks.insert_one({
        "task_id": "opt1", "title": "Fix crash", "status": "Open",
        "wp_type": "Bug", "priority": "High", "due_date": None, "progress": 0,
        "assignee": "Someone Else", "author": "Manas Ankarla",
        "source_system": "openproject", "project_source_id": None,
    })
    r = client.get("/api/v1/tasks/my", headers=auth_header("manas.ankarla@flynava.ai"))
    authored = r.json()["authored"]
    assert any(t["title"] == "Fix crash" for t in authored)


# --- Compliance items ---

def test_compliance_items_readable_by_any_user(client, auth_header):
    r = client.get("/api/v1/compliance/items", headers=auth_header("manas.ankarla@flynava.ai"))
    assert r.status_code == 200
    items = r.json()
    assert len(items) == 3
    assert {"GST quarterly filing", "ISO 27001 surveillance audit",
            "PF/ESI monthly remittance"} == {i["title"] for i in items}


# --- Positions ---

def test_positions_open_and_dept_filter(client, auth_header):
    r = client.get("/api/v1/positions", headers=auth_header("chandrakala.t@flynava.ai"))
    assert r.status_code == 200
    assert len(r.json()) == 3
    eng_only = client.get("/api/v1/positions?dept=eng",
                          headers=auth_header("chandrakala.t@flynava.ai")).json()
    assert len(eng_only) == 2
    assert all(p["dept"] == "eng" for p in eng_only)


# --- KPI history ---

def test_kpi_history_requires_lead_role(client, auth_header):
    denied = client.get("/api/v1/kpis/fin_revenue_mtd/history",
                        headers=auth_header("manas.ankarla@flynava.ai"))
    assert denied.status_code == 403


def test_kpi_history_department_scoped_for_l1_and_l2(client, auth_header):
    # marketing executive (L1, role=employee, dept=mkt) reads marketing KPIs
    ok = client.get("/api/v1/kpis/mkt_leads/history",
                    headers=auth_header("arnav.jain@flynava.ai"))
    assert ok.status_code == 200
    # but not another department's KPI
    denied = client.get("/api/v1/kpis/fin_revenue_mtd/history",
                        headers=auth_header("arnav.jain@flynava.ai"))
    assert denied.status_code == 403
    # marketing team lead (L2) also reads marketing KPIs
    ok2 = client.get("/api/v1/kpis/mkt_conversion/history",
                     headers=auth_header("tanvi.gupta@flynava.ai"))
    assert ok2.status_code == 200
    # Rakshitha (Finance Manager, role="manager", department="fin") passes
    # via a normal department match — her department covers the finance
    # module, same gate a non-manager finance user would go through.
    ok = client.get("/api/v1/kpis/fin_revenue_mtd/history",
                    headers=auth_header("rakshitha.s@flynava.ai"))
    assert ok.status_code == 200
    body = ok.json()
    assert body["kpi_id"] == "fin_revenue_mtd"
    assert len(body["points"]) == 12


def test_kpi_history_404_for_unknown_kpi(client, auth_header):
    r = client.get("/api/v1/kpis/does_not_exist/history",
                   headers=auth_header("rakshitha.s@flynava.ai"))
    assert r.status_code == 404


# --- HR Pending Leaves queue ---

def test_pending_leaves_scoping(client, auth_header):
    denied = client.get("/api/v1/hr/leaves", headers=auth_header("manas.ankarla@flynava.ai"))
    assert denied.status_code == 403
    # HR head is allowed (require_hr_access's role=="hr" branch)
    ok = client.get("/api/v1/hr/leaves", headers=auth_header("hr@flynava.ai"))
    assert ok.status_code == 200
    rows = ok.json()
    assert len(rows) > 0
    assert all(r["status"] == "Pending" for r in rows)
    assert all("emp_name" in r for r in rows)
    # a non-HR team lead is denied
    denied2 = client.get("/api/v1/hr/leaves", headers=auth_header("murugan.p@flynava.ai"))
    assert denied2.status_code == 403


def test_pending_leave_approve_decrements_balance(client, auth_header, db):
    pending = list(db.leaves.find({"status": "Pending"}).limit(1))
    assert pending, "seed should produce at least one Pending leave"
    leave = pending[0]
    emp = db.employees.find_one({"emp_id": leave["emp_id"]})
    before = emp["leave_balance"].get(leave["type"], 0)

    h = auth_header("hr@flynava.ai")
    r = client.post(f"/api/v1/hr/leaves/{leave['leave_id']}/approve", headers=h,
                    json={"comment": "ok"})
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "Approved"
    assert body["balance"]["balance_after"] == max(0, before - leave["days"])

    after_emp = db.employees.find_one({"emp_id": leave["emp_id"]})
    assert after_emp["leave_balance"][leave["type"]] == max(0, before - leave["days"])

    # already-decided leave can't be decided again
    again = client.post(f"/api/v1/hr/leaves/{leave['leave_id']}/reject", headers=h, json={})
    assert again.status_code == 404


def test_pending_leave_reject_no_balance_change(client, auth_header, db):
    pending = list(db.leaves.find({"status": "Pending"}))
    assert len(pending) >= 2
    leave = pending[1]
    emp_before = db.employees.find_one({"emp_id": leave["emp_id"]})
    before = dict(emp_before["leave_balance"])

    h = auth_header("hr@flynava.ai")
    r = client.post(f"/api/v1/hr/leaves/{leave['leave_id']}/reject", headers=h, json={})
    assert r.status_code == 200
    assert r.json()["status"] == "Rejected"

    after_emp = db.employees.find_one({"emp_id": leave["emp_id"]})
    assert after_emp["leave_balance"] == before


# --- Reports access for team_lead (QA TL bug-report builder) ---

def test_reports_projects_allows_team_lead(client, auth_header):
    r = client.get("/api/v1/reports/projects", headers=auth_header("prathima.ds@flynava.ai"))
    assert r.status_code == 200
    denied = client.get("/api/v1/reports/projects", headers=auth_header("akshaya.g@flynava.ai"))
    assert denied.status_code == 403
