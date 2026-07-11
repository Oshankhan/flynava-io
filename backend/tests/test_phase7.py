def test_award_creation_notifies_recipient(client, auth_header, db):
    # HR issues an award to the employee
    r = client.post("/api/v1/awards", headers=auth_header("hr@flynava.ai"),
                    json={"recipient_id": "u_emp", "title": "Innovation Star",
                          "description": "Shipped IO Phase 0", "category": "Innovation Award"})
    assert r.status_code == 200
    # recipient has an unread notification (AWR-005)
    unread = client.get("/api/v1/notifications/unread_count",
                        headers=auth_header("employee@flynava.ai"))
    assert unread.json()["count"] == 1


def test_employee_cannot_create_award(client, auth_header):
    r = client.post("/api/v1/awards", headers=auth_header("employee@flynava.ai"),
                    json={"recipient_id": "u_mgr", "title": "x"})
    assert r.status_code == 403


def test_award_react_and_leaderboard(client, auth_header, db):
    made = client.post("/api/v1/awards", headers=auth_header("manager@flynava.ai"),
                       json={"recipient_id": "u_emp", "title": "Team Player"})
    award_id = made.json()["award_id"]
    react = client.post(f"/api/v1/awards/{award_id}/react",
                        headers=auth_header("employee@flynava.ai"),
                        json={"type": "clap"})
    assert react.status_code == 200
    lb = client.get("/api/v1/awards/leaderboard", headers=auth_header("hr@flynava.ai"))
    assert lb.status_code == 200
    assert lb.json()[0]["recipient_id"] == "u_emp"


def test_mark_notification_read(client, auth_header, db):
    client.post("/api/v1/awards", headers=auth_header("hr@flynava.ai"),
                json={"recipient_id": "u_emp", "title": "Kudos"})
    notes = client.get("/api/v1/notifications",
                       headers=auth_header("employee@flynava.ai")).json()
    nid = notes[0]["notif_id"]
    client.post(f"/api/v1/notifications/{nid}/read",
                headers=auth_header("employee@flynava.ai"))
    unread = client.get("/api/v1/notifications/unread_count",
                        headers=auth_header("employee@flynava.ai"))
    assert unread.json()["count"] == 0


def test_admin_kpi_def_upsert_requires_super_admin(client, auth_header, db):
    denied = client.put("/api/v1/admin/kpi-defs", headers=auth_header("hr@flynava.ai"),
                        json={"kpi_id": "x", "name": "X", "module": "hr"})
    assert denied.status_code == 403
    ok = client.put("/api/v1/admin/kpi-defs", headers=auth_header("admin@flynava.ai"),
                    json={"kpi_id": "cust_metric", "name": "Custom Metric",
                          "module": "hr", "unit": "count"})
    assert ok.status_code == 200
    defs = client.get("/api/v1/admin/kpi-defs", headers=auth_header("admin@flynava.ai"))
    assert any(d["kpi_id"] == "cust_metric" for d in defs.json())


def test_admin_notification_log(client, auth_header, db):
    client.post("/api/v1/awards", headers=auth_header("hr@flynava.ai"),
                json={"recipient_id": "u_emp", "title": "Log Me"})
    log = client.get("/api/v1/admin/notification-log",
                     headers=auth_header("admin@flynava.ai"))
    assert log.status_code == 200
    assert len(log.json()) >= 1
