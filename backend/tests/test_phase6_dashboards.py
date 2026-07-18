"""Phase 6 — all six role dashboards return populated KPI data."""
import pytest

DASHBOARDS = {
    "leadership": "leadership@flynava.ai",
    "manager": "harsha.varlani@flynava.ai",
    "hr": "hr@flynava.ai",
    "finance": "leadership@flynava.ai",   # finance dashboard: leadership has access
    "marketing": "tanvi.gupta@flynava.ai",
    "employee": "manas.ankarla@flynava.ai",
}


@pytest.mark.parametrize("key,email", DASHBOARDS.items())
def test_each_dashboard_renders_with_kpis(client, auth_header, key, email):
    r = client.get(f"/api/v1/dashboards/{key}", headers=auth_header(email))
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["key"] == key
    assert len(body["kpis"]) > 0  # every dashboard has at least one KPI


def test_finance_demo_values_present(client, auth_header):
    r = client.get("/api/v1/dashboards/finance",
                   headers=auth_header("leadership@flynava.ai"))
    kpis = {k["kpi_id"]: k for k in r.json()["kpis"]}
    assert kpis["fin_revenue_mtd"]["value"] == 432000
    assert kpis["fin_gross_margin"]["rag"] in {"green", "amber", "red"}


def test_recalculate_does_not_wipe_static_values(client, auth_header, db):
    # recalc runs the engine; genuinely-static KPIs (no integration wired yet)
    # must keep their seeded demo values rather than being overwritten with null.
    client.post("/api/v1/kpis/recalculate", headers=auth_header("admin@flynava.ai"))
    r = client.get("/api/v1/dashboards/hr", headers=auth_header("hr@flynava.ai"))
    kpis = {k["kpi_id"]: k for k in r.json()["kpis"]}
    assert kpis["hr_attrition"]["value"] == 6.4  # still static — no GreytHR connected
    # hr_headcount, by contrast, is now live-computed from the seeded employee
    # roster — recalc should replace the old demo value (128) with the real count.
    active = db.employees.count_documents({"status": "active"})
    assert kpis["hr_headcount"]["value"] == active
