def _upload(client, headers, title="Q2 Board MOM", kind="mom"):
    return client.post(
        "/api/v1/documents",
        headers=headers,
        data={"title": title, "kind": kind},
        files={"file": ("mom.txt", b"Decisions: ship IO v1.", "text/plain")},
    )


def test_upload_creates_pending_doc_and_notifies_approvers(client, auth_header):
    r = _upload(client, auth_header("employee@flynava.ai"))
    assert r.status_code == 200, r.text
    doc = r.json()
    assert doc["status"] == "pending"
    assert doc["kind"] == "mom"
    assert "path" not in doc  # storage path never exposed
    # an approver (hr) got an approval-request notification
    unread = client.get("/api/v1/notifications/unread_count",
                        headers=auth_header("hr@flynava.ai"))
    assert unread.json()["count"] >= 1


def test_approval_flow_notifies_uploader_and_audits(client, auth_header, db):
    doc_id = _upload(client, auth_header("employee@flynava.ai")).json()["doc_id"]
    r = client.post(f"/api/v1/documents/{doc_id}/approve",
                    headers=auth_header("leadership@flynava.ai"),
                    json={"comment": "Looks good"})
    assert r.status_code == 200
    assert r.json()["status"] == "approved"
    # uploader notified
    notes = client.get("/api/v1/notifications",
                       headers=auth_header("employee@flynava.ai")).json()
    assert any(n["type"] == "approval_decision" for n in notes)
    # audit trail written
    assert db.audit_logs.count_documents({"action": "document_approved"}) == 1
    # double-decide blocked
    again = client.post(f"/api/v1/documents/{doc_id}/reject",
                        headers=auth_header("leadership@flynava.ai"), json={})
    assert again.status_code == 409


def test_employee_cannot_approve(client, auth_header):
    doc_id = _upload(client, auth_header("manager@flynava.ai")).json()["doc_id"]
    r = client.post(f"/api/v1/documents/{doc_id}/approve",
                    headers=auth_header("employee@flynava.ai"), json={})
    assert r.status_code == 403


def test_download_returns_file_and_logs_export(client, auth_header, db):
    doc_id = _upload(client, auth_header("hr@flynava.ai"), kind="policy").json()["doc_id"]
    r = client.get(f"/api/v1/documents/{doc_id}/download",
                   headers=auth_header("hr@flynava.ai"))
    assert r.status_code == 200
    assert r.content == b"Decisions: ship IO v1."
    assert db.audit_logs.count_documents({"action": "document_downloaded"}) == 1


def test_invalid_kind_rejected(client, auth_header):
    r = _upload(client, auth_header("hr@flynava.ai"), kind="meme")
    assert r.status_code == 400
