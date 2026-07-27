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


def test_department_allows_cross_cutting_modules_for_everyone():
    for dept in ["eng", "product", "mkt", "hr", "fin", "exec", None]:
        assert rbac.department_allows(dept, "awards")
        assert rbac.department_allows(dept, "ai_insights")


def test_department_allows_owned_modules_only_for_matching_department():
    assert rbac.department_allows("fin", "finance")
    assert rbac.department_allows("fin", "compliance")
    assert not rbac.department_allows("eng", "finance")
    assert not rbac.department_allows(None, "finance")
    # exec covers every module (super_admin/leadership/investor/partner)
    assert all(rbac.department_allows("exec", m) for m in rbac.MODULES)


def test_accessible_modules_for_user_gates_manager_by_department():
    eng_manager = {"role": "manager", "department": "eng"}
    fin_manager = {"role": "manager", "department": "fin"}
    mods = rbac.accessible_modules_for_user(eng_manager)
    assert "operations" in mods and "product_dev" in mods
    assert "finance" not in mods and "hr" not in mods and "marketing_sales" not in mods
    assert "finance" in rbac.accessible_modules_for_user(fin_manager)


def test_accessible_modules_for_user_exec_department_sees_everything():
    # super_admin's role already grants "full" on every module in MATRIX;
    # department=exec (which maps to every module) doesn't narrow that.
    super_admin = {"role": "super_admin", "department": "exec"}
    assert set(rbac.accessible_modules_for_user(super_admin)) == set(rbac.MODULES)


def test_accessible_modules_for_user_no_department_denies_owned_modules():
    no_dept = {"role": "manager", "department": None}
    mods = rbac.accessible_modules_for_user(no_dept)
    assert "finance" not in mods and "operations" not in mods
    assert "awards" in mods


def test_extra_marketing_role_grants_marketing_sales_outside_own_department():
    # A product-department manager holding an explicit extra "marketing"
    # role (e.g. Meghna Mehra, seeded to co-run marketing) must still see
    # marketing_sales even though department=product doesn't cover it —
    # the role's own home module bypasses the department gate.
    product_manager_plus_marketing = {
        "role": "manager", "roles": ["manager", "marketing"], "department": "product",
    }
    mods = rbac.accessible_modules_for_user(product_manager_plus_marketing)
    assert "marketing_sales" in mods
    assert "product_dev" in mods
    # still no finance/hr — those aren't the extra role's home module and
    # product department doesn't cover them either
    assert "finance" not in mods and "hr" not in mods


def test_hr_role_still_denied_operations_despite_home_module_bypass():
    # The home-module bypass is scoped to hr's own modules (hr, recruitment)
    # only — it must NOT reopen hr role's coarse "read" access to operations,
    # which is exactly the leak department gating closes.
    hr_user = {"role": "hr", "department": "hr"}
    mods = rbac.accessible_modules_for_user(hr_user)
    assert "hr" in mods and "recruitment" in mods
    assert "operations" not in mods
