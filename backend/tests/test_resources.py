from app.services import resource_mgmt


# --- Payload shape / RBAC ---
def test_dashboard_shape(client, auth_header):
    r = client.get("/api/v1/resources/dashboard", headers=auth_header("admin@flynava.ai"))
    assert r.status_code == 200
    body = r.json()
    assert {"kpi_cards", "team_capacity", "heatmap", "top_performers",
            "performance_matrix", "at_risk_resources", "project_resource_status",
            "work_lifecycle", "insights", "generated_at"} <= set(body)
    assert len(body["kpi_cards"]) == 6
    assert body["team_capacity"]
    assert body["heatmap"]
    assert len(body["work_lifecycle"]) == 5
    assert body["insights"]


def test_dashboard_requires_dept_head(client, auth_header):
    r = client.get("/api/v1/resources/dashboard", headers=auth_header("oshan.khan@flynava.ai"))
    assert r.status_code == 403


def test_dashboard_allows_manager(client, auth_header):
    r = client.get("/api/v1/resources/dashboard", headers=auth_header("harsha.varlani@flynava.ai"))
    assert r.status_code == 200


# --- Derivation sanity ---
def test_heatmap_rows_are_internally_consistent(client, auth_header):
    r = client.get("/api/v1/resources/dashboard", headers=auth_header("admin@flynava.ai"))
    body = r.json()
    for row in body["heatmap"]:
        assert row["tasks"] == row["pending"] + row["in_progress"] + row["overdue"] + row["completed"]
        assert row["open"] == row["pending"] + row["in_progress"]
        if row["workload_pct"] > 100:
            assert row["status"] == "overloaded"
        elif row["workload_pct"] < 70:
            assert row["status"] == "underutilized"
        else:
            assert row["status"] == "optimal"


def test_kpi_overloaded_count_matches_heatmap(client, auth_header):
    r = client.get("/api/v1/resources/dashboard", headers=auth_header("admin@flynava.ai"))
    body = r.json()
    overloaded_in_heatmap = sum(1 for row in body["heatmap"] if row["status"] == "overloaded")
    overloaded_kpi = next(c["value"] for c in body["kpi_cards"] if c["kpi_id"] == "res_overloaded")
    assert overloaded_kpi == overloaded_in_heatmap


def test_work_lifecycle_departments_and_sources(client, auth_header):
    r = client.get("/api/v1/resources/dashboard", headers=auth_header("admin@flynava.ai"))
    body = r.json()
    by_dept = {row["department"]: row for row in body["work_lifecycle"]}
    assert set(by_dept) == {"Engineering", "HR", "Finance", "Marketing", "Support"}
    assert by_dept["Engineering"]["source"] == "live"
    assert by_dept["Finance"]["source"] == "live"
    assert by_dept["Support"]["source"] == "demo"
    assert len(by_dept["Engineering"]["stages"]) == 6


def test_utilization_pct_formula():
    assert resource_mgmt._utilization_pct(open_count=4, overdue_count=0, target=4.0) == 100.0
    assert resource_mgmt._utilization_pct(open_count=0, overdue_count=2, target=4.0) == 75.0


def test_person_status_bands():
    assert resource_mgmt._person_status(101) == "overloaded"
    assert resource_mgmt._person_status(69.9) == "underutilized"
    assert resource_mgmt._person_status(85) == "optimal"
