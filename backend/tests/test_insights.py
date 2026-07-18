import datetime as dt

import mongomock

from app.insights import engine as ie


def _run_detector(db, dept: str, finding_id: str, project: str | None = None) -> dict | None:
    for fid, _title, fn in ie.detectors_for(dept):
        if fid == finding_id:
            return fn(db, project)
    raise AssertionError(f"detector {finding_id!r} not registered for {dept!r}")


# --- Isolated detector unit tests (controlled data, no seed noise) ---

def test_reopened_bugs_detector_counts_and_flags_repeat_offender():
    db = mongomock.MongoClient()["t_ops_reopen"]
    db.tasks.insert_many([
        {"task_id": "b1", "wp_type": "Bug", "status": "Reopen", "priority": "High",
         "assignee": "Alice", "project_id": "p1"},
        {"task_id": "b2", "wp_type": "Bug", "status": "Reopen", "priority": "Normal",
         "assignee": "Alice", "project_id": "p1"},
        {"task_id": "b3", "wp_type": "Bug", "status": "Closed", "priority": "Normal",
         "assignee": "Bob", "project_id": "p1"},
    ])
    finding = _run_detector(db, "operations", "ops_reopened_bugs")
    assert finding is not None
    assert finding["metrics"][0]["value"] == 2  # 2 reopened bugs, Bob's closed one excluded
    assert finding["severity"] == "high"  # Alice is a repeat offender (2 reopens)
    assert any("Alice" in e for e in finding["evidence"])


def test_reopened_bugs_detector_links_real_op_bugs_not_seed_bugs():
    db = mongomock.MongoClient()["t_ops_links"]
    db.tasks.insert_many([
        {"source_system": "openproject", "source_id": "7582", "wp_type": "Bug",
         "status": "Reopen", "priority": "High", "assignee": "Alice", "project_source_id": "10"},
        {"task_id": "bug_kq_001", "wp_type": "Bug", "status": "Reopen", "priority": "Normal",
         "assignee": "Bob", "project_id": "proj_kq"},
    ])
    finding = _run_detector(db, "operations", "ops_reopened_bugs")
    assert finding is not None
    by_id = {e["id"]: e for e in finding["entities"]}
    assert by_id["7582"]["url"] == "https://op.flynava.ai/work_packages/7582"
    assert by_id["bug_kq_001"]["url"] is None
    assert any(e.startswith("#7582 ") for e in finding["evidence"])


def test_critical_bug_aging_flags_under_labeled_bug_by_title_not_priority():
    db = mongomock.MongoClient()["t_ops_underlabeled"]
    now = dt.datetime.now(dt.timezone.utc)
    db.tasks.insert_many([
        # Low priority, but the title says "payment" -> should still show up,
        # flagged as under-labeled, not silently excluded by priority alone.
        {"task_id": "b_payment", "title": "Payment retry loop double-charges card",
         "wp_type": "Bug", "status": "Open", "priority": "Low",
         "assignee": "Alice", "project_id": "p1", "created_at": now - dt.timedelta(days=5)},
        # High priority, but cosmetic-only by title -> not flagged as under-labeled
        # (it's still "critical" by priority, just not mislabeled).
        {"task_id": "b_logo", "title": "Logo color slightly off on login screen",
         "wp_type": "Bug", "status": "Open", "priority": "High",
         "assignee": "Bob", "project_id": "p1", "created_at": now - dt.timedelta(days=3)},
        # Genuinely irrelevant low-priority bug -> excluded entirely.
        {"task_id": "b_normal", "title": "Table column width slightly narrow",
         "wp_type": "Bug", "status": "Open", "priority": "Normal",
         "assignee": "Carol", "project_id": "p1", "created_at": now},
    ])
    finding = _run_detector(db, "operations", "ops_critical_bug_aging")
    assert finding is not None
    ids = {e["id"] for e in finding["entities"]}
    assert ids == {"b_payment", "b_logo"}  # b_normal never qualifies
    assert "under-labeled" in finding["problem"].lower()
    assert "Payment retry loop" in finding["problem"]
    under_labeled_metric = next(m for m in finding["metrics"] if "Under-labeled" in m["label"])
    assert under_labeled_metric["value"] == 1
    payment_entity = next(e for e in finding["entities"] if e["id"] == "b_payment")
    assert payment_entity["extra"]["under_labeled"] is True
    logo_entity = next(e for e in finding["entities"] if e["id"] == "b_logo")
    assert logo_entity["extra"]["under_labeled"] is False
    assert finding["severity"] == "high"  # under-labeled bugs force high severity


