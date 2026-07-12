"""Client projects: board list, detail, creation (L3/L4), stage advance
(L3/L4), member add (L2+) + project_added notifications."""
from __future__ import annotations


def test_list_scoped_by_membership_for_l1(client, auth_header):
    # Manas (Python dev) is on the KQ project via team_python
    r = client.get("/api/v1/projects", headers=auth_header("manas.ankarla@flynava.ai"))
    assert r.status_code == 200
    codes = {p["code"] for p in r.json()}
    assert "KQ" in codes
    assert "OM" not in codes  # Oman is marketing-only right now


def test_list_shows_all_for_l3(client, auth_header):
    r = client.get("/api/v1/projects", headers=auth_header("harsha.varlani@flynava.ai"))
    assert r.status_code == 200
    codes = {p["code"] for p in r.json()}
    assert {"KQ", "OM", "SV"} <= codes


def test_project_summary_shape(client, auth_header):
    r = client.get("/api/v1/projects", headers=auth_header("admin@flynava.ai"))
    kq = next(p for p in r.json() if p["code"] == "KQ")
    for key in ("project_id", "code", "name", "client", "status", "current_stage",
                "current_stage_name", "progress", "members", "member_count",
                "bug_count", "task_count"):
        assert key in kq
    assert kq["bug_count"] == 40


def test_get_project_detail(client, auth_header):
    r = client.get("/api/v1/projects/proj_kq", headers=auth_header("murugan.p@flynava.ai"))
    assert r.status_code == 200
    body = r.json()
    assert body["code"] == "KQ"
    assert len(body["bugs"]) == 40
    assert len(body["stages"]) == 8
    assert any(m["user_id"] == "u_murugan" for m in body["members"])


def test_get_project_detail_denied_for_non_member(client, auth_header):
    denied = client.get("/api/v1/projects/proj_om", headers=auth_header("manas.ankarla@flynava.ai"))
    assert denied.status_code == 403


def test_get_project_404(client, auth_header):
    r = client.get("/api/v1/projects/does_not_exist", headers=auth_header("admin@flynava.ai"))
    assert r.status_code == 404


def test_create_project_requires_l3(client, auth_header):
    denied = client.post("/api/v1/projects", headers=auth_header("murugan.p@flynava.ai"),
                         json={"code": "TST", "name": "Test Airways"})
    assert denied.status_code == 403

    ok = client.post("/api/v1/projects", headers=auth_header("harsha.varlani@flynava.ai"),
                     json={"code": "TST", "name": "Test Airways", "client": "Test Airways",
                           "team_ids": ["team_python"], "member_ids": ["u_manas"]})
    assert ok.status_code == 200
    body = ok.json()
    assert body["current_stage"] == "client_acquisition"
    assert body["status"] == "pipeline"
    assert "u_manas" in body["member_ids"]
    assert "u_harsha" in body["member_ids"]  # creator auto-added


def test_stage_advance_requires_l3(client, auth_header):
    denied = client.patch("/api/v1/projects/proj_om/stage",
                          headers=auth_header("tanvi.gupta@flynava.ai"),
                          json={"stage": "rfp_proposal"})
    assert denied.status_code == 403

    ok = client.patch("/api/v1/projects/proj_om/stage",
                      headers=auth_header("meghna.mehra@flynava.ai"),
                      json={"stage": "rfp_proposal"})
    assert ok.status_code == 200
    body = ok.json()
    assert body["current_stage"] == "rfp_proposal"
    done = {s["key"]: s["status"] for s in body["stages"]}
    assert done["client_acquisition"] == "done"
    assert done["rfp_proposal"] == "active"
    assert done["requirements"] == "pending"


def test_stage_advance_bad_key_rejected(client, auth_header):
    r = client.patch("/api/v1/projects/proj_om/stage",
                     headers=auth_header("meghna.mehra@flynava.ai"),
                     json={"stage": "not_a_stage"})
    assert r.status_code == 400


def test_add_members_requires_l2_and_notifies(client, auth_header, db):
    denied = client.post("/api/v1/projects/proj_kq/members",
                         headers=auth_header("manas.ankarla@flynava.ai"),
                         json={"member_ids": ["u_dinesh"]})
    assert denied.status_code == 403

    ok = client.post("/api/v1/projects/proj_kq/members",
                     headers=auth_header("murugan.p@flynava.ai"),
                     json={"member_ids": ["u_dinesh", "u_manas"]})
    assert ok.status_code == 200
    assert ok.json()["added"] == ["u_dinesh"]  # u_manas already a member
    assert db.notifications.find_one({"recipient_id": "u_dinesh", "type": "project_added"})
    assert not db.notifications.find_one({"recipient_id": "u_manas", "type": "project_added"})
