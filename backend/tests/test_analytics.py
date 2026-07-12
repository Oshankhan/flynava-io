"""Phase D — L4 org-wide analytics over the audit_logs dataset."""
from __future__ import annotations


def test_analytics_requires_l4_role(client, auth_header):
    denied = client.get("/api/v1/analytics/summary",
                        headers=auth_header("harsha.varlani@flynava.ai"))
    assert denied.status_code == 403
    ok = client.get("/api/v1/analytics/summary", headers=auth_header("admin@flynava.ai"))
    assert ok.status_code == 200


def test_analytics_shape_and_counts(client, auth_header, db):
    h_emp = auth_header("manas.ankarla@flynava.ai")
    h_admin = auth_header("admin@flynava.ai")

    client.post("/api/v1/tasks", headers=h_emp, json={"title": "Analytics probe"})

    r = client.get("/api/v1/analytics/summary", headers=h_admin)
    assert r.status_code == 200
    body = r.json()
    for key in ("window_days", "total_actions", "actions_per_day", "by_action",
                "top_actors", "by_department", "integrations"):
        assert key in body

    assert body["total_actions"] > 0
    assert any(row["action"] == "api_call" for row in body["by_action"])
    assert any(a["user_id"] == "u_manas" for a in body["top_actors"])
    # AuditMiddleware attaches meta.department for resolved actors (Evan -> eng)
    assert any(d["department"] == "eng" for d in body["by_department"])
    today = db.audit_logs.find_one(sort=[("created_at", -1)])["created_at"].strftime("%Y-%m-%d")
    assert any(p["date"] == today for p in body["actions_per_day"])


def test_analytics_integrations_reflects_sync(client, auth_header, db):
    import datetime as dt
    db.integration_logs.insert_one({
        "source": "openproject", "run_at": dt.datetime.now(dt.timezone.utc),
        "records_fetched": 5, "records_processed": 5, "errors": [], "status": "ok",
    })
    r = client.get("/api/v1/analytics/summary", headers=auth_header("leadership@flynava.ai"))
    assert r.status_code == 200
    sources = {i["source"]: i for i in r.json()["integrations"]}
    assert sources["openproject"]["status"] == "ok"
    assert sources["openproject"]["records_processed"] == 5
