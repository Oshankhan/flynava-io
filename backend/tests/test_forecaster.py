import datetime as dt

from app.services import success as success_service
from app.services.forecaster_seed import FUTURE_MONTHS, months_forward, seed_forecaster


def _current_month() -> str:
    return dt.datetime.now(dt.timezone.utc).strftime("%Y-%m")


# --- Payload shape ---
def test_overview_shape(client, auth_header):
    r = client.get("/api/v1/forecaster/overview", headers=auth_header("admin@flynava.ai"))
    assert r.status_code == 200
    body = r.json()
    assert body["month"] == _current_month()
    assert len(body["cards"]) == 8
    assert set(body["panels"]) == {"revenue", "workforce", "costs", "cashflow", "analyzer"}
    assert isinstance(body["insights"], list) and body["insights"]
    assert isinstance(body["alerts"], list)
    assert len(body["forecast_cards"]) == 4
    assert body["forecast_label"]
    assert body["last_updated"]


def test_workforce_shape(client, auth_header):
    r = client.get("/api/v1/forecaster/workforce", headers=auth_header("admin@flynava.ai"))
    assert r.status_code == 200
    body = r.json()
    assert len(body["cards"]) == 4
    assert "actual" in body["charts"]["headcount_forecast"]
    assert "forecast" in body["charts"]["headcount_forecast"]
    assert body["charts"]["headcount_forecast"]["forecast"]
    assert body["tables"]["departments"]


def test_revenue_shape(client, auth_header):
    r = client.get("/api/v1/forecaster/revenue", headers=auth_header("admin@flynava.ai"))
    assert r.status_code == 200
    body = r.json()
    assert len(body["cards"]) == 3
    assert body["tables"]["actual_vs_forecast"]
    assert body["tables"]["revenue_segments"]


def test_cashflow_shape(client, auth_header):
    r = client.get("/api/v1/forecaster/cashflow", headers=auth_header("admin@flynava.ai"))
    assert r.status_code == 200
    body = r.json()
    assert len(body["cards"]) == 4
    assert body["charts"]["cash_in_vs_out"]["bars"]
    assert "actual" in body["charts"]["cash_balance_forecast"]


def test_costs_shape(client, auth_header):
    r = client.get("/api/v1/forecaster/costs", headers=auth_header("admin@flynava.ai"))
    assert r.status_code == 200
    body = r.json()
    assert len(body["cards"]) == 3
    assert body["tables"]["categories"]
    for row in body["tables"]["categories"]:
        assert "change_pct" in row


def test_analyzer_shape(client, auth_header):
    r = client.get("/api/v1/forecaster/analyzer", headers=auth_header("admin@flynava.ai"))
    assert r.status_code == 200
    body = r.json()
    assert len(body["cards"]) == 4
    assert body["charts"]["status_breakdown"]["slices"]
    assert "invoices" in body["tables"]


def test_analyzer_tolerates_projects_without_project_id(client, auth_header, db):
    # OpenProject-synced project docs are keyed by source_system/source_id,
    # not project_id — the analyzer's project-name lookup must not choke on them.
    db.projects.insert_one({"source_system": "openproject", "source_id": "999", "name": "Synced"})
    r = client.get("/api/v1/forecaster/analyzer", headers=auth_header("admin@flynava.ai"))
    assert r.status_code == 200


# --- Consistency with Indicator Of Success (same source collections) ---
def test_overview_matches_finance_and_organization_screens(client, auth_header, db):
    month = _current_month()
    fin_doc = db.finance_monthly.find_one({"month": month})
    org_doc = db.org_monthly.find_one({"month": month})

    overview = client.get("/api/v1/forecaster/overview",
                          headers=auth_header("admin@flynava.ai")).json()
    finance_screen = client.get("/api/v1/success/finance",
                               headers=auth_header("admin@flynava.ai")).json()
    org_screen = client.get("/api/v1/success/organization",
                           headers=auth_header("admin@flynava.ai")).json()

    revenue_card = next(c for c in overview["cards"] if c["id"] == "total_revenue")
    employees_card = next(c for c in overview["cards"] if c["id"] == "total_employees")
    finance_summary = {row["metric"]: row for row in finance_screen["tables"]["financial_summary"]}
    org_headcount_card = next(c for c in org_screen["cards"] if c["id"] == "headcount")

    assert revenue_card["value"] == fin_doc["revenue"] == finance_summary["Total Revenue"]["current"]
    assert employees_card["value"] == org_doc["headcount"] == org_headcount_card["value"]


