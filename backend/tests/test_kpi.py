from app.kpi import engine


def test_operations_kpis_match_seeded_data(db):
    """Cross-checks the KPI engine's computed values against the actual
    seeded projects/tasks (derived here, not hardcoded) — robust to the
    exact seed roster/project mix changing over time.
    """
    import datetime as dt

    snap = {r["kpi_id"]: r for r in engine.run_all(db, "operations")}

    active_projects = list(db.projects.find({"status": "active"}))
    expected_completion = round(
        sum(p.get("progress", 0) for p in active_projects) / len(active_projects), 2
    ) if active_projects else 0.0
    assert snap["ops_project_completion"]["value"] == expected_completion
    assert snap["ops_active_projects"]["value"] == len(active_projects)

    expected_at_risk = sum(
        1 for p in active_projects
        if p.get("expected_progress") and p.get("progress", 0) < 0.7 * p["expected_progress"]
    )
    assert snap["ops_at_risk_projects"]["value"] == expected_at_risk

    total_tasks = db.tasks.count_documents({})
    done_tasks = db.tasks.count_documents(
        {"$or": [{"status": {"$in": ["Done", "Closed", "done", "closed", "Resolved"]}},
                 {"progress": 100}]})
    expected_task_completion = round(done_tasks / total_tasks * 100, 2) if total_tasks else 0.0
    assert snap["ops_task_completion"]["value"] == expected_task_completion

    today = dt.date.today().isoformat()
    expected_overdue = db.tasks.count_documents(
        {"due_date": {"$lt": today, "$ne": None}, "progress": {"$lt": 100}})
    assert snap["ops_overdue_tasks"]["value"] == expected_overdue


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
    fresh = {r["kpi_id"]: r for r in engine.run_all(db, "operations")}
    snap = engine.latest_snapshot(db, ["operations"])
    by_id = {r["kpi_id"]: r for r in snap}
    assert by_id["ops_project_completion"]["value"] == fresh["ops_project_completion"]["value"]
    assert by_id["ops_at_risk_projects"]["rag"] in {"red", "amber", "green"}


def test_kpis_endpoint_filters_by_role(client, auth_header, db):
    engine.run_all(db)  # all modules
    # marketing role: no operations access, but has marketing_sales
    r = client.get("/api/v1/kpis", headers=auth_header("tanvi.gupta@flynava.ai"))
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
