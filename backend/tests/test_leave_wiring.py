"""Leave requests write through to HR data on approval (Phase A).

Submitting type=leave requires leave_type/from_date/to_date and computes
`days`; approving decrements employees.leave_balance and adds a `leaves`
history row; rejecting or other request types leave HR data untouched.
"""
from __future__ import annotations


def test_leave_requires_type_dates(client, auth_header):
    h = auth_header("manas.ankarla@flynava.ai")
    r = client.post("/api/v1/requests", headers=h,
                    json={"type": "leave", "title": "Family trip"})
    assert r.status_code == 400


def test_leave_days_computed(client, auth_header):
    h = auth_header("manas.ankarla@flynava.ai")
    r = client.post("/api/v1/requests", headers=h, json={
        "type": "leave", "title": "Family trip", "leave_type": "Casual",
        "from_date": "2030-01-01", "to_date": "2030-01-03"})
    assert r.status_code == 200
    body = r.json()
    assert body["days"] == 3
    assert body["leave_type"] == "Casual"


def test_leave_approve_writes_through_to_hr(client, auth_header):
    h_emp = auth_header("manas.ankarla@flynava.ai")
    h_tl = auth_header("murugan.p@flynava.ai")

    before = client.get("/api/v1/hr/me", headers=h_emp).json()
    before_balance = before["leave_balance"]["Casual"]
    before_leave_count = len(before["leaves"])

    req = client.post("/api/v1/requests", headers=h_emp, json={
        "type": "leave", "title": "Family trip", "leave_type": "Casual",
        "from_date": "2030-01-01", "to_date": "2030-01-02"}).json()
    assert req["days"] == 2

    dec = client.post(f"/api/v1/requests/{req['req_id']}/approve", headers=h_tl,
                      json={"comment": "enjoy"})
    assert dec.status_code == 200
    assert dec.json()["status"] == "approved"

    after = client.get("/api/v1/hr/me", headers=h_emp).json()
    assert after["leave_balance"]["Casual"] == max(0, before_balance - 2)
    assert len(after["leaves"]) == before_leave_count + 1
    newest = after["leaves"][0]
    assert newest["type"] == "Casual"
    assert newest["days"] == 2
    assert newest["status"] == "Approved"


def test_leave_reject_does_not_mutate_hr(client, auth_header):
    h_emp = auth_header("manas.ankarla@flynava.ai")
    h_tl = auth_header("murugan.p@flynava.ai")

    before = client.get("/api/v1/hr/me", headers=h_emp).json()

    req = client.post("/api/v1/requests", headers=h_emp, json={
        "type": "leave", "title": "Trip", "leave_type": "Sick",
        "from_date": "2030-02-01", "to_date": "2030-02-01"}).json()

    dec = client.post(f"/api/v1/requests/{req['req_id']}/reject", headers=h_tl,
                      json={"comment": "not now"})
    assert dec.status_code == 200
    assert dec.json()["status"] == "rejected"

    after = client.get("/api/v1/hr/me", headers=h_emp).json()
    assert after["leave_balance"] == before["leave_balance"]
    assert len(after["leaves"]) == len(before["leaves"])


def test_non_leave_request_unaffected(client, auth_header):
    h_emp = auth_header("manas.ankarla@flynava.ai")
    h_tl = auth_header("murugan.p@flynava.ai")

    before = client.get("/api/v1/hr/me", headers=h_emp).json()

    req = client.post("/api/v1/requests", headers=h_emp,
                      json={"type": "general", "title": "Laptop stand"}).json()
    assert req["days"] is None
    assert req["leave_type"] is None

    dec = client.post(f"/api/v1/requests/{req['req_id']}/approve", headers=h_tl, json={})
    assert dec.status_code == 200

    after = client.get("/api/v1/hr/me", headers=h_emp).json()
    assert after["leave_balance"] == before["leave_balance"]
    assert len(after["leaves"]) == len(before["leaves"])


def test_leave_insufficient_balance_still_approves_floored_at_zero(client, auth_header, db):
    h_emp = auth_header("manas.ankarla@flynava.ai")
    h_tl = auth_header("murugan.p@flynava.ai")
    db.employees.update_one({"email": "manas.ankarla@flynava.ai"},
                            {"$set": {"leave_balance.Earned": 1}})

    req = client.post("/api/v1/requests", headers=h_emp, json={
        "type": "leave", "title": "Long trip", "leave_type": "Earned",
        "from_date": "2030-03-01", "to_date": "2030-03-05"}).json()
    assert req["days"] == 5

    dec = client.post(f"/api/v1/requests/{req['req_id']}/approve", headers=h_tl, json={})
    assert dec.status_code == 200

    after = client.get("/api/v1/hr/me", headers=h_emp).json()
    assert after["leave_balance"]["Earned"] == 0

    audit_row = db.audit_logs.find_one({"action": "request_approved",
                                        "entity_id": req["req_id"]})
    assert audit_row["meta"]["leave"]["insufficient"] is True
