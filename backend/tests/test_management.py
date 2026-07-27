import datetime as dt
from collections import Counter

from app.kpi.engine import CLOSED_BUG_STATUSES, _BUG_Q


def _direct_unresolved_count(db) -> int:
    bugs = list(db.tasks.find(_BUG_Q, {"status": 1}))
    return sum(1 for b in bugs if b.get("status") not in CLOSED_BUG_STATUSES)


# --- Payload shape ---
def test_bugs_shape(client, auth_header):
    r = client.get("/api/v1/management/bugs?preset=3m", headers=auth_header("admin@flynava.ai"))
    assert r.status_code == 200
    body = r.json()
    assert len(body["cards"]) == 5
    assert set(body["charts"]) == {"creation_trend", "by_status", "by_severity", "resolution_time_trend"}
    assert set(body["tables"]) == {"by_status", "by_module", "recent_unresolved", "recent_activity"}
    assert body["projects"]  # proj_kq has seeded bugs
    assert body["last_updated"]


def test_report_shape(client, auth_header):
    r = client.get("/api/v1/management/report?project=proj_kq",
                   headers=auth_header("admin@flynava.ai"))
    assert r.status_code == 200
    body = r.json()
    assert body["project"]["project_id"] == "proj_kq"
    assert body["project"]["rag"] in ("green", "amber", "red", "grey")
    assert len(body["stages"]) == 6
    assert body["stats"]["bugs_total"] >= 40
    assert "paid" in body["invoices"] and "rows" in body["invoices"]


def test_projects_selector(client, auth_header):
    r = client.get("/api/v1/management/projects", headers=auth_header("admin@flynava.ai"))
    assert r.status_code == 200
    ids = {p["project_id"] for p in r.json()}
    assert {"proj_kq", "proj_om", "proj_sv"} <= ids


# --- Window presets / validation ---
def test_window_presets_all_succeed(client, auth_header):
    hdr = auth_header("admin@flynava.ai")
    for preset in ["week", "month", "3m"]:
        r = client.get(f"/api/v1/management/bugs?preset={preset}", headers=hdr)
        assert r.status_code == 200, preset


def test_explicit_range_overrides_preset(client, auth_header):
    today = dt.date.today()
    d_from = (today - dt.timedelta(days=10)).isoformat()
    d_to = today.isoformat()
    r = client.get(f"/api/v1/management/bugs?from={d_from}&to={d_to}",
                   headers=auth_header("admin@flynava.ai"))
    assert r.status_code == 200
    assert r.json()["window"] == {"from": d_from, "to": d_to}


def test_bad_preset_422(client, auth_header):
    r = client.get("/api/v1/management/bugs?preset=year", headers=auth_header("admin@flynava.ai"))
    assert r.status_code == 422


def test_range_requires_both_bounds(client, auth_header):
    r = client.get("/api/v1/management/bugs?from=2026-07-01", headers=auth_header("admin@flynava.ai"))
    assert r.status_code == 422


def test_from_after_to_422(client, auth_header):
    r = client.get("/api/v1/management/bugs?from=2026-07-20&to=2026-07-01",
                   headers=auth_header("admin@flynava.ai"))
    assert r.status_code == 422


def test_report_missing_project_422(client, auth_header):
    r = client.get("/api/v1/management/report", headers=auth_header("admin@flynava.ai"))
    assert r.status_code == 422


def test_report_unknown_project_404(client, auth_header):
    r = client.get("/api/v1/management/report?project=nope",
                   headers=auth_header("admin@flynava.ai"))
    assert r.status_code == 404


def test_bugs_unknown_project_404(client, auth_header):
    r = client.get("/api/v1/management/bugs?project=nope", headers=auth_header("admin@flynava.ai"))
    assert r.status_code == 404


# --- Correctness against real data ---
def test_unresolved_matches_direct_count(client, auth_header, db):
    r = client.get("/api/v1/management/bugs?preset=3m", headers=auth_header("admin@flynava.ai"))
    body = r.json()
    unresolved_card = next(c for c in body["cards"] if c["id"] == "unresolved")
    assert unresolved_card["value"] == _direct_unresolved_count(db)
    assert unresolved_card["delta_pct"] is None  # no fabricated prior-window comparison


