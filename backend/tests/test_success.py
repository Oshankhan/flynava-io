import datetime as dt

from app.services import success as success_service
from app.services.success_seed import seed_success


def _current_month() -> str:
    return dt.datetime.now(dt.timezone.utc).strftime("%Y-%m")


# --- Payload shape ---
def test_central_shape(client, auth_header):
    r = client.get("/api/v1/success/central", headers=auth_header("admin@flynava.ai"))
    assert r.status_code == 200
    body = r.json()
    assert body["month"] == _current_month()
    assert len(body["cards"]) == 4
    assert "visitors" in body["charts"]
    assert "progress" in body["charts"]
    assert len(body["tables"]["timeline"]) == 4
    assert len(body["tables"]["mini_cards"]) == 6
    assert body["last_updated"]


def test_organization_shape(client, auth_header):
    r = client.get("/api/v1/success/organization", headers=auth_header("admin@flynava.ai"))
    assert r.status_code == 200
    body = r.json()
    assert len(body["cards"]) == 5
    assert "headcount_trend" in body["charts"]
    assert "dept_headcount" in body["charts"]
    assert "demographics" in body["charts"]
    assert len(body["tables"]["top_departments"]) == 4


def test_marketing_shape(client, auth_header):
    r = client.get("/api/v1/success/marketing", headers=auth_header("admin@flynava.ai"))
    assert r.status_code == 200
    body = r.json()
    assert len(body["cards"]) == 5
    assert body["tables"]["leads_by_source"]
    assert body["tables"]["top_campaigns"]
    assert body["tables"]["channels"]


def test_finance_shape(client, auth_header):
    r = client.get("/api/v1/success/finance", headers=auth_header("admin@flynava.ai"))
    assert r.status_code == 200
    body = r.json()
    assert len(body["cards"]) == 3
    assert len(body["tables"]["financial_summary"]) == 5
    assert body["tables"]["revenue_segments"]
    assert body["tables"]["expense_breakdown"]


def test_startup_shape(client, auth_header):
    r = client.get("/api/v1/success/startup", headers=auth_header("admin@flynava.ai"))
    assert r.status_code == 200
    body = r.json()
    assert len(body["cards"]) == 5
    assert len(body["tables"]["kpi_overview"]) == 5
    assert "dau_trend" in body["charts"]


def test_operations_shape(client, auth_header):
    r = client.get("/api/v1/success/operations", headers=auth_header("admin@flynava.ai"))
    assert r.status_code == 200
    body = r.json()
    assert len(body["cards"]) == 5
    assert body["tables"]["by_status"]
    assert body["tables"]["by_priority"]
    assert body["tables"]["top_processes"]
    assert len(body["tables"]["efficiency"]) == 4


# --- Month filter + true month-over-month delta ---
def test_month_filter_and_mom_delta(client, auth_header, db):
    cur = _current_month()
    prev = success_service.prev_month(cur)
    r_cur = client.get(f"/api/v1/success/organization?month={cur}",
                      headers=auth_header("admin@flynava.ai")).json()
    r_prev = client.get(f"/api/v1/success/organization?month={prev}",
                       headers=auth_header("admin@flynava.ai")).json()
    assert r_cur["month"] == cur
    assert r_prev["month"] == prev

    cur_doc = db.org_monthly.find_one({"month": cur})
    prev_doc = db.org_monthly.find_one({"month": prev})
    headcount_card = next(c for c in r_cur["cards"] if c["id"] == "headcount")
    expected_delta = round(
        (cur_doc["headcount"] - prev_doc["headcount"]) / prev_doc["headcount"] * 100, 1)
    assert headcount_card["value"] == cur_doc["headcount"]
    assert headcount_card["delta_pct"] == expected_delta


# --- Central custom range ---
def test_central_custom_range_bounds_visitor_points(client, auth_header):
    today = dt.datetime.now(dt.timezone.utc).date()
    d_from = (today - dt.timedelta(days=5)).isoformat()
    d_to = today.isoformat()
    r = client.get(f"/api/v1/success/central?from={d_from}&to={d_to}",
                  headers=auth_header("admin@flynava.ai"))
    assert r.status_code == 200
    body = r.json()
    assert body["period"] == {"from": d_from, "to": d_to}
    points = body["charts"]["visitors"]["points"]
    assert points
    assert all(d_from <= p["t"] <= d_to for p in points)


