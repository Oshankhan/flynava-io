from app.core import rbac


def test_matrix_cells_match_prd():
    assert rbac.access_level("manager", "operations") == "team"
    assert rbac.access_level("employee", "finance") == rbac.NONE
    assert rbac.access_level("investor", "finance") == "summary"
    assert rbac.access_level("partner", "customer_support") == "sla"
    assert rbac.access_level("super_admin", "admin_panel") == "full"
    assert rbac.access_level("leadership", "admin_panel") == rbac.NONE


def test_has_access_and_accessible_modules():
    assert rbac.has_access("hr", "hr")
    assert not rbac.has_access("marketing", "finance")
    mods = rbac.accessible_modules("employee")
    assert "operations" in mods and "finance" not in mods


def test_users_endpoint_allows_hr_denies_employee(client, auth_header):
    from app.services.seed import USERS

    ok = client.get("/api/v1/users", headers=auth_header("hr@flynava.ai"))
    assert ok.status_code == 200
    assert len(ok.json()) == len(USERS)
    denied = client.get("/api/v1/users", headers=auth_header("manas.ankarla@flynava.ai"))
    assert denied.status_code == 403


def test_rbac_matrix_endpoint_super_admin_only(client, auth_header):
    ok = client.get("/api/v1/rbac/matrix", headers=auth_header("admin@flynava.ai"))
    assert ok.status_code == 200
    assert ok.json()["matrix"]["finance"]["investor"] == "summary"
    denied = client.get("/api/v1/rbac/matrix", headers=auth_header("harsha.varlani@flynava.ai"))
    assert denied.status_code == 403