def test_critical_bug_aging_excludes_low_priority_bug_with_no_keyword_match():
    db = mongomock.MongoClient()["t_ops_noimpact"]
    db.tasks.insert_one(
        {"task_id": "b1", "title": "Some unrelated minor issue", "wp_type": "Bug",
         "status": "Open", "priority": "Normal", "assignee": "Alice", "project_id": "p1"})
    assert _run_detector(db, "operations", "ops_critical_bug_aging") is None


def test_reopened_bugs_detector_returns_none_when_clean():
    db = mongomock.MongoClient()["t_ops_clean"]
    db.tasks.insert_one({"task_id": "b1", "wp_type": "Bug", "status": "Closed",
                         "priority": "Normal", "assignee": "Bob", "project_id": "p1"})
    assert _run_detector(db, "operations", "ops_reopened_bugs") is None


def test_cash_position_buckets_invoice_at_45_days_into_31_60():
    db = mongomock.MongoClient()["t_fin_aging"]
    due = (dt.date.today() - dt.timedelta(days=45)).isoformat()
    db.project_invoices.insert_one({
        "invoice_id": "i1", "project_id": "p1", "number": "N1",
        "date": due, "due_date": due, "amount": 1000, "currency": "USD",
        "status": "overdue", "description": "",
    })
    finding = _run_detector(db, "finance", "fin_cash_position")
    assert finding is not None
    aging = {m["label"]: m["value"] for m in finding["metrics"]}
    assert aging["Aging 31-60"] == 1000
    assert aging["Aging 1-30"] == 0


def test_leave_collision_flags_overlapping_approved_leave():
    db = mongomock.MongoClient()["t_hr_collision"]
    db.employees.insert_many([
        {"emp_id": "e1", "name": "Alice", "department": "eng"},
        {"emp_id": "e2", "name": "Bob", "department": "eng"},
    ])
    db.leaves.insert_many([
        {"leave_id": "l1", "emp_id": "e1", "type": "Casual", "from": "2026-07-10",
         "to": "2026-07-14", "status": "Approved", "days": 5},
        {"leave_id": "l2", "emp_id": "e2", "type": "Casual", "from": "2026-07-12",
         "to": "2026-07-16", "status": "Approved", "days": 5},
    ])
    finding = _run_detector(db, "hr", "hr_leave_collision")
    assert finding is not None
    assert finding["metrics"][1]["value"] == 2


def test_leave_collision_ignores_non_overlapping_leave():
    db = mongomock.MongoClient()["t_hr_no_collision"]
    db.employees.insert_many([
        {"emp_id": "e1", "name": "Alice", "department": "eng"},
        {"emp_id": "e2", "name": "Bob", "department": "eng"},
    ])
    db.leaves.insert_many([
        {"leave_id": "l1", "emp_id": "e1", "type": "Casual", "from": "2026-07-10",
         "to": "2026-07-12", "status": "Approved", "days": 3},
        {"leave_id": "l2", "emp_id": "e2", "type": "Casual", "from": "2026-07-20",
         "to": "2026-07-22", "status": "Approved", "days": 3},
    ])
    assert _run_detector(db, "hr", "hr_leave_collision") is None


# --- run_dept: caching, echo determinism, stale-card pruning ---

def test_run_dept_is_deterministic_on_echo_and_matches_finding(db):
    from app.ai.provider import EchoProvider

    result = ie.run_dept(db, "operations", EchoProvider(), "u_test", force=True)
    assert result["cached"] is False
    assert result["cards"], "seeded operations data should trip at least one detector"
    for card in result["cards"]:
        assert card["ai_provider"] == "echo"
        assert card["confidence"] in {"Low", "Medium", "High"}
        assert card["answer"]  # echo path fills answer from the finding, never blank
        assert card["recommended_action"]


def test_run_dept_caches_until_forced(db):
    from app.ai.provider import EchoProvider

    r1 = ie.run_dept(db, "operations", EchoProvider(), "u_test")
    assert r1["cached"] is False
    r2 = ie.run_dept(db, "operations", EchoProvider(), "u_test")
    assert r2["cached"] is True
    assert r2["cards"][0]["generated_at"] == r1["cards"][0]["generated_at"]

    r3 = ie.run_dept(db, "operations", EchoProvider(), "u_test", force=True)
    assert r3["cached"] is False


