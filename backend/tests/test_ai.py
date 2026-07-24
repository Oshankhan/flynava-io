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


def test_live_facts_scope_bug_counts_per_project_not_global(db):
    # Regression: asked live "how many bugs are open in the KQ project" and
    # got the ORG-WIDE open-bug count (179, across every project) quoted as
    # if it were KQ-specific — because the only bug fact available was a
    # single global aggregate with no per-project breakdown at all.
    db.projects.insert_many([
        {"source_system": "openproject", "source_id": "px_kq", "name": "KQ Co", "status": "active"},
        {"source_system": "openproject", "source_id": "px_sv", "name": "SV Co", "status": "active"},
    ])
    db.tasks.insert_many([
        {"source_system": "openproject", "source_id": "b1", "project_source_id": "px_kq",
         "title": "kq bug 1", "wp_type": "Bug", "status": "Open", "priority": "High"},
        {"source_system": "openproject", "source_id": "b2", "project_source_id": "px_kq",
         "title": "kq bug 2", "wp_type": "Bug", "status": "In progress", "priority": "Normal"},
        {"source_system": "openproject", "source_id": "b3", "project_source_id": "px_kq",
         "title": "kq bug 3 closed", "wp_type": "Bug", "status": "Closed", "priority": "High"},
        {"source_system": "openproject", "source_id": "b4", "project_source_id": "px_sv",
         "title": "sv bug 1", "wp_type": "Bug", "status": "Open", "priority": "Normal"},
        {"source_system": "openproject", "source_id": "b5", "project_source_id": "px_sv",
         "title": "sv bug 2", "wp_type": "Bug", "status": "Open", "priority": "Normal"},
        {"source_system": "openproject", "source_id": "b6", "project_source_id": "px_sv",
         "title": "sv bug 3", "wp_type": "Bug", "status": "Open", "priority": "Normal"},
    ])
    evidence = rag.retrieve(db, "how many bugs are open in KQ Co?")

    # the global line exists but is clearly labeled as org-wide, not KQ-specific
    assert any(e.startswith("Bugs (all projects combined)") for e in evidence)

    per_project = next(e for e in evidence if e.startswith("Bug counts by project"))
    assert "KQ Co: 3 total, 2 open, 1 critical" in per_project
    assert "SV Co: 3 total, 3 open, 0 critical" in per_project

    status_breakdown = next(
        e for e in evidence if e.startswith("Open bug status breakdown by project"))
    assert "KQ Co: Open 1, In progress 1" in status_breakdown or \
           "KQ Co: In progress 1, Open 1" in status_breakdown


def test_live_facts_list_every_item_for_a_named_assignee(db):
    # Regression: asked live "what bugs are assigned to Oshan Khan" — the
    # answer named only 1 of their 2 real open bugs, because per-item recall
    # runs through semantic top-k search (a similarity ranking, not an exact
    # filter) and the second bug simply didn't rank in the top-k alongside
    # other bug chunks, even though it was indexed. The assignee's full list
    # must come from a direct query instead.
    db.tasks.insert_many([
        {"source_system": "openproject", "source_id": "a1", "project_source_id": "px_kq",
         "title": "bug one", "wp_type": "Bug", "status": "Replica Done", "assignee": "Test Person"},
        {"source_system": "openproject", "source_id": "a2", "project_source_id": "px_kq",
         "title": "bug two", "wp_type": "Bug", "status": "Open", "assignee": "Test Person"},
        {"source_system": "openproject", "source_id": "a3", "project_source_id": "px_kq",
         "title": "someone else's bug", "wp_type": "Bug", "status": "Open", "assignee": "Other Person"},
    ])
    evidence = rag.retrieve(db, "what bugs are assigned to Test Person")
    header = next(e for e in evidence if e.startswith("Test Person has"))
    assert "2 OPEN work item(s)" in header
    assert any("bug one" in e for e in evidence)
    assert any("bug two" in e for e in evidence)
    assert not any("someone else's bug" in e for e in evidence)


