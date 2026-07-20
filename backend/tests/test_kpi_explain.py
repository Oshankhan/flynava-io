import pytest

from app.kpi import engine

FN_KPI_IDS = [
    "fin_revenue_mtd", "fin_burn_rate", "fin_ar_over_60",
    "fin_ar_days", "hr_headcount", "hr_absenteeism", "hr_late_rate",
    "pd_bug_resolution_days", "pd_reopen_rate", "mkt_contact_coverage",
]


@pytest.mark.parametrize("kpi_id", FN_KPI_IDS)
def test_fn_kpi_explain_matches_live_value_and_has_full_envelope(
    client, auth_header, db, kpi_id
):
    """Every FN-KPIs.docx-derived KPI: explain's headline value matches a
    fresh engine.compute(), and the full AI envelope is present — same
    contract as the original 8 live KPIs' explainers."""
    d = db.kpi_defs.find_one({"kpi_id": kpi_id})
    expected_value = engine.compute(db, d)

    r = client.get(f"/api/v1/kpis/{kpi_id}/explain",
                   headers=auth_header("leadership@flynava.ai"))
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["value"] == expected_value
    assert body["formula_text"]
    assert body["computation"]
    for key in ("answer", "reason", "recommended_action", "confidence", "ai_provider"):
        assert body[key]
    assert body["confidence"] in {"Low", "Medium", "High"}


def test_explain_matches_live_computation(client, auth_header, db):
    active_projects = list(db.projects.find({"status": "active"}))
    expected_value = round(
        sum(p.get("progress", 0) for p in active_projects) / len(active_projects), 2
    )

    r = client.get("/api/v1/kpis/ops_project_completion/explain",
                   headers=auth_header("leadership@flynava.ai"))
    assert r.status_code == 200
    body = r.json()
    assert body["value"] == expected_value
    assert str(expected_value) in body["computation"]
    assert len(body["evidence"]) == len(active_projects)
    assert body["source"]["collection"] == "projects"
    for key in ("answer", "reason", "recommended_action", "confidence", "ai_provider"):
        assert body[key]
    assert body["confidence"] in {"Low", "Medium", "High"}


def test_explain_open_bugs_evidence_matches_query(client, auth_header, db):
    open_q = {"wp_type": {"$regex": "bug", "$options": "i"},
              "status": {"$nin": ["Closed", "Rejected", "Resolved"]}}
    expected = db.tasks.count_documents(open_q)

    r = client.get("/api/v1/kpis/pd_open_bugs/explain",
                   headers=auth_header("leadership@flynava.ai"))
    assert r.status_code == 200
    body = r.json()
    assert body["value"] == expected
    assert all(e["kind"] == "bug" for e in body["evidence"])


def test_explain_static_kpi_discloses_demo_placeholder(client, auth_header):
    # fin_revenue_mtd/hr_headcount etc. are now live-computed — fin_gross_margin
    # stays "static" (no ERP connected) so it's still a valid demo-disclosure case.
    r = client.get("/api/v1/kpis/fin_gross_margin/explain",
                   headers=auth_header("leadership@flynava.ai"))
    assert r.status_code == 200
    body = r.json()
    assert body["source"]["live"] is False
    assert body["source"]["system"] == "None (demo)"
    assert "not connected" in body["source"]["note"]
    assert body["evidence"] == []


def test_explain_requires_department_access(client, auth_header):
    # employee in the hr department has no access to operations KPIs
    denied = client.get("/api/v1/kpis/ops_project_completion/explain",
                        headers=auth_header("chandrakala.t@flynava.ai"))
    assert denied.status_code == 403

    # but does have access to hr's own (static) KPIs
    ok = client.get("/api/v1/kpis/hr_headcount/explain",
                    headers=auth_header("chandrakala.t@flynava.ai"))
    assert ok.status_code == 200


def test_explain_ar_over_60_evidence_are_invoices_past_due(client, auth_header, db):
    import datetime as dt
    db.project_invoices.insert_one({
        "invoice_id": "inv_test_old", "project_id": "proj_kq", "number": "INV-TEST-OLD",
        "date": "2026-01-01", "due_date": (dt.date.today() - dt.timedelta(days=90)).isoformat(),
        "amount": 5000, "currency": "USD", "status": "overdue", "description": "test",
    })
    r = client.get("/api/v1/kpis/fin_ar_over_60/explain",
                   headers=auth_header("leadership@flynava.ai"))
    assert r.status_code == 200
    body = r.json()
    assert body["value"] >= 5000
    assert all(e["kind"] == "invoice" for e in body["evidence"])
    assert any(e["id"] == "inv_test_old" for e in body["evidence"])