def test_run_dept_prunes_cards_for_resolved_findings():
    from app.ai.provider import EchoProvider

    db = mongomock.MongoClient()["t_prune"]
    db.tasks.insert_one({"task_id": "b1", "wp_type": "Bug", "status": "Reopen",
                         "priority": "High", "assignee": "Alice", "project_id": "p1"})
    r1 = ie.run_dept(db, "operations", EchoProvider(), "u_test", force=True)
    assert any(c["insight_id"] == "operations:all:ops_reopened_bugs" for c in r1["cards"])

    db.tasks.update_one({"task_id": "b1"}, {"$set": {"status": "Closed"}})
    r2 = ie.run_dept(db, "operations", EchoProvider(), "u_test", force=True)
    assert not any(c["insight_id"] == "operations:all:ops_reopened_bugs" for c in r2["cards"])
    assert db.ai_insights.count_documents({"insight_id": "operations:all:ops_reopened_bugs"}) == 0


# --- Project scoping ---

def test_reopened_bugs_detector_scoped_to_project():
    db = mongomock.MongoClient()["t_ops_scope"]
    db.tasks.insert_many([
        {"task_id": "b1", "wp_type": "Bug", "status": "Reopen", "priority": "High",
         "assignee": "Alice", "project_source_id": "10"},
        {"task_id": "b2", "wp_type": "Bug", "status": "Reopen", "priority": "Normal",
         "assignee": "Bob", "project_source_id": "20"},
    ])
    scoped = _run_detector(db, "operations", "ops_reopened_bugs", project="10")
    assert scoped is not None
    assert scoped["metrics"][0]["value"] == 1
    assert any("Alice" in e for e in scoped["evidence"])
    assert not any("Bob" in e for e in scoped["evidence"])

    unscoped = _run_detector(db, "operations", "ops_reopened_bugs")
    assert unscoped["metrics"][0]["value"] == 2


def test_run_dept_caches_all_and_project_scopes_independently():
    from app.ai.provider import EchoProvider

    db = mongomock.MongoClient()["t_ops_scope_cache"]
    db.tasks.insert_many([
        {"task_id": "b1", "wp_type": "Bug", "status": "Reopen", "priority": "High",
         "assignee": "Alice", "project_source_id": "10"},
        {"task_id": "b2", "wp_type": "Bug", "status": "Reopen", "priority": "Normal",
         "assignee": "Bob", "project_source_id": "20"},
    ])
    r_all = ie.run_dept(db, "operations", EchoProvider(), "u_test", force=True)
    r_10 = ie.run_dept(db, "operations", EchoProvider(), "u_test", force=True, project="10")

    all_card = next(c for c in r_all["cards"] if c["insight_id"] == "operations:all:ops_reopened_bugs")
    scoped_card = next(c for c in r_10["cards"] if c["insight_id"] == "operations:10:ops_reopened_bugs")
    assert all_card["metrics"][0]["value"] == 2
    assert scoped_card["metrics"][0]["value"] == 1

    # both persisted as distinct docs, refreshing one doesn't touch the other
    assert db.ai_insights.count_documents(
        {"insight_id": "operations:all:ops_reopened_bugs"}) == 1
    assert db.ai_insights.count_documents(
        {"insight_id": "operations:10:ops_reopened_bugs"}) == 1


# --- /insights/{dept} endpoint: RBAC, caching, refresh, feedback ---

def test_insights_endpoint_returns_cards_and_caches(client, auth_header, db):
    r1 = client.get("/api/v1/insights/operations", headers=auth_header("leadership@flynava.ai"))
    assert r1.status_code == 200
    body1 = r1.json()
    assert body1["dept"] == "operations"
    assert body1["cached"] is False
    assert len(body1["cards"]) > 0

    r2 = client.get("/api/v1/insights/operations", headers=auth_header("leadership@flynava.ai"))
    body2 = r2.json()
    assert body2["cached"] is True
    assert body2["cards"][0]["generated_at"] == body1["cards"][0]["generated_at"]


def test_insights_refresh_forces_recompute(client, auth_header, db):
    client.get("/api/v1/insights/operations", headers=auth_header("leadership@flynava.ai"))
    r = client.post("/api/v1/insights/operations/refresh",
                    headers=auth_header("leadership@flynava.ai"))
    assert r.status_code == 200
    assert r.json()["cached"] is False


