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
    assert len(body["projects"]) == 1  # only proj_sv has status="active" in the new seed


def test_dashboard_access_denied_for_wrong_role(client, auth_header):
    r = client.get("/api/v1/dashboards/finance",
                   headers=auth_header("tanvi.gupta@flynava.ai"))
    assert r.status_code == 403


def test_unknown_dashboard_404(client, auth_header):
    r = client.get("/api/v1/dashboards/nope",
                   headers=auth_header("admin@flynava.ai"))
    assert r.status_code == 404
