"""Enterprise Reporting Hub: seeded report defs, visibility (org/restricted/
private/confidential), creation gates, run generation + versioning, stats,
scheduling, sharing, sending, export, and saved views."""
from __future__ import annotations

from app.services.seed import REPORT_DEFS


def test_seed_creates_report_defs(db):
    assert db.report_defs.count_documents({}) == len(REPORT_DEFS)


def test_ceo_sees_all_non_confidential_employee_sees_only_org(client, auth_header):
    ceo = client.get("/api/v1/reports/defs?tab=all", headers=auth_header("admin@flynava.ai")).json()
    confidential_ids = {d["report_id"] for d in REPORT_DEFS if d["confidential"]}
    assert not (confidential_ids & {r["report_id"] for r in ceo})  # tab=all never shows confidential
    non_confidential = len(REPORT_DEFS) - len(confidential_ids)
    assert len(ceo) == non_confidential

    manas = client.get("/api/v1/reports/defs?tab=all",
                       headers=auth_header("manas.ankarla@flynava.ai")).json()
    names = {r["name"] for r in manas}
    assert "Bug Status Summary" in names          # org — everyone
    assert "Team Task Progress" not in names       # restricted to manager/team_lead
    assert "My Task Summary" not in names          # private, owned by someone else


def test_confidential_visibility_owner_allowlist_and_outsider(client, auth_header):
    outsider = client.get("/api/v1/reports/defs/rep_payroll",
                          headers=auth_header("manas.ankarla@flynava.ai"))
    assert outsider.status_code == 404

    owner = client.get("/api/v1/reports/defs/rep_payroll",
                       headers=auth_header("rakshitha.s@flynava.ai"))
    assert owner.status_code == 200

    allowlisted = client.get("/api/v1/reports/defs/rep_payroll", headers=auth_header("hr@flynava.ai"))
    assert allowlisted.status_code == 200

    ceo = client.get("/api/v1/reports/defs/rep_aws_monthly", headers=auth_header("admin@flynava.ai"))
    assert ceo.status_code == 200
    # AWS report's own owner (Kalaiarasan) isn't on the allowlist but still owns it
    owner2 = client.get("/api/v1/reports/defs/rep_aws_monthly",
                        headers=auth_header("kalaiarasan.d@flynava.ai"))
    assert owner2.status_code == 200


def test_confidential_tab_only_surfaces_confidential_defs(client, auth_header):
    rows = client.get("/api/v1/reports/defs?tab=confidential",
                      headers=auth_header("admin@flynava.ai")).json()
    assert rows and all(r["confidential"] for r in rows)


def test_create_def_creation_gates_by_level(client, auth_header):
    employee = auth_header("manas.ankarla@flynava.ai")
    denied_org = client.post("/api/v1/reports/defs", headers=employee, json={
        "name": "My Org Report", "domain": "development", "type": "summary",
        "sections": [{"kind": "documents_stats", "params": {}}], "visibility": "org",
    })
    assert denied_org.status_code == 403

    ok_private = client.post("/api/v1/reports/defs", headers=employee, json={
        "name": "My Private Report", "domain": "development", "type": "summary",
        "sections": [{"kind": "documents_stats", "params": {}}], "visibility": "private",
    })
    assert ok_private.status_code == 200
    assert ok_private.json()["is_mine"] is True

    denied_confidential = client.post("/api/v1/reports/defs", headers=employee, json={
        "name": "Sneaky Confidential", "domain": "finance", "type": "summary",
        "sections": [{"kind": "documents_stats", "params": {}}], "visibility": "private",
        "confidential": True,
    })
    assert denied_confidential.status_code == 403

    team_lead = auth_header("murugan.p@flynava.ai")
    ok_restricted = client.post("/api/v1/reports/defs", headers=team_lead, json={
        "name": "Team Lead Report", "domain": "development", "type": "summary",
        "sections": [{"kind": "documents_stats", "params": {}}], "visibility": "restricted",
    })
    assert ok_restricted.status_code == 200

    manager = auth_header("harsha.varlani@flynava.ai")
    ok_confidential = client.post("/api/v1/reports/defs", headers=manager, json={
        "name": "Manager Confidential", "domain": "finance", "type": "summary",
        "sections": [{"kind": "documents_stats", "params": {}}], "visibility": "restricted",
        "confidential": True,
    })
    assert ok_confidential.status_code == 200


