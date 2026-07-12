import io

from app.services import hr

SAMPLE_CSV = (
    "Emp Code,Employee Name,Date,In Time,Out Time,Status\n"
    "E0005,Evan Employee,2026-07-07,09:05,18:10,\n"      # status derived -> Present
    "E0003,Mia Manager,2026-07-07,09:47,18:00,Late\n"
    "E0004,Hana HR,2026-07-07,,,Absent\n"
)


def test_seed_hr_creates_employees_payslips_leaves(db):
    # conftest seed() already runs seed_hr; every login user has an employee record
    assert db.employees.count_documents({}) >= 8
    emp = db.employees.find_one({"email": "manas.ankarla@flynava.ai"})
    assert emp and emp["salary"]["net"] < emp["salary"]["gross"]
    assert db.payslips.count_documents({"emp_id": emp["emp_id"]}) == 3
    assert emp["leave_balance"]["Casual"] >= 0


def test_employee_by_email_returns_payslips_and_leaves(db):
    rec = hr.employee_by_email(db, "manas.ankarla@flynava.ai")
    assert rec is not None
    assert len(rec["payslips"]) == 3
    assert isinstance(rec["leaves"], list)


def test_parse_attendance_maps_columns_and_derives_status():
    rows = hr.parse_attendance(SAMPLE_CSV.encode())
    assert len(rows) == 3
    evan = rows[0]
    assert evan["name"] == "Evan Employee"
    assert evan["status"] == "Present"      # derived from in+out present
    assert evan["hours"] and evan["hours"] > 8
    assert rows[2]["status"] == "Absent"


def test_summary_counts_by_status():
    rows = hr.parse_attendance(SAMPLE_CSV.encode())
    s = hr._summary(rows)
    assert s["total"] == 3
    assert s["by_status"]["Present"] == 1
    assert s["by_status"]["Absent"] == 1


def test_my_record_endpoint_self_service(client, auth_header):
    r = client.get("/api/v1/hr/me", headers=auth_header("manas.ankarla@flynava.ai"))
    assert r.status_code == 200
    body = r.json()
    assert body["email"] == "manas.ankarla@flynava.ai"
    assert "payslips" in body and "leave_balance" in body


def test_directory_requires_hr_role(client, auth_header):
    denied = client.get("/api/v1/hr/employees",
                        headers=auth_header("manas.ankarla@flynava.ai"))
    assert denied.status_code == 403
    ok = client.get("/api/v1/hr/employees", headers=auth_header("hr@flynava.ai"))
    assert ok.status_code == 200
    assert len(ok.json()) >= 8


def test_attendance_upload_and_send_flow(client, auth_header, db):
    files = {"file": ("bio.csv", io.BytesIO(SAMPLE_CSV.encode()), "text/csv")}
    up = client.post("/api/v1/hr/attendance/upload",
                     headers=auth_header("hr@flynava.ai"), files=files)
    assert up.status_code == 200
    body = up.json()
    assert body["rows"] == 3
    assert body["summary"]["by_status"]["Late"] == 1
    upload_id = body["upload_id"]

    sent = client.post("/api/v1/hr/attendance/send",
                       headers=auth_header("hr@flynava.ai"),
                       json={"upload_id": upload_id, "recipients": ["boss@flynava.ai"],
                             "title": "Daily Attendance 07/07"})
    assert sent.status_code == 200
    assert sent.json()["status"] == "preview"  # no SMTP in tests
    assert "Evan Employee" in sent.json()["preview_html"]
    assert db.attendance.count_documents({"upload_id": upload_id}) == 3


def test_attendance_upload_rejects_empty(client, auth_header):
    files = {"file": ("empty.csv", io.BytesIO(b"col1,col2\n"), "text/csv")}
    r = client.post("/api/v1/hr/attendance/upload",
                    headers=auth_header("hr@flynava.ai"), files=files)
    assert r.status_code == 400
