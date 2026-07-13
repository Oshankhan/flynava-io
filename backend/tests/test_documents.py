"""Document Management: folder visibility, draft → submit → approve flow,
sharing ("allot"), starring, stats, and the seeded mockup dataset."""
from __future__ import annotations


def _upload(client, headers, title="Q2 Board MOM", kind="mom", folder_id="", project_id=""):
    return client.post(
        "/api/v1/documents",
        headers=headers,
        data={"title": title, "kind": kind, "folder_id": folder_id, "project_id": project_id},
        files={"file": ("mom.txt", b"Decisions: ship IO v1.", "text/plain")},
    )


# --- Seeded folders + dataset ---

def test_seeded_folders_and_document_counts(client, auth_header):
    r = client.get("/api/v1/folders", headers=auth_header("admin@flynava.ai"))
    assert r.status_code == 200
    by_name = {f["name"]: f for f in r.json()}
    assert by_name["Brand & Guidelines"]["document_count"] == 12
    assert by_name["Marketing Collaterals"]["document_count"] == 28
    assert by_name["Campaigns"]["document_count"] == 24


def test_folder_visibility_scoped_by_role_and_team(client, auth_header):
    # Manas (python dev, no marketing role/team) shouldn't see Campaigns
    manas = client.get("/api/v1/folders", headers=auth_header("manas.ankarla@flynava.ai")).json()
    names = {f["name"] for f in manas}
    assert "Brand & Guidelines" in names  # general folder — everyone
    assert "Campaigns" not in names

    # Tanvi (marketing lead) does see it
    tanvi = client.get("/api/v1/folders", headers=auth_header("tanvi.gupta@flynava.ai")).json()
    assert "Campaigns" in {f["name"] for f in tanvi}

    # L3 sees every folder regardless of access lists
    harsha = client.get("/api/v1/folders", headers=auth_header("harsha.varlani@flynava.ai")).json()
    assert len(harsha) == 8


def test_document_list_hides_docs_in_folders_the_user_cant_see(client, auth_header):
    manas = client.get("/api/v1/documents", headers=auth_header("manas.ankarla@flynava.ai")).json()
    assert not any(d["title"] == "Campaign Brief - Q3 2026" for d in manas)

    tanvi = client.get("/api/v1/documents", headers=auth_header("tanvi.gupta@flynava.ai")).json()
    assert any(d["title"] == "Campaign Brief - Q3 2026" for d in tanvi)


# --- Folder management (L3/L4 only) ---

def test_create_folder_requires_l3(client, auth_header):
    denied = client.post("/api/v1/folders", headers=auth_header("murugan.p@flynava.ai"),
                         json={"name": "Engineering Docs"})
    assert denied.status_code == 403

    ok = client.post("/api/v1/folders", headers=auth_header("harsha.varlani@flynava.ai"),
                     json={"name": "Engineering Docs", "category": "general",
                           "roles": ["team_lead"], "teams": ["team_python"]})
    assert ok.status_code == 200
    assert ok.json()["document_count"] == 0


def test_update_folder_access_requires_l3(client, auth_header):
    folders = client.get("/api/v1/folders", headers=auth_header("admin@flynava.ai")).json()
    reports = next(f for f in folders if f["name"] == "Reports")

    denied = client.patch(f"/api/v1/folders/{reports['folder_id']}",
                          headers=auth_header("manas.ankarla@flynava.ai"),
                          json={"description": "nope"})
    assert denied.status_code == 403

    ok = client.patch(f"/api/v1/folders/{reports['folder_id']}",
                      headers=auth_header("harsha.varlani@flynava.ai"),
                      json={"description": "Updated description"})
    assert ok.status_code == 200
    assert ok.json()["description"] == "Updated description"


# --- Upload / draft / submit / approve flow ---

def test_upload_lands_as_draft_visible_only_to_owner(client, auth_header):
    r = _upload(client, auth_header("manas.ankarla@flynava.ai"))
    assert r.status_code == 200, r.text
    doc = r.json()
    assert doc["status"] == "draft"
    assert "path" not in doc

    mine = client.get("/api/v1/documents", headers=auth_header("manas.ankarla@flynava.ai")).json()
    assert any(d["doc_id"] == doc["doc_id"] for d in mine)

    others = client.get("/api/v1/documents", headers=auth_header("harsha.varlani@flynava.ai")).json()
    assert not any(d["doc_id"] == doc["doc_id"] for d in others)


def test_submit_moves_draft_to_pending_and_notifies_managers(client, auth_header):
    doc_id = _upload(client, auth_header("manas.ankarla@flynava.ai")).json()["doc_id"]

    denied = client.post(f"/api/v1/documents/{doc_id}/submit",
                         headers=auth_header("harsha.varlani@flynava.ai"))
    assert denied.status_code == 403  # not the owner

    r = client.post(f"/api/v1/documents/{doc_id}/submit",
                    headers=auth_header("manas.ankarla@flynava.ai"))
    assert r.status_code == 200
    assert r.json()["status"] == "pending"

    unread = client.get("/api/v1/notifications/unread_count",
                        headers=auth_header("harsha.varlani@flynava.ai"))
    assert unread.json()["count"] >= 1

    again = client.post(f"/api/v1/documents/{doc_id}/submit",
                        headers=auth_header("manas.ankarla@flynava.ai"))
    assert again.status_code == 409