def test_insights_rbac_blocks_wrong_department(client, auth_header):
    # marketing role has no access to hr or operations, only marketing_sales
    denied_hr = client.get("/api/v1/insights/hr", headers=auth_header("tanvi.gupta@flynava.ai"))
    assert denied_hr.status_code == 403
    denied_ops = client.get("/api/v1/insights/operations",
                            headers=auth_header("tanvi.gupta@flynava.ai"))
    assert denied_ops.status_code == 403
    ok = client.get("/api/v1/insights/marketing", headers=auth_header("tanvi.gupta@flynava.ai"))
    assert ok.status_code == 200


def test_insights_unknown_department_404(client, auth_header):
    r = client.get("/api/v1/insights/bogus", headers=auth_header("admin@flynava.ai"))
    assert r.status_code == 404


def test_insight_feedback_toggle(client, auth_header, db):
    cards = client.get("/api/v1/insights/operations",
                       headers=auth_header("leadership@flynava.ai")).json()["cards"]
    insight_id = cards[0]["insight_id"]

    fb = client.post("/api/v1/insights/feedback",
                     json={"insight_id": insight_id, "useful": True},
                     headers=auth_header("leadership@flynava.ai"))
    assert fb.status_code == 200
    assert fb.json() == {"insight_id": insight_id, "useful": 1, "not_useful": 0, "mine": True}

    fb2 = client.post("/api/v1/insights/feedback",
                      json={"insight_id": insight_id, "useful": False},
                      headers=auth_header("leadership@flynava.ai"))
    assert fb2.json() == {"insight_id": insight_id, "useful": 0, "not_useful": 1, "mine": False}


def test_insight_feedback_survives_refresh(client, auth_header, db):
    cards = client.get("/api/v1/insights/operations",
                       headers=auth_header("leadership@flynava.ai")).json()["cards"]
    insight_id = cards[0]["insight_id"]
    client.post("/api/v1/insights/feedback", json={"insight_id": insight_id, "useful": True},
               headers=auth_header("leadership@flynava.ai"))

    client.post("/api/v1/insights/operations/refresh",
               headers=auth_header("leadership@flynava.ai"))
    cards2 = client.get("/api/v1/insights/operations",
                        headers=auth_header("leadership@flynava.ai")).json()["cards"]
    card = next(c for c in cards2 if c["insight_id"] == insight_id)
    assert card["feedback"]["useful"] == 1
    assert card["feedback"]["mine"] is True


def test_insight_feedback_unknown_id_404(client, auth_header):
    r = client.post("/api/v1/insights/feedback",
                    json={"insight_id": "operations:does_not_exist", "useful": True},
                    headers=auth_header("leadership@flynava.ai"))
    assert r.status_code == 404


# --- Project scoping over the API ---

def test_insight_projects_endpoint_lists_synced_op_projects(client, auth_header, db):
    db.projects.insert_many([
        {"source_system": "openproject", "source_id": "10", "name": "Alpha", "status": "active"},
        {"source_system": "openproject", "source_id": "20", "name": "Beta", "status": "active"},
    ])
    db.tasks.insert_many([
        {"source_system": "openproject", "source_id": "t1", "project_source_id": "10",
         "wp_type": "Task", "status": "New"},
    ])
    r = client.get("/api/v1/insights/projects", headers=auth_header("leadership@flynava.ai"))
    assert r.status_code == 200
    rows = {row["source_id"]: row for row in r.json()}
    assert rows["10"]["task_count"] == 1
    assert rows["20"]["task_count"] == 0
    assert rows["10"]["name"] == "Alpha"


def test_insights_endpoint_scoped_by_project_query_param(client, auth_header, db):
    db.projects.insert_one(
        {"source_system": "openproject", "source_id": "10", "name": "Alpha", "status": "active"})
    db.tasks.insert_many([
        {"source_system": "openproject", "source_id": "b1", "wp_type": "Bug", "status": "Reopen",
         "priority": "High", "assignee": "Alice", "project_source_id": "10"},
        {"source_system": "openproject", "source_id": "b2", "wp_type": "Bug", "status": "Reopen",
         "priority": "High", "assignee": "Bob", "project_source_id": "999"},
    ])
    r = client.get("/api/v1/insights/operations?project=10",
                   headers=auth_header("leadership@flynava.ai"))
    assert r.status_code == 200
    body = r.json()
    assert body["project"] == "10"
    card = next(c for c in body["cards"] if c["insight_id"] == "operations:10:ops_reopened_bugs")
    assert card["metrics"][0]["value"] == 1


def test_insights_endpoint_rejects_unknown_project(client, auth_header, db):
    r = client.get("/api/v1/insights/operations?project=nope",
                   headers=auth_header("leadership@flynava.ai"))
    assert r.status_code == 404