def test_explain_active_headcount_evidence_are_active_employees(client, auth_header, db):
    r = client.get("/api/v1/kpis/hr_headcount/explain",
                   headers=auth_header("leadership@flynava.ai"))
    assert r.status_code == 200
    body = r.json()
    assert body["value"] == db.employees.count_documents({"status": "active"})
    assert all(e["kind"] == "employee" for e in body["evidence"])


def test_explain_bug_reopen_rate_discloses_journal_verification(client, auth_header, db):
    db.tasks.insert_one({
        "source_system": "openproject", "source_id": "j1", "wp_type": "Bug",
        "title": "Journal-verified reopen", "status": "Developed", "reopen_count": 1,
        "journal_synced_updated_at": "2026-06-01T00:00:00Z",
    })
    r = client.get("/api/v1/kpis/pd_reopen_rate/explain",
                   headers=auth_header("leadership@flynava.ai"))
    assert r.status_code == 200
    body = r.json()
    assert "journal" in body["formula_text"].lower()
    evidence = next(e for e in body["evidence"] if e["id"] == "j1")
    assert evidence["extra"]["journal_verified"] is True


def test_explain_bug_resolution_days_shows_journal_vs_proxy_source(client, auth_header, db):
    now = "2026-06-15T00:00:00Z"
    db.tasks.insert_one({
        "source_system": "openproject", "source_id": "j2", "wp_type": "Bug",
        "title": "Closed via journal", "status": "Closed",
        "created_at": "2026-06-01T00:00:00Z", "updated_at": now,
        "closed_at": "2026-06-05T00:00:00Z", "closed_by": "Alice",
    })
    r = client.get("/api/v1/kpis/pd_bug_resolution_days/explain",
                   headers=auth_header("leadership@flynava.ai"))
    assert r.status_code == 200
    body = r.json()
    evidence = next(e for e in body["evidence"] if e["id"] == "j2")
    assert evidence["extra"]["source"] == "journal"
    assert evidence["extra"]["closed_by"] == "Alice"
    assert evidence["extra"]["days_to_resolve"] == 4.0  # Jun 1 -> Jun 5, not Jun 15


def test_explain_404_for_unknown_kpi(client, auth_header):
    r = client.get("/api/v1/kpis/does_not_exist/explain",
                   headers=auth_header("admin@flynava.ai"))
    assert r.status_code == 404


def test_explain_narrative_is_cached_until_value_changes(client, auth_header, db):
    r1 = client.get("/api/v1/kpis/ops_active_projects/explain",
                    headers=auth_header("leadership@flynava.ai"))
    assert r1.status_code == 200
    assert db.kpi_explanations.count_documents({"kpi_id": "ops_active_projects"}) == 1
    # Compare against the Mongo-stored (millisecond-precision) timestamp rather
    # than r1's raw JSON, since r1's is Python-native microsecond precision
    # computed before the round trip through Mongo's storage precision.
    first_generated_at = db.kpi_explanations.find_one(
        {"kpi_id": "ops_active_projects"})["generated_at"].isoformat()

    r2 = client.get("/api/v1/kpis/ops_active_projects/explain",
                    headers=auth_header("leadership@flynava.ai"))
    assert r2.status_code == 200
    assert r2.json()["generated_at"] == first_generated_at  # cache hit, no regeneration
    assert db.kpi_explanations.count_documents({"kpi_id": "ops_active_projects"}) == 1

    # underlying data changes -> value changes -> narrative regenerates
    db.projects.insert_one({"project_id": "px_extra", "name": "Extra Co", "status": "active",
                            "progress": 10, "expected_progress": 50})
    r3 = client.get("/api/v1/kpis/ops_active_projects/explain",
                    headers=auth_header("leadership@flynava.ai"))
    assert r3.json()["value"] == engine.compute(db, db.kpi_defs.find_one(
        {"kpi_id": "ops_active_projects"}))
    assert r3.json()["generated_at"] != first_generated_at