def test_run_bug_summary_returns_table_and_versions_increment(client, auth_header):
    headers = auth_header("harsha.varlani@flynava.ai")
    r1 = client.post("/api/v1/reports/defs/rep_bug_summary/run", headers=headers, json={})
    assert r1.status_code == 200
    body = r1.json()
    assert body["version"] == 1
    table = next(s for s in body["sections"] if s["kind"] == "table")
    assert len(table["rows"]) > 0
    breakdown = next(s for s in body["sections"] if s["kind"] == "stats")
    assert len(breakdown["stats"]) > 0

    r2 = client.post("/api/v1/reports/defs/rep_bug_summary/run", headers=headers, json={})
    assert r2.json()["version"] == 2


def test_run_kpi_module_returns_stats_and_chart(client, auth_header):
    r = client.post("/api/v1/reports/defs/rep_resource_util/run",
                    headers=auth_header("harsha.varlani@flynava.ai"), json={})
    assert r.status_code == 200
    sections = r.json()["sections"]
    stats = next(s for s in sections if s["kind"] == "stats")
    chart = next(s for s in sections if s["kind"] == "chart")
    assert len(stats["stats"]) > 0
    assert len(chart["series"]) > 0


def test_run_with_ai_summary_stores_deterministic_echo_text(client, auth_header):
    r = client.post("/api/v1/reports/defs/rep_bug_summary/run",
                    headers=auth_header("harsha.varlani@flynava.ai"), json={"ai_summary": True})
    assert r.status_code == 200
    assert r.json()["ai_summary"]  # EchoProvider in tests — non-empty deterministic text


def test_payroll_run_denied_for_outsider_allowed_for_owner(client, auth_header):
    denied = client.post("/api/v1/reports/defs/rep_payroll/run",
                         headers=auth_header("manas.ankarla@flynava.ai"), json={})
    assert denied.status_code == 404  # can't even see the def to run it

    ok = client.post("/api/v1/reports/defs/rep_payroll/run",
                     headers=auth_header("rakshitha.s@flynava.ai"), json={})
    assert ok.status_code == 200
    assert ok.json()["sections"][0]["kind"] == "table"


def test_stats_endpoint_shape(client, auth_header):
    r = client.get("/api/v1/reports/stats", headers=auth_header("admin@flynava.ai"))
    assert r.status_code == 200
    body = r.json()
    for key in ("total_reports", "total_delta_this_month", "scheduled_reports", "next_schedule",
                "shared_reports", "total_downloads", "delivery_success_pct"):
        assert key in body
    assert body["total_reports"] > 0
    assert body["scheduled_reports"] > 0


def test_scheduled_endpoint_sorted_by_next_run(client, auth_header):
    rows = client.get("/api/v1/reports/scheduled", headers=auth_header("admin@flynava.ai")).json()
    assert len(rows) > 0
    assert all(r["schedule"]["active"] for r in rows)
    next_runs = [r["schedule"]["next_run_at"] for r in rows]
    assert next_runs == sorted(next_runs)


def test_schedule_set_requires_edit_rights_and_computes_next_run(client, auth_header):
    denied = client.put("/api/v1/reports/defs/rep_bug_summary/schedule",
                        headers=auth_header("manas.ankarla@flynava.ai"),
                        json={"frequency": "daily", "time": "10:00"})
    assert denied.status_code == 403

    ok = client.put("/api/v1/reports/defs/rep_bug_summary/schedule",
                    headers=auth_header("harsha.varlani@flynava.ai"),
                    json={"frequency": "weekly", "time": "10:00", "weekday": 2})
    assert ok.status_code == 200
    assert ok.json()["schedule"]["frequency"] == "weekly"
    assert ok.json()["schedule"]["next_run_at"]

    removed = client.delete("/api/v1/reports/defs/rep_bug_summary/schedule",
                            headers=auth_header("harsha.varlani@flynava.ai"))
    assert removed.status_code == 200
    assert removed.json()["status"] == "unscheduled"


def test_share_requires_owner_or_manager_and_notifies(client, auth_header):
    denied = client.post("/api/v1/reports/defs/rep_bug_summary/share",
                         headers=auth_header("manas.ankarla@flynava.ai"),
                         json={"user_ids": ["u_manas"]})
    assert denied.status_code == 403

    ok = client.post("/api/v1/reports/defs/rep_bug_summary/share",
                     headers=auth_header("harsha.varlani@flynava.ai"),
                     json={"user_ids": ["u_manas"]})
    assert ok.status_code == 200
    assert ok.json()["shared"] == ["u_manas"]
    notifs = client.get("/api/v1/notifications", headers=auth_header("manas.ankarla@flynava.ai")).json()
    assert any(n["type"] == "report_shared" for n in notifs)