def test_approval_flow_requires_l3_notifies_uploader_and_audits(client, auth_header, db):
    doc_id = _upload(client, auth_header("manas.ankarla@flynava.ai")).json()["doc_id"]
    client.post(f"/api/v1/documents/{doc_id}/submit", headers=auth_header("manas.ankarla@flynava.ai"))

    denied = client.post(f"/api/v1/documents/{doc_id}/approve",
                         headers=auth_header("murugan.p@flynava.ai"), json={})
    assert denied.status_code == 403  # L2, not a manager

    r = client.post(f"/api/v1/documents/{doc_id}/approve",
                    headers=auth_header("harsha.varlani@flynava.ai"),
                    json={"comment": "Looks good"})
    assert r.status_code == 200
    assert r.json()["status"] == "approved"

    notes = client.get("/api/v1/notifications",
                       headers=auth_header("manas.ankarla@flynava.ai")).json()
    assert any(n["type"] == "approval_decision" for n in notes)
    assert db.audit_logs.count_documents({"action": "document_approved"}) == 1

    again = client.post(f"/api/v1/documents/{doc_id}/reject",
                        headers=auth_header("harsha.varlani@flynava.ai"), json={})
    assert again.status_code == 409


def test_approvals_tab_requires_manager(client, auth_header):
    doc_id = _upload(client, auth_header("manas.ankarla@flynava.ai")).json()["doc_id"]
    client.post(f"/api/v1/documents/{doc_id}/submit", headers=auth_header("manas.ankarla@flynava.ai"))

    denied = client.get("/api/v1/documents?tab=approvals",
                        headers=auth_header("manas.ankarla@flynava.ai"))
    assert denied.status_code == 403

    ok = client.get("/api/v1/documents?tab=approvals", headers=auth_header("harsha.varlani@flynava.ai"))
    assert ok.status_code == 200
    assert any(d["doc_id"] == doc_id for d in ok.json())


# --- Share ("allot"), star, stats ---

def test_share_requires_l3_and_notifies_appears_in_shared_tab(client, auth_header, db):
    doc_id = _upload(client, auth_header("harsha.varlani@flynava.ai")).json()["doc_id"]

    denied = client.post(f"/api/v1/documents/{doc_id}/share",
                         headers=auth_header("murugan.p@flynava.ai"),
                         json={"user_ids": ["u_manas"]})
    assert denied.status_code == 403

    ok = client.post(f"/api/v1/documents/{doc_id}/share",
                     headers=auth_header("harsha.varlani@flynava.ai"),
                     json={"user_ids": ["u_manas"]})
    assert ok.status_code == 200
    assert ok.json()["shared"] == ["u_manas"]
    assert db.notifications.find_one({"recipient_id": "u_manas", "type": "document_shared"})

    shared = client.get("/api/v1/documents?tab=shared",
                        headers=auth_header("manas.ankarla@flynava.ai")).json()
    assert any(d["doc_id"] == doc_id for d in shared)


def test_star_toggle(client, auth_header):
    doc_id = _upload(client, auth_header("manas.ankarla@flynava.ai")).json()["doc_id"]
    h = auth_header("manas.ankarla@flynava.ai")

    on = client.post(f"/api/v1/documents/{doc_id}/star", headers=h)
    assert on.json()["starred"] is True
    starred = client.get("/api/v1/documents?tab=starred", headers=h).json()
    assert any(d["doc_id"] == doc_id for d in starred)

    off = client.post(f"/api/v1/documents/{doc_id}/star", headers=h)
    assert off.json()["starred"] is False


def test_stats_shape_and_counts(client, auth_header, db):
    r = client.get("/api/v1/documents/stats", headers=auth_header("admin@flynava.ai"))
    assert r.status_code == 200
    body = r.json()
    for key in ("total_documents", "uploaded_this_month", "marketing_assets",
                "pending_approval", "total_downloads", "storage_used_bytes",
                "storage_quota_bytes"):
        assert key in body
    # drafts are owner-private even to managers — admin's counts exclude
    # everyone else's drafts, matching what /documents would actually list
    visible = {"uploaded_by": "u_ceo"}
    others_drafts_excluded = {"$or": [{"status": {"$ne": "draft"}}, visible]}
    assert body["total_documents"] == db.documents.count_documents(others_drafts_excluded)
    marketing_folders = [f["folder_id"] for f in db.folders.find({"category": "marketing"})]
    assert body["marketing_assets"] == db.documents.count_documents(
        {"folder_id": {"$in": marketing_folders}, **others_drafts_excluded})


# --- Download / delete / misc ---

def test_download_returns_file_and_logs_export(client, auth_header, db):
    doc_id = _upload(client, auth_header("hr@flynava.ai"), kind="policy").json()["doc_id"]
    r = client.get(f"/api/v1/documents/{doc_id}/download", headers=auth_header("hr@flynava.ai"))
    assert r.status_code == 200
    assert r.content == b"Decisions: ship IO v1."
    assert db.audit_logs.count_documents({"action": "document_downloaded"}) == 1


def test_download_404s_for_seeded_docs_with_no_stored_file(client, auth_header):
    docs = client.get("/api/v1/documents", headers=auth_header("admin@flynava.ai")).json()
    seeded = next(d for d in docs if d.get("source") == "seed")
    r = client.get(f"/api/v1/documents/{seeded['doc_id']}/download",
                   headers=auth_header("admin@flynava.ai"))
    assert r.status_code == 404


def test_delete_owner_draft_or_manager(client, auth_header):
    doc_id = _upload(client, auth_header("manas.ankarla@flynava.ai")).json()["doc_id"]

    denied = client.delete(f"/api/v1/documents/{doc_id}", headers=auth_header("murugan.p@flynava.ai"))
    assert denied.status_code == 403

    ok = client.delete(f"/api/v1/documents/{doc_id}", headers=auth_header("manas.ankarla@flynava.ai"))
    assert ok.status_code == 200


def test_invalid_kind_rejected(client, auth_header):
    r = _upload(client, auth_header("hr@flynava.ai"), kind="meme")
    assert r.status_code == 400
