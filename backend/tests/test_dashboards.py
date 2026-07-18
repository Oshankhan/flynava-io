from app.kpi import engine


def _recalc(db):
    engine.run_all(db)


def test_list_dashboards_scoped_to_role(client, auth_header):
    r = client.get("/api/v1/dashboards", headers=auth_header("tanvi.gupta@flynava.ai"))
    assert r.status_code == 200
    keys = {d["key"] for d in r.json()}
    assert "marketing" in keys
    assert "finance" not in keys  # marketing role can't view finance dashboard


def test_dashboard_list_is_role_scoped_by_role_not_module(client, auth_header):
    # employee sees ONLY the employee dashboard (not leadership/manager/hr/...)
    emp = {d["key"] for d in client.get(
        "/api/v1/dashboards", headers=auth_header("manas.ankarla@flynava.ai")).json()}
    assert emp == {"employee"}
    # partner sees only partner; investor sees finance + investor
    partner = {d["key"] for d in client.get(
        "/api/v1/dashboards", headers=auth_header("partner@flynava.ai")).json()}
    assert partner == {"partner"}
    investor = {d["key"] for d in client.get(
        "/api/v1/dashboards", headers=auth_header("investor@flynava.ai")).json()}
    assert investor == {"finance", "investor"}
    # leadership sees all eight
    lead = {d["key"] for d in client.get(
        "/api/v1/dashboards", headers=auth_header("leadership@flynava.ai")).json()}
    assert len(lead) == 8


def test_employee_cannot_open_leadership_dashboard(client, auth_header):
    r = client.get("/api/v1/dashboards/leadership",
                   headers=auth_header("manas.ankarla@flynava.ai"))
    assert r.status_code == 403


def test_leadership_dashboard_has_kpis_and_projects(client, auth_header, db):
    _recalc(db)
    r = client.get("/api/v1/dashboards/leadership",
                   headers=auth_header("leadership@flynava.ai"))
    assert r.status_code == 200
    body = r.json()
    assert body["title"] == "Leadership"
    assert len(body["kpis"]) > 0
    assert len(body["projects"]) == 2  # proj_kq and proj_sv have status="active" in the new seed


def test_dashboard_access_denied_for_wrong_role(client, auth_header):
    r = client.get("/api/v1/dashboards/finance",
                   headers=auth_header("tanvi.gupta@flynava.ai"))
    assert r.status_code == 403


def test_unknown_dashboard_404(client, auth_header):
    r = client.get("/api/v1/dashboards/nope",
                   headers=auth_header("admin@flynava.ai"))
    assert r.status_code == 404


def _seed_op_project(db, source_id: str, name: str) -> None:
    db.projects.insert_one(
        {"source_system": "openproject", "source_id": source_id, "name": name, "status": "active"})


def test_dashboard_project_scope_overrides_ops_kpis(client, auth_header, db):
    _seed_op_project(db, "10", "Alpha")
    _seed_op_project(db, "20", "Beta")
    db.tasks.insert_many([
        {"source_system": "openproject", "source_id": "t1", "project_source_id": "10",
         "wp_type": "Task", "status": "Closed", "progress": 100},
        {"source_system": "openproject", "source_id": "t2", "project_source_id": "10",
         "wp_type": "Task", "status": "New", "progress": 0},
        {"source_system": "openproject", "source_id": "t3", "project_source_id": "20",
         "wp_type": "Task", "status": "New", "progress": 0},
    ])
    _recalc(db)

    def kv(body, kid):
        return next(k["value"] for k in body["kpis"] if k["kpi_id"] == kid)

    r_all = client.get("/api/v1/dashboards/leadership",
                       headers=auth_header("leadership@flynava.ai")).json()
    r_scoped = client.get("/api/v1/dashboards/leadership?project=10",
                          headers=auth_header("leadership@flynava.ai")).json()

    assert r_scoped["project"] == "10"
    # scoped to Alpha only: 1 of its 2 tasks is closed = 50%, distinct from
    # the unscoped value (which also includes the seed's own ops tasks)
    assert kv(r_scoped, "ops_task_completion") == 50.0
    assert kv(r_scoped, "ops_task_completion") != kv(r_all, "ops_task_completion")
    # project list narrows to just the selected project
    assert [p["name"] for p in r_scoped["projects"]] == ["Alpha"]
    assert len(r_all["projects"]) > 1
    # scoped ops KPIs drop out of the trend-chart series (their history is global)
    scoped_series_ids = {s["kpi_id"] for s in r_scoped["series"]}
    assert "ops_task_completion" not in scoped_series_ids


def test_dashboard_rejects_unknown_project(client, auth_header, db):
    r = client.get("/api/v1/dashboards/leadership?project=nope",
                   headers=auth_header("leadership@flynava.ai"))
    assert r.status_code == 404


def test_dashboard_project_scope_ignored_for_non_operations_kpis(client, auth_header, db):
    _seed_op_project(db, "10", "Alpha")
    _recalc(db)
    r_all = client.get("/api/v1/dashboards/leadership",
                       headers=auth_header("leadership@flynava.ai")).json()
    r_scoped = client.get("/api/v1/dashboards/leadership?project=10",
                          headers=auth_header("leadership@flynava.ai")).json()

    def kv(body, kid):
        return next(k["value"] for k in body["kpis"] if k["kpi_id"] == kid)

    # finance/hr KPIs aren't project-shaped -> unaffected by the selector
    assert kv(r_scoped, "hr_headcount") == kv(r_all, "hr_headcount")
    assert kv(r_scoped, "fin_revenue_mtd") == kv(r_all, "fin_revenue_mtd")