# --- Finance yearly granularity ---
def test_finance_yearly_sums_twelve_months(client, auth_header, db):
    cur = _current_month()
    months = success_service.months_back(cur, 12)
    rows = list(db.finance_monthly.find({"month": {"$in": months}}))
    expected_revenue = sum(r["revenue"] for r in rows)
    latest = rows[-1] if rows else None

    r = client.get("/api/v1/success/finance?granularity=yearly",
                  headers=auth_header("admin@flynava.ai"))
    assert r.status_code == 200
    body = r.json()
    summary = {row["metric"]: row for row in body["tables"]["financial_summary"]}
    assert summary["Total Revenue"]["current"] == expected_revenue

    ratio_card = next(c for c in body["cards"] if c["id"] == "current_ratio")
    assert ratio_card["value"] == (latest.get("current_ratio") if latest else None)


def test_finance_yearly_omits_delta_without_full_prior_year(client, auth_header):
    # Seed only covers 13 months, so the prior 12-month window (13-24 months
    # back) is never fully populated — summing a partial window against a
    # full one would produce a misleading "change"; it must be omitted
    # instead of shown.
    r = client.get("/api/v1/success/finance?granularity=yearly",
                  headers=auth_header("admin@flynava.ai"))
    assert r.status_code == 200
    body = r.json()
    net_cash_flow_card = next(c for c in body["cards"] if c["id"] == "net_cash_flow")
    assert net_cash_flow_card["delta_pct"] is None
    summary = {row["metric"]: row for row in body["tables"]["financial_summary"]}
    assert summary["Total Revenue"]["previous"] is None
    assert summary["Total Revenue"]["change"] is None
    assert summary["Operating Margin"]["previous"] is None


def test_finance_bad_granularity_422(client, auth_header):
    r = client.get("/api/v1/success/finance?granularity=weekly",
                  headers=auth_header("admin@flynava.ai"))
    assert r.status_code == 422


# --- RBAC ---
def test_rbac_employee_denied_everywhere(client, auth_header):
    hdr = auth_header("manas.ankarla@flynava.ai")
    for tab in ["central", "organization", "marketing", "finance", "startup", "operations"]:
        r = client.get(f"/api/v1/success/{tab}", headers=hdr)
        assert r.status_code == 403, tab


def test_rbac_marketing_role(client, auth_header):
    hdr = auth_header("tanvi.gupta@flynava.ai")
    assert client.get("/api/v1/success/central", headers=hdr).status_code == 200
    assert client.get("/api/v1/success/marketing", headers=hdr).status_code == 200
    assert client.get("/api/v1/success/organization", headers=hdr).status_code == 403
    assert client.get("/api/v1/success/finance", headers=hdr).status_code == 403
    assert client.get("/api/v1/success/startup", headers=hdr).status_code == 403
    assert client.get("/api/v1/success/operations", headers=hdr).status_code == 403


def test_rbac_hr_role(client, auth_header):
    hdr = auth_header("hr@flynava.ai")
    assert client.get("/api/v1/success/organization", headers=hdr).status_code == 200
    assert client.get("/api/v1/success/central", headers=hdr).status_code == 200
    # hr role has operations:"read" per MATRIX, but hr's department (hr) doesn't
    # cover the operations module — department gating denies this now.
    assert client.get("/api/v1/success/operations", headers=hdr).status_code == 403
    assert client.get("/api/v1/success/marketing", headers=hdr).status_code == 403
    assert client.get("/api/v1/success/finance", headers=hdr).status_code == 403
    assert client.get("/api/v1/success/startup", headers=hdr).status_code == 403


def test_rbac_investor_multi_module(client, auth_header):
    hdr = auth_header("investor@flynava.ai")
    assert client.get("/api/v1/success/central", headers=hdr).status_code == 200
    assert client.get("/api/v1/success/marketing", headers=hdr).status_code == 200
    assert client.get("/api/v1/success/finance", headers=hdr).status_code == 200
    assert client.get("/api/v1/success/startup", headers=hdr).status_code == 200
    assert client.get("/api/v1/success/operations", headers=hdr).status_code == 200
    assert client.get("/api/v1/success/organization", headers=hdr).status_code == 403


def test_rbac_leadership_sees_everything(client, auth_header):
    hdr = auth_header("leadership@flynava.ai")
    for tab in ["central", "organization", "marketing", "finance", "startup", "operations"]:
        assert client.get(f"/api/v1/success/{tab}", headers=hdr).status_code == 200, tab


# --- Validation ---
def test_bad_month_format_422(client, auth_header):
    r = client.get("/api/v1/success/organization?month=2026-7",
                  headers=auth_header("admin@flynava.ai"))
    assert r.status_code == 422


def test_custom_range_requires_both_bounds(client, auth_header):
    r = client.get("/api/v1/success/central?from=2026-07-01",
                  headers=auth_header("admin@flynava.ai"))
    assert r.status_code == 422


# --- Seeding idempotency ---
def test_seed_success_idempotent(db):
    before = db.org_monthly.count_documents({})
    seed_success(db, dt.datetime.now(dt.timezone.utc))
    after = db.org_monthly.count_documents({})
    assert before == after