# --- Month filter + true MoM delta ---
def test_month_filter_and_mom_delta(client, auth_header, db):
    cur = _current_month()
    prev = success_service.prev_month(cur)
    r_cur = client.get(f"/api/v1/forecaster/workforce?month={cur}",
                      headers=auth_header("admin@flynava.ai")).json()
    r_prev = client.get(f"/api/v1/forecaster/workforce?month={prev}",
                       headers=auth_header("admin@flynava.ai")).json()
    assert r_cur["month"] == cur
    assert r_prev["month"] == prev

    cur_doc = db.forecaster_monthly.find_one({"month": cur})
    prev_doc = db.forecaster_monthly.find_one({"month": prev})
    joiners_card = next(c for c in r_cur["cards"] if c["id"] == "joiners")
    expected_delta = round(
        (cur_doc["joiners"] - prev_doc["joiners"]) / prev_doc["joiners"] * 100, 1)
    assert joiners_card["value"] == cur_doc["joiners"]
    assert joiners_card["delta_pct"] == expected_delta


def test_bad_month_format_422(client, auth_header):
    r = client.get("/api/v1/forecaster/overview?month=2026-7",
                  headers=auth_header("admin@flynava.ai"))
    assert r.status_code == 422


# --- Forecast horizon ---
def test_forecast_months_exist(db):
    cur = _current_month()
    future = months_forward(cur, FUTURE_MONTHS)
    assert len(future) == FUTURE_MONTHS
    docs = list(db.forecaster_monthly.find({"month": {"$in": future}}))
    assert len(docs) == FUTURE_MONTHS
    for d in docs:
        assert d["headcount_forecast"] is not None
        assert d["forecast_revenue"] is not None
        assert d["forecast_expenses"] is not None
        assert d["forecast_profit"] == d["forecast_revenue"] - d["forecast_expenses"]


# --- Insights / alerts reference real data ---
def test_insights_and_alerts_present(client, auth_header, db):
    # Force an overdue invoice so the "Overdue Payments" alert is guaranteed.
    db.project_invoices.update_one(
        {"invoice_id": "inv_kq_02"},
        {"$set": {"status": "overdue", "due_date": "2026-05-30"}})
    r = client.get("/api/v1/forecaster/overview", headers=auth_header("admin@flynava.ai"))
    body = r.json()
    assert any("Revenue" in b for b in body["insights"])
    titles = {a["title"] for a in body["alerts"]}
    assert "Overdue Payments" in titles


# --- RBAC: whole module gated on finance (non-"own") ---
def test_rbac_employee_denied(client, auth_header):
    hdr = auth_header("manas.ankarla@flynava.ai")
    for tab in ["overview", "workforce", "revenue", "cashflow", "costs", "analyzer"]:
        assert client.get(f"/api/v1/forecaster/{tab}", headers=hdr).status_code == 403, tab


def test_rbac_hr_and_marketing_denied(client, auth_header):
    assert client.get("/api/v1/forecaster/overview",
                      headers=auth_header("hr@flynava.ai")).status_code == 403
    assert client.get("/api/v1/forecaster/overview",
                      headers=auth_header("tanvi.gupta@flynava.ai")).status_code == 403


def test_rbac_manager_and_investor_allowed(client, auth_header):
    assert client.get("/api/v1/forecaster/overview",
                      headers=auth_header("rakshitha.s@flynava.ai")).status_code == 200
    assert client.get("/api/v1/forecaster/overview",
                      headers=auth_header("investor@flynava.ai")).status_code == 200


def test_rbac_leadership_sees_everything(client, auth_header):
    hdr = auth_header("leadership@flynava.ai")
    for tab in ["overview", "workforce", "revenue", "cashflow", "costs", "analyzer"]:
        assert client.get(f"/api/v1/forecaster/{tab}", headers=hdr).status_code == 200, tab


# --- Seeding idempotency ---
def test_seed_forecaster_idempotent(db):
    before = db.forecaster_monthly.count_documents({})
    seed_forecaster(db, dt.datetime.now(dt.timezone.utc))
    after = db.forecaster_monthly.count_documents({})
    assert before == after
