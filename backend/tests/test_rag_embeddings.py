import mongomock

from app.ai.embeddings import HashingEmbedder
from app.ai.provider import EchoProvider
from app.ai.vectorstore import get_store
from app.ai import rag
from app.services import rag_index


def test_hashing_embedder_deterministic_and_normalized():
    e = HashingEmbedder()
    v1 = e.embed(["reopened bug in KQ Module wise Issues"])[0]
    v2 = e.embed(["reopened bug in KQ Module wise Issues"])[0]
    assert v1 == v2  # same text -> same vector every time
    assert len(v1) == e.dim
    norm = sum(x * x for x in v1) ** 0.5
    assert abs(norm - 1.0) < 1e-6 or norm == 0.0  # unit-normalized (or all-zero for empty text)


def test_hashing_embedder_different_text_different_vector():
    e = HashingEmbedder()
    v1 = e.embed(["bug reopened for Kenya Airways"])[0]
    v2 = e.embed(["invoice overdue for Saudia Airlines"])[0]
    assert v1 != v2


def test_reindex_builds_chunks_for_every_registered_source():
    db = mongomock.MongoClient()["t_rag_build"]
    db.projects.insert_one({"project_id": "p1", "name": "Alpha", "status": "active", "progress": 40})
    db.tasks.insert_one({"task_id": "t1", "title": "Fix login bug", "wp_type": "Bug",
                         "status": "Reopen", "priority": "High", "assignee": "Alice",
                         "project_id": "p1"})
    stats = rag_index.reindex(db)
    assert stats["sources"]["tasks"] == 1
    assert stats["sources"]["projects"] == 1
    assert stats["embedded"] == 2
    assert stats["unchanged"] == 0
    doc = db.rag_chunks.find_one({"chunk_id": "tasks:t1"})
    assert doc is not None
    assert "Fix login bug" in doc["text"]
    assert len(doc["embedding"]) == HashingEmbedder.dim


def test_reindex_is_incremental_only_changed_text_reembeds():
    db = mongomock.MongoClient()["t_rag_incremental"]
    db.tasks.insert_one({"task_id": "t1", "title": "Fix login bug", "wp_type": "Bug",
                         "status": "Open", "priority": "High", "assignee": "Alice",
                         "project_id": "p1"})
    db.tasks.insert_one({"task_id": "t2", "title": "Fix logout bug", "wp_type": "Bug",
                         "status": "Open", "priority": "Normal", "assignee": "Bob",
                         "project_id": "p1"})
    stats1 = rag_index.reindex(db, sources=["tasks"])
    assert stats1["embedded"] == 2

    # nothing changed -> second call re-embeds nothing
    stats2 = rag_index.reindex(db, sources=["tasks"])
    assert stats2["embedded"] == 0
    assert stats2["unchanged"] == 2

    # change one task's status -> only that one chunk re-embeds
    db.tasks.update_one({"task_id": "t1"}, {"$set": {"status": "Closed"}})
    stats3 = rag_index.reindex(db, sources=["tasks"])
    assert stats3["embedded"] == 1
    assert stats3["unchanged"] == 1
    assert "Closed" in db.rag_chunks.find_one({"chunk_id": "tasks:t1"})["text"]


def test_reindex_prunes_chunks_for_deleted_records():
    db = mongomock.MongoClient()["t_rag_prune"]
    db.tasks.insert_one({"task_id": "t1", "title": "Temp task", "wp_type": "Task",
                         "status": "New", "project_id": "p1"})
    rag_index.reindex(db, sources=["tasks"])
    assert db.rag_chunks.count_documents({"chunk_id": "tasks:t1"}) == 1

    db.tasks.delete_one({"task_id": "t1"})
    stats = rag_index.reindex(db, sources=["tasks"])
    assert stats["pruned"] == 1
    assert db.rag_chunks.count_documents({"chunk_id": "tasks:t1"}) == 0