def test_project_filter_narrows_to_kq(client, auth_header, db):
    r_all = client.get("/api/v1/management/bugs?preset=3m", headers=auth_header("admin@flynava.ai")).json()
    r_kq = client.get("/api/v1/management/bugs?preset=3m&project=proj_kq",
                      headers=auth_header("admin@flynava.ai")).json()
    total_all = sum(row["count"] for row in r_all["tables"]["by_status"])
    total_kq = sum(row["count"] for row in r_kq["tables"]["by_status"])
    assert total_kq <= total_all
    assert total_kq >= 40  # all seeded KQ bugs belong to proj_kq


def test_severity_mapping_immediate_is_critical(client, auth_header, db):
    db.tasks.insert_one({
        "task_id": "bug_test_sev", "project_id": "proj_kq", "wp_type": "Bug",
        "title": "[Booking] Severity mapping test", "status": "Open", "priority": "Immediate",
        "created_at": dt.datetime.now(dt.timezone.utc),
    })
    r = client.get("/api/v1/management/bugs?preset=3m", headers=auth_header("admin@flynava.ai"))
    slices = {s["label"]: s["value"] for s in r.json()["charts"]["by_severity"]["slices"]}
    assert slices.get("Critical", 0) >= 1


def test_module_parsed_from_title_prefix(client, auth_header):
    r = client.get("/api/v1/management/bugs?preset=3m", headers=auth_header("admin@flynava.ai"))
    modules = {row["module"] for row in r.json()["tables"]["by_module"]}
    assert modules  # KQ bug titles are seeded as "[Module] description (#n)"


def test_created_resolved_counts_match_manual_recount(client, auth_header, db):
    r = client.get("/api/v1/management/bugs?preset=3m", headers=auth_header("admin@flynava.ai"))
    body = r.json()
    window = body["window"]
    d_from, d_to = window["from"], window["to"]

    bugs = list(db.tasks.find(_BUG_Q))
    expected_created = 0
    expected_resolved = 0
    for b in bugs:
        c = b.get("created_at")
        c_date = c.date().isoformat() if hasattr(c, "date") else None
        if c_date and d_from <= c_date <= d_to:
            expected_created += 1
        if b.get("status") in CLOSED_BUG_STATUSES:
            u = b.get("updated_at")
            u_date = u.date().isoformat() if hasattr(u, "date") else None
            if u_date and d_from <= u_date <= d_to:
                expected_resolved += 1

    created_card = next(c for c in body["cards"] if c["id"] == "created")
    resolved_card = next(c for c in body["cards"] if c["id"] == "resolved")
    assert created_card["value"] == expected_created
    assert resolved_card["value"] == expected_resolved


# --- RBAC (module matrix: operations/product_dev, non-"own") ---
def test_rbac_employee_denied(client, auth_header):
    hdr = auth_header("manas.ankarla@flynava.ai")
    assert client.get("/api/v1/management/bugs", headers=hdr).status_code == 403
    assert client.get("/api/v1/management/report?project=proj_kq", headers=hdr).status_code == 403


def test_rbac_marketing_denied(client, auth_header):
    hdr = auth_header("tanvi.gupta@flynava.ai")
    assert client.get("/api/v1/management/bugs", headers=hdr).status_code == 403


def test_rbac_hr_denied_operations_department_mismatch(client, auth_header):
    # hr role has operations:"read" (non-"own") per the RBAC matrix, but hr's
    # department (hr) doesn't cover the operations/product_dev modules —
    # department gating denies this even though the role alone would allow it.
    r = client.get("/api/v1/management/bugs", headers=auth_header("hr@flynava.ai"))
    assert r.status_code == 403


def test_rbac_investor_and_partner_allowed(client, auth_header):
    # investor/partner's department is "exec", which covers every module.
    assert client.get("/api/v1/management/bugs",
                      headers=auth_header("investor@flynava.ai")).status_code == 200
    assert client.get("/api/v1/management/bugs",
                      headers=auth_header("partner@flynava.ai")).status_code == 200


def test_rbac_leadership_allowed(client, auth_header):
    # leadership's department is "exec", which covers every module.
    assert client.get("/api/v1/management/bugs",
                      headers=auth_header("leadership@flynava.ai")).status_code == 200


def test_rbac_manager_department_gates_access(client, auth_header):
    # rakshitha.s is a manager in the fin department, which doesn't cover
    # operations/product_dev — no longer allowed just by role.
    assert client.get("/api/v1/management/bugs",
                      headers=auth_header("rakshitha.s@flynava.ai")).status_code == 403
    # harsha.varlani is a manager in the eng department, which does cover
    # operations/product_dev — an in-department manager still gets access.
    assert client.get("/api/v1/management/bugs",
                      headers=auth_header("harsha.varlani@flynava.ai")).status_code == 200
