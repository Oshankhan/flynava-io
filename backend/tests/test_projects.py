"""Client projects: board list, detail, creation (L3/L4), editable stages
(add/delete L3/L4, update L2+), member add (L2+) + project_added
notifications, project edit (L3/L4), and the activity feed."""
from __future__ import annotations


def test_list_scoped_by_membership_for_l1(client, auth_header):
    # Manas (Python dev) is on the KQ project via team_python
    r = client.get("/api/v1/projects", headers=auth_header("manas.ankarla@flynava.ai"))
    assert r.status_code == 200
    codes = {p["code"] for p in r.json()}
    assert "KQ" in codes
    assert "WY" not in codes  # Oman is marketing-only right now


def test_list_shows_all_for_l3(client, auth_header):
    r = client.get("/api/v1/projects", headers=auth_header("harsha.varlani@flynava.ai"))
    assert r.status_code == 200
    codes = {p["code"] for p in r.json()}
    assert {"KQ", "WY", "SV"} <= codes


def test_project_summary_shape(client, auth_header):
    r = client.get("/api/v1/projects", headers=auth_header("admin@flynava.ai"))
    kq = next(p for p in r.json() if p["code"] == "KQ")
    for key in ("project_id", "code", "name", "client", "status", "description",
                "engagement", "priority", "start_date", "due_date", "project_manager",
                "current_stage", "current_stage_name", "progress", "members",
                "member_count", "bug_count", "task_count", "open_tasks"):
        assert key in kq
    assert kq["bug_count"] == 40
    assert kq["open_tasks"] == 12
    assert kq["project_manager"]["name"] == "Animesh Singh"
    assert kq["status"] == "active"
    assert kq["engagement"] == "Existing Client - Production Support"
    assert kq["logo"] == "/logos/kq.png"


def test_get_project_detail(client, auth_header):
    r = client.get("/api/v1/projects/proj_kq", headers=auth_header("murugan.p@flynava.ai"))
    assert r.status_code == 200
    body = r.json()
    assert body["code"] == "KQ"
    assert len(body["bugs"]) == 40
    assert len(body["stages"]) == 6
    assert body["stages"][0]["key"] == "initiation"
    assert body["stages"][0]["status"] == "done"
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
    assert body["status"] == "planning"
    assert "u_manas" in body["member_ids"]
    assert "u_harsha" in body["member_ids"]  # creator auto-added


def test_patch_project_requires_l3(client, auth_header):
    denied = client.patch("/api/v1/projects/proj_om", headers=auth_header("tanvi.gupta@flynava.ai"),
                          json={"priority": "High"})
    assert denied.status_code == 403

    ok = client.patch("/api/v1/projects/proj_om", headers=auth_header("meghna.mehra@flynava.ai"),
                      json={"priority": "High", "description": "Updated description"})
    assert ok.status_code == 200
    body = ok.json()
    assert body["priority"] == "High"
    assert body["description"] == "Updated description"


def test_add_stage_requires_l3_and_recomputes_progress(client, auth_header, db):
    denied = client.post("/api/v1/projects/proj_om/stages",
                         headers=auth_header("tanvi.gupta@flynava.ai"),
                         json={"key": "requirements", "name": "Requirements"})
    assert denied.status_code == 403

    before = db.projects.find_one({"project_id": "proj_om"})["progress"]
    ok = client.post("/api/v1/projects/proj_om/stages",
                     headers=auth_header("meghna.mehra@flynava.ai"),
                     json={"key": "requirements", "name": "Requirements",
                           "description": "Gather requirements", "status": "pending",
                           "progress": 0})
    assert ok.status_code == 200
    body = ok.json()
    stage_keys = [s["key"] for s in body["stages"]]
    assert "requirements" in stage_keys
    assert len(body["stages"]) == 3  # client_acquisition + rfp_proposal + new one
    # adding a 0%-progress stage pulls the mean down from the pre-add value
    assert body["progress"] <= before


def test_add_stage_duplicate_key_rejected(client, auth_header):
    r = client.post("/api/v1/projects/proj_om/stages",
                    headers=auth_header("meghna.mehra@flynava.ai"),
                    json={"key": "client_acquisition", "name": "Dup"})
    assert r.status_code == 400