def test_reindex_force_reembeds_even_when_unchanged():
    db = mongomock.MongoClient()["t_rag_force"]
    db.tasks.insert_one({"task_id": "t1", "title": "Stable task", "wp_type": "Task",
                         "status": "New", "project_id": "p1"})
    rag_index.reindex(db, sources=["tasks"])
    stats = rag_index.reindex(db, sources=["tasks"], force=True)
    assert stats["embedded"] == 1
    assert stats["unchanged"] == 0


def test_vector_search_finds_semantically_closest_chunk():
    db = mongomock.MongoClient()["t_rag_search"]
    db.tasks.insert_many([
        {"task_id": "t1", "title": "Login page crashes on submit", "wp_type": "Bug",
         "status": "Reopen", "priority": "High", "assignee": "Alice", "project_id": "p1"},
        {"task_id": "t2", "title": "Invoice PDF export is slow", "wp_type": "Task",
         "status": "New", "priority": "Normal", "assignee": "Bob", "project_id": "p1"},
    ])
    rag_index.reindex(db, sources=["tasks"])

    from app.ai.embeddings import HashingEmbedder
    embedder = HashingEmbedder()
    query_vec = embedder.embed(["login page crash"])[0]
    hits = get_store().search(db, query_vec, k=5, min_score=0.0)
    assert hits
    assert hits[0].chunk_id == "tasks:t1"  # closer match ranks first


def test_vector_search_respects_min_score_and_returns_empty_on_no_index():
    db = mongomock.MongoClient()["t_rag_empty"]
    hits = get_store().search(db, [0.1] * HashingEmbedder.dim, k=5, min_score=0.0)
    assert hits == []


def test_ask_io_answer_includes_semantic_evidence_after_reindex(db):
    db.tasks.insert_one({"task_id": "t_extra", "title": "Payment gateway retry storm",
                         "wp_type": "Bug", "status": "Reopen", "priority": "Immediate",
                         "assignee": "Nayana Anaji", "project_id": "proj_kq"})
    rag_index.reindex(db, sources=["tasks"])

    result = rag.answer(db, "payment gateway retry issue", EchoProvider())
    assert any("Payment gateway retry storm" in e for e in result["evidence"])
    for key in ("answer", "reason", "evidence", "recommended_action", "confidence", "last_updated"):
        assert key in result


def test_ask_io_still_works_when_index_is_empty(db):
    # No reindex called on the shared `db` fixture's fresh state for this test's
    # own inserted data — confirms live structured facts alone are enough.
    result = rag.answer(db, "which projects are at risk?", EchoProvider())
    assert result["confidence"] in {"Low", "Medium", "High"}
    assert isinstance(result["evidence"], list)


def test_reindex_endpoint_requires_super_admin(client, auth_header):
    denied = client.post("/api/v1/ai/reindex", json={},
                         headers=auth_header("leadership@flynava.ai"))
    assert denied.status_code == 403
    ok = client.post("/api/v1/ai/reindex", json={},
                     headers=auth_header("admin@flynava.ai"))
    assert ok.status_code == 200
    body = ok.json()
    assert "sources" in body and "embedded" in body


def test_reindex_endpoint_scoped_to_given_sources(client, auth_header, db):
    r = client.post("/api/v1/ai/reindex", json={"sources": ["compliance_items"]},
                    headers=auth_header("admin@flynava.ai"))
    assert r.status_code == 200
    assert list(r.json()["sources"].keys()) == ["compliance_items"]


def test_index_status_endpoint(client, auth_header, db):
    client.post("/api/v1/ai/reindex", json={}, headers=auth_header("admin@flynava.ai"))
    r = client.get("/api/v1/ai/index/status", headers=auth_header("admin@flynava.ai"))
    assert r.status_code == 200
    body = r.json()
    assert body["total_chunks"] > 0
    assert body["embedder"] == "hashing"  # rag_embeddings_enabled=False in tests
    assert "tasks" in body["available_sources"]


def test_index_status_requires_super_admin(client, auth_header):
    denied = client.get("/api/v1/ai/index/status", headers=auth_header("leadership@flynava.ai"))
    assert denied.status_code == 403
