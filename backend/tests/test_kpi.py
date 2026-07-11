from app.kpi import engine


def test_operations_kpis_match_seeded_data(db):
    snap = {r["kpi_id"]: r for r in engine.run_all(db, "operations")}

    # 2 active seed projects, progress 42 and 88 -> mean 65.0
    assert snap["ops_project_completion"]["value"] == 65.0
    # 3 tasks, 1 done -> 33.33%
    assert snap["ops_task_completion"]["value"] == 33.33
    # t2 overdue (progress 30, due 2020)
    assert snap["ops_overdue_tasks"]["value"] == 1
    # p_alpha 42 < 0.7*70 -> at risk; p_beta not
    assert snap["ops_at_risk_projects"]["value"] == 1
    assert snap["ops_active_projects"]["value"] == 2


def test_rag_status_directions():
    assert engine.rag_status(95, 90, "higher") == "green"
    assert engine.rag_status(80, 90, "higher") == "amber"
    assert engine.rag_status(50, 90, "higher") == "red"
    assert engine.rag_status(0, 0, "lower") == "green"
    assert engine.rag_status(5, 0, "lower") == "red"
    assert engine.rag_status(None, 90, "higher") == "grey"


def test_run_all_stores_kpi_values(db):
    engine.run_all(db, "operations")
    assert db.kpi_values.count_documents({"kpi_id": "ops_project_completion"}) == 1


def test_latest_snapshot_reads_without_recompute(db):
    engine.run_all(db, "operations")
    snap = engine.latest_snapshot(db, ["operations"])
    by_id = {r["kpi_id"]: r for r in snap}
    assert by_id["ops_project_completion"]["value"] == 65.0
    assert by_id["ops_at_risk_projects"]["rag"] in {"red", "amber", "green"}


def test_kpis_endpoint_filters_by_role(client, auth_header, db):
    engine.run_all(db)  # all modules
    # marketing role: no operations access, but has marketing_sales
    r = client.get("/api/v1/kpis", headers=auth_header("marketing@flynava.ai"))
    assert r.status_code == 200
    modules = {row["module"] for row in r.json()}
    assert "operations" not in modules
    assert "marketing_sales" in modules


def test_recalculate_requires_super_admin(client, auth_header):
    denied = client.post("/api/v1/kpis/recalculate",
                         headers=auth_header("leadership@flynava.ai"))
    assert denied.status_code == 403
    ok = client.post("/api/v1/kpis/recalculate",
                     headers=auth_header("admin@flynava.ai"))
    assert ok.status_code == 200
    assert len(ok.json()) > 0