def test_patch_stage_allows_l2_and_recomputes(client, auth_header):
    # murugan (L2, python lead) is on KQ — team leads may update stage progress
    ok = client.patch("/api/v1/projects/proj_kq/stages/development",
                     headers=auth_header("murugan.p@flynava.ai"),
                     json={"progress": 100, "status": "done"})
    assert ok.status_code == 200
    body = ok.json()
    dev = next(s for s in body["stages"] if s["key"] == "development")
    assert dev["progress"] == 100
    assert dev["status"] == "done"
    # initiation(100) + planning(100) + development(100) + testing/deployment/closure(0) = 300/6
    assert body["progress"] == 50
    # current_stage advances to the next non-done stage
    assert body["current_stage"] == "testing"


def test_patch_stage_denied_for_l1(client, auth_header):
    denied = client.patch("/api/v1/projects/proj_kq/stages/development",
                          headers=auth_header("manas.ankarla@flynava.ai"),
                          json={"progress": 80})
    assert denied.status_code == 403


def test_patch_stage_unknown_key_404(client, auth_header):
    r = client.patch("/api/v1/projects/proj_kq/stages/not_a_stage",
                     headers=auth_header("murugan.p@flynava.ai"),
                     json={"progress": 50})
    assert r.status_code == 404


def test_delete_stage_requires_l3_and_recomputes(client, auth_header):
    denied = client.delete("/api/v1/projects/proj_sv/stages/go_live",
                           headers=auth_header("soochana.byaravalli@flynava.ai"))
    assert denied.status_code == 403

    ok = client.delete("/api/v1/projects/proj_sv/stages/go_live",
                       headers=auth_header("meghna.mehra@flynava.ai"))
    assert ok.status_code == 200
    body = ok.json()
    stage_keys = [s["key"] for s in body["stages"]]
    assert "go_live" not in stage_keys
    assert len(body["stages"]) == 4


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


def test_project_activity_feed(client, auth_header):
    h = auth_header("murugan.p@flynava.ai")
    client.patch("/api/v1/projects/proj_kq/stages/development", headers=h,
                json={"progress": 90})
    client.post("/api/v1/tasks", headers=h,
               json={"title": "Activity probe", "project_id": "proj_kq",
                     "stage": "development"})

    r = client.get("/api/v1/projects/proj_kq/activity", headers=h)
    assert r.status_code == 200
    actions = {a["action"] for a in r.json()}
    assert "stage_updated" in actions
    assert "task_created" in actions

    denied = client.get("/api/v1/projects/proj_om/activity",
                        headers=auth_header("manas.ankarla@flynava.ai"))
    assert denied.status_code == 403


def test_delete_project_requires_super_admin_and_cascades(client, auth_header, db):
    denied = client.delete("/api/v1/projects/proj_om",
                           headers=auth_header("harsha.varlani@flynava.ai"))
    assert denied.status_code == 403
    assert db.projects.find_one({"project_id": "proj_om"})

    ok = client.delete("/api/v1/projects/proj_om", headers=auth_header("admin@flynava.ai"))
    assert ok.status_code == 200
    assert ok.json() == {"deleted": "proj_om"}
    assert not db.projects.find_one({"project_id": "proj_om"})
    assert db.crm_contacts.count_documents({"project_id": "proj_om"}) == 0
    assert db.tasks.count_documents({"project_id": "proj_om"}) == 0


def test_delete_project_404(client, auth_header):
    r = client.delete("/api/v1/projects/does_not_exist", headers=auth_header("admin@flynava.ai"))
    assert r.status_code == 404


def test_documents_project_filter(client, auth_header):
    h = auth_header("murugan.p@flynava.ai")
    files = {"file": ("readme.txt", b"hello", "text/plain")}
    r = client.post("/api/v1/documents", headers=h,
                    data={"title": "KQ handover doc", "kind": "document",
                         "project_id": "proj_kq"}, files=files)
    assert r.status_code == 200
    assert r.json()["project_id"] == "proj_kq"

    scoped = client.get("/api/v1/documents?project_id=proj_kq", headers=h).json()
    assert any(d["title"] == "KQ handover doc" for d in scoped)
    unscoped = client.get("/api/v1/documents?project_id=proj_om", headers=h).json()
    assert not any(d["title"] == "KQ handover doc" for d in unscoped)