def test_live_facts_excludes_closed_items_for_named_assignee(db):
    # User-reported (2026-07-20, real OpenProject screenshot): "assigned to
    # X" was including years-old Closed bugs alongside current open work,
    # inflating the count far past what the person's real OpenProject
    # "Assigned to me" view shows (that view hides closed/done by default).
    # Verified live via direct OpenProject API call that our data was
    # accurate, not stale — this is a scope/definition fix, not a sync bug.
    db.tasks.insert_many([
        {"source_system": "openproject", "source_id": "b1", "project_source_id": "px_kq",
         "title": "old closed bug", "wp_type": "Bug", "status": "Closed", "assignee": "Test Person"},
        {"source_system": "openproject", "source_id": "b2", "project_source_id": "px_kq",
         "title": "current open bug", "wp_type": "Bug", "status": "Open", "assignee": "Test Person"},
    ])
    evidence = rag.retrieve(db, "what bugs are assigned to Test Person")
    header = next(e for e in evidence if e.startswith("Test Person has"))
    assert "1 OPEN work item(s)" in header
    assert any("current open bug" in e for e in evidence)
    assert not any("old closed bug" in e for e in evidence)


def test_live_facts_reports_zero_open_when_all_closed(db):
    db.tasks.insert_one(
        {"source_system": "openproject", "source_id": "c1", "project_source_id": "px_kq",
         "title": "long done bug", "wp_type": "Bug", "status": "Done", "assignee": "Test Person"})
    evidence = rag.retrieve(db, "what bugs are assigned to Test Person")
    assert any("Test Person has 0 open work items" in e for e in evidence)


def test_live_facts_resolves_unambiguous_first_name_only(db):
    # User-reported (2026-07-20, real usage): asked "how many bugs in the
    # name of Oshan" (first name only, casual phrasing) — the full-name-only
    # substring match found nothing, silently returned no evidence, and the
    # model confidently answered "no bugs assigned to Oshan" — wrong, since
    # they had a real open bug. A bare first name must resolve when only one
    # real assignee has it.
    db.tasks.insert_one(
        {"source_system": "openproject", "source_id": "d1", "project_source_id": "px_kq",
         "title": "unique first name bug", "wp_type": "Bug", "status": "Open",
         "assignee": "Zolan Marek"})
    evidence = rag.retrieve(db, "how many bugs for Zolan in kq project")
    assert any(e.startswith("Zolan Marek has") for e in evidence)
    assert any("unique first name bug" in e for e in evidence)


def test_live_facts_bare_first_name_ambiguous_across_two_people_no_guess(db):
    # This org has genuine collisions (e.g. real "Rahul Chowta" vs "Rahul
    # Kumar") — guessing one when two different real people share a first
    # name would silently attribute someone else's bugs to the wrong person.
    db.tasks.insert_many([
        {"source_system": "openproject", "source_id": "e1", "project_source_id": "px_kq",
         "title": "person one's bug", "wp_type": "Bug", "status": "Open",
         "assignee": "Zolan Marek"},
        {"source_system": "openproject", "source_id": "e2", "project_source_id": "px_kq",
         "title": "person two's bug", "wp_type": "Bug", "status": "Open",
         "assignee": "Zolan Petrova"},
    ])
    evidence = rag.retrieve(db, "how many bugs for Zolan in kq project")
    assert not any(e.startswith("Zolan Marek has") for e in evidence)
    assert not any(e.startswith("Zolan Petrova has") for e in evidence)


def test_live_facts_no_assignee_match_when_no_name_in_question(db):
    db.tasks.insert_one({"source_system": "openproject", "source_id": "a1",
                        "project_source_id": "px_kq", "title": "bug one",
                        "wp_type": "Bug", "status": "Open", "assignee": "Test Person"})
    evidence = rag.retrieve(db, "which projects are at risk?")
    assert not any(e.startswith("Test Person has") for e in evidence)


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
