import json

from app.ai import narrate, rag
from app.ai.provider import EchoProvider, LLMProvider, get_provider
from app.kpi import engine


def test_get_provider_defaults_to_echo_without_key():
    assert get_provider().name == "echo"


def test_live_facts_include_accurate_per_project_task_counts(db):
    # Regression: Inaya used to have no ground-truth per-project task count
    # and would guess from whatever semantic-search chunks mentioned a
    # project's name — verified live to answer "6 tasks" for a project that
    # actually had 400. The live fact must match a direct count query.
    db.projects.insert_one({"source_system": "openproject", "source_id": "px9",
                            "name": "Count Check Co", "status": "active"})
    db.tasks.insert_many([
        {"source_system": "openproject", "source_id": f"t{i}",
         "project_source_id": "px9", "title": f"task {i}"}
        for i in range(4)
    ])
    evidence = rag.retrieve(db, "how many tasks are in Count Check Co?")
    fact = next(e for e in evidence if e.startswith("OpenProject task counts by project"))
    assert "Count Check Co: 4 task(s)" in fact


def test_retrieve_pulls_evidence_from_seeded_data(db):
    # insert a controlled at-risk active project rather than relying on the
    # real roster's seeded projects (whose progress numbers change over time)
    db.projects.insert_one({"project_id": "px_risk", "name": "At Risk Co",
                            "status": "active", "progress": 20,
                            "expected_progress": 70})
    engine.run_all(db)
    evidence = rag.retrieve(db, "which projects are at risk?")
    assert any("AT RISK" in e for e in evidence)  # 20 < 0.7*70
    assert any("overdue" in e for e in evidence)  # seeded overdue task


def test_answer_returns_full_rag_envelope(db):
    engine.run_all(db)
    result = rag.answer(db, "why is productivity low?", EchoProvider())
    for key in ("answer", "reason", "evidence", "recommended_action",
                "confidence", "last_updated"):
        assert key in result
    assert result["confidence"] in {"Low", "Medium", "High"}
    assert isinstance(result["evidence"], list) and result["evidence"]


class _ObjectAnswerProvider(LLMProvider):
    """Reproduces a real failure: the model nests a structured object under
    'answer' instead of writing prose (seen live when asked for "the bug
    list") — every field the frontend renders as JSX text must survive that
    without crashing React with 'objects are not valid as a child'."""

    name = "openai"

    def complete(self, system: str, user: str) -> str:
        return json.dumps({
            "answer": {"issue": "Logo mismatch", "status": "Open", "priority": "High",
                      "assignee": "Alice", "due": "2026-07-20"},
            "reason": ["Detected via evidence scan", "matched 3 bugs"],
            "recommended_action": "Fix the logo issue.",
        })


def test_answer_coerces_non_string_llm_fields_to_text(db):
    engine.run_all(db)
    result = rag.answer(db, "give me the bug list", _ObjectAnswerProvider())
    assert isinstance(result["answer"], str)
    assert isinstance(result["reason"], str)
    assert isinstance(result["recommended_action"], str)
    assert "Logo mismatch" in result["answer"]  # coerced, not dropped


def test_narrate_llm_envelope_coerces_non_string_fields():
    envelope = narrate.llm_envelope("sys", "user", ["ev1"], _ObjectAnswerProvider())
    assert isinstance(envelope["answer"], str)
    assert isinstance(envelope["reason"], str)
    assert isinstance(envelope["recommended_action"], str)


def test_ask_endpoint_requires_ai_access(client, auth_header):
    # partner role has no ai_insights access
    denied = client.post("/api/v1/ai/ask", json={"question": "hi"},
                         headers=auth_header("partner@flynava.ai"))
    assert denied.status_code == 403


def test_ask_endpoint_returns_answer_for_leadership(client, auth_header, db):
    engine.run_all(db)
    r = client.post("/api/v1/ai/ask", json={"question": "which projects are at risk?"},
                    headers=auth_header("leadership@flynava.ai"))
    assert r.status_code == 200
    body = r.json()
    assert body["confidence"] in {"Low", "Medium", "High"}
    assert body["evidence"]


class _CaptureProvider(LLMProvider):
    """Records the exact prompt it was called with, so tests can assert on
    what actually reaches the model rather than on rag.answer's return value."""

    name = "openai"

    def __init__(self) -> None:
        self.last_system = ""
        self.last_user = ""

    def complete(self, system: str, user: str) -> str:
        self.last_system = system
        self.last_user = user
        return json.dumps({"answer": "ok", "reason": "ok", "recommended_action": "ok"})


def test_answer_includes_capped_history_in_prompt(db):
    engine.run_all(db)
    provider = _CaptureProvider()
    history = [{"q": "which bugs are high priority?", "a": "Three bugs: A, B, C."}]
    rag.answer(db, "which of those are assigned to Alice?", provider, history=history)
    assert "Conversation so far:" in provider.last_user
    assert "which bugs are high priority?" in provider.last_user
    assert "Three bugs: A, B, C." in provider.last_user


def test_answer_without_history_omits_conversation_block(db):
    engine.run_all(db)
    provider = _CaptureProvider()
    rag.answer(db, "which projects are at risk?", provider)
    assert "Conversation so far:" not in provider.last_user


def test_answer_caps_history_to_last_five_turns(db):
    engine.run_all(db)
    provider = _CaptureProvider()
    history = [{"q": f"question {i}", "a": f"answer {i}"} for i in range(7)]
    rag.answer(db, "final question", provider, history=history)
    # only the last 5 turns survive (2..6 kept, 0..1 dropped)
    assert "question 0" not in provider.last_user
    assert "question 1" not in provider.last_user
    assert "question 6" in provider.last_user


def test_answer_truncates_long_history_fields(db):
    engine.run_all(db)
    provider = _CaptureProvider()
    long_turn = {"q": "x" * 500, "a": "y" * 800}
    rag.answer(db, "final question", provider, history=[long_turn])
    assert "x" * 301 not in provider.last_user  # truncated to 300 chars
    assert "y" * 501 not in provider.last_user  # truncated to 500 chars
    assert "x" * 300 in provider.last_user
    assert "y" * 500 in provider.last_user


def test_ask_endpoint_accepts_history(client, auth_header, db):
    engine.run_all(db)
    r = client.post(
        "/api/v1/ai/ask",
        json={
            "question": "which of those are assigned to Alice?",
            "history": [{"q": "which bugs are high priority?", "a": "Three bugs."}],
        },
        headers=auth_header("leadership@flynava.ai"),
    )
    assert r.status_code == 200
