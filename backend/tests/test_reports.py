from app.services import reports


def _seed_bugs(db):
    rows = [
        ("7014", "CLARA | Certain O-Ds missing from dropdown selection", "Reopen",
         "Normal", "Birbal Kumar", "Nikkitha Ann Bobby"),
        ("7858", "PROD | AMS-NBO recommendation needs to check", "New", "High",
         "Harshitha", "Akhil N"),
        ("7577", "REPLICA | Footnote fare count not matching", "In progress",
         "Immediate", "Anuvrat Gautam", "Nikshitha TB"),
    ]
    db.projects.insert_one({"source_system": "openproject", "source_id": "52",
                            "name": "KQ Module wise Issues", "status": "active"})
    for op_id, title, st, prio, assignee, author in rows:
        db.tasks.insert_one({
            "source_system": "openproject", "source_id": op_id, "title": title,
            "wp_type": "Bug", "status": st, "priority": prio,
            "assignee": assignee, "author": author, "project_source_id": "52",
            "progress": 0,
        })


def test_split_subject_parses_prefix():
    assert reports._split_subject("REPLICA | Rules query", "Bug") == (
        "REPLICA", "Rules query")
    assert reports._split_subject("No prefix here", "Bug") == ("Bug", "No prefix here")


def test_list_projects_and_bugs(db):
    _seed_bugs(db)
    projects = reports.list_projects(db)
    assert projects[0]["source_id"] == "52"
    assert projects[0]["bug_count"] == 3
    bugs = reports.list_bugs(db, "52")
    assert len(bugs) == 3
    clara = next(b for b in bugs if b["op_id"] == "7014")
    assert clara["bug_type"] == "CLARA"
    assert clara["accountable"] == "Nikkitha Ann Bobby"


def test_render_html_contains_rows_and_links(db):
    _seed_bugs(db)
    rows = reports.bugs_by_ids(db, ["7858", "7014"])
    assert [r["op_id"] for r in rows] == ["7858", "7014"]  # preserves selection order
    html = reports.render_html("Bug Status Summary", "Please review.", rows)
    assert "Bug Status Summary" not in html  # title isn't injected; subject only
    assert "AMS-NBO" in html and "7858" in html
    assert "work_packages/7858" in html
    assert "Accountable" in html


def test_projects_endpoint_requires_sender_role(client, auth_header, db):
    _seed_bugs(db)
    denied = client.get("/api/v1/reports/projects",
                        headers=auth_header("manas.ankarla@flynava.ai"))
    assert denied.status_code == 403
    ok = client.get("/api/v1/reports/projects",
                    headers=auth_header("harsha.varlani@flynava.ai"))
    assert ok.status_code == 200
    assert ok.json()[0]["bug_count"] == 3


def test_generate_report_returns_html(client, auth_header, db):
    _seed_bugs(db)
    r = client.post("/api/v1/reports/generate",
                    headers=auth_header("harsha.varlani@flynava.ai"),
                    json={"bug_ids": ["7014", "7577"], "title": "Re-Opens Compilation"})
    assert r.status_code == 200
    body = r.json()
    assert body["count"] == 2
    assert "7014" in body["html"]


def test_send_report_preview_mode_without_smtp(client, auth_header, db):
    _seed_bugs(db)
    r = client.post("/api/v1/reports/send",
                    headers=auth_header("harsha.varlani@flynava.ai"),
                    json={"bug_ids": ["7014"], "recipients": ["boss@flynava.ai"],
                          "title": "Daily Bugs"})
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "preview"  # no SMTP configured in tests
    assert body["count"] == 1
    # audit + sender notification recorded
    assert db.audit_logs.count_documents({"action": "bug_report_preview"}) == 1


def test_send_with_smtp_configured(client, auth_header, db, monkeypatch):
    _seed_bugs(db)
    from app.config import settings

    sent = {}

    class FakeSMTP:
        def __init__(self, *a, **k):
            pass

        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

        def starttls(self):
            sent["tls"] = True

        def login(self, u, p):
            sent["login"] = (u, p)

        def sendmail(self, frm, to, msg):
            sent["to"] = to

    monkeypatch.setattr(settings, "smtp_host", "smtp.test")
    monkeypatch.setattr(settings, "smtp_user", "io@flynava.ai")
    monkeypatch.setattr(settings, "smtp_password", "pw")
    monkeypatch.setattr("app.services.reports.smtplib.SMTP", FakeSMTP)

    r = client.post("/api/v1/reports/send",
                    headers=auth_header("leadership@flynava.ai"),
                    json={"bug_ids": ["7858"], "recipients": ["mahesh@flynava.ai"],
                          "title": "Status"})
    assert r.status_code == 200
    assert r.json()["status"] == "sent"
    assert sent["to"] == ["mahesh@flynava.ai"]


def test_generate_empty_selection_400(client, auth_header):
    r = client.post("/api/v1/reports/generate",
                    headers=auth_header("harsha.varlani@flynava.ai"),
                    json={"bug_ids": []})
    assert r.status_code == 400