def test_shared_tab_shows_up_for_recipient(client, auth_header):
    client.post("/api/v1/reports/defs/rep_bug_summary/share",
               headers=auth_header("harsha.varlani@flynava.ai"), json={"user_ids": ["u_manas"]})
    shared = client.get("/api/v1/reports/defs?tab=shared",
                        headers=auth_header("manas.ankarla@flynava.ai")).json()
    assert any(r["report_id"] == "rep_bug_summary" for r in shared)


def test_send_preview_mode_without_smtp(client, auth_header):
    r = client.post("/api/v1/reports/defs/rep_bug_summary/send",
                    headers=auth_header("harsha.varlani@flynava.ai"),
                    json={"recipients": ["manas.ankarla@flynava.ai"]})
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "preview"
    run = client.get(f"/api/v1/reports/runs/{body['run_id']}",
                     headers=auth_header("harsha.varlani@flynava.ai")).json()
    assert run["delivery"]["status"] == "preview"


def test_send_requires_level_2(client, auth_header):
    denied = client.post("/api/v1/reports/defs/rep_bug_summary/send",
                         headers=auth_header("manas.ankarla@flynava.ai"),
                         json={"recipients": ["x@flynava.ai"]})
    assert denied.status_code == 403


def test_export_csv_increments_downloads(client, auth_header):
    headers = auth_header("harsha.varlani@flynava.ai")
    run_id = client.post("/api/v1/reports/defs/rep_bug_summary/run", headers=headers,
                         json={}).json()["run_id"]
    before = client.get("/api/v1/reports/defs/rep_bug_summary", headers=headers).json()["downloads"]
    csv_resp = client.get(f"/api/v1/reports/runs/{run_id}/export?fmt=csv", headers=headers)
    assert csv_resp.status_code == 200
    assert "text/csv" in csv_resp.headers["content-type"]
    after = client.get("/api/v1/reports/defs/rep_bug_summary", headers=headers).json()["downloads"]
    assert after == before + 1

    xls_resp = client.get(f"/api/v1/reports/runs/{run_id}/export?fmt=xls", headers=headers)
    assert xls_resp.status_code == 200
    assert "ms-excel" in xls_resp.headers["content-type"]

    bad = client.get(f"/api/v1/reports/runs/{run_id}/export?fmt=pdf", headers=headers)
    assert bad.status_code == 400


def test_delete_def_owner_or_super_admin_only(client, auth_header):
    denied = client.delete("/api/v1/reports/defs/rep_bug_summary",
                           headers=auth_header("manas.ankarla@flynava.ai"))
    assert denied.status_code == 403

    ok = client.delete("/api/v1/reports/defs/rep_bug_summary",
                       headers=auth_header("harsha.varlani@flynava.ai"))
    assert ok.status_code == 200
    gone = client.get("/api/v1/reports/defs/rep_bug_summary", headers=auth_header("admin@flynava.ai"))
    assert gone.status_code == 404


def test_saved_views_crud_and_per_user_isolation(client, auth_header):
    manas = auth_header("manas.ankarla@flynava.ai")
    created = client.post("/api/v1/reports/views", headers=manas,
                          json={"name": "My QA View", "filters": {"domain": "qa"}})
    assert created.status_code == 200
    view_id = created.json()["view_id"]

    mine = client.get("/api/v1/reports/views", headers=manas).json()
    assert any(v["view_id"] == view_id for v in mine)

    others = client.get("/api/v1/reports/views", headers=auth_header("harsha.varlani@flynava.ai")).json()
    assert not any(v["view_id"] == view_id for v in others)

    deleted = client.delete(f"/api/v1/reports/views/{view_id}", headers=manas)
    assert deleted.status_code == 200
    missing = client.delete(f"/api/v1/reports/views/{view_id}", headers=manas)
    assert missing.status_code == 404


def test_meta_hides_confidential_kinds_from_low_level_employee(client, auth_header):
    employee_meta = client.get("/api/v1/reports/meta", headers=auth_header("manas.ankarla@flynava.ai")).json()
    employee_kinds = {k["kind"] for k in employee_meta["section_kinds"]}
    assert "payroll_summary" not in employee_kinds

    manager_meta = client.get("/api/v1/reports/meta",
                              headers=auth_header("harsha.varlani@flynava.ai")).json()
    manager_kinds = {k["kind"] for k in manager_meta["section_kinds"]}
    assert "payroll_summary" in manager_kinds


def test_templates_endpoint_returns_catalog(client, auth_header):
    r = client.get("/api/v1/reports/templates", headers=auth_header("admin@flynava.ai"))
    assert r.status_code == 200
    assert len(r.json()) >= 10
