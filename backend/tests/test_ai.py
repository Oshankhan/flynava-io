from app.ai import rag
from app.ai.provider import EchoProvider, get_provider
from app.kpi import engine


def test_get_provider_defaults_to_echo_without_key():
    assert get_provider().name == "echo"


def test_retrieve_pulls_evidence_from_seeded_data(db):
    engine.run_all(db)
    evidence = rag.retrieve(db, "which projects are at risk?")
    assert any("AT RISK" in e for e in evidence)  # p_alpha 42 < 0.7*70
    assert any("overdue" in e for e in evidence)  # seeded overdue task


def test_answer_returns_full_rag_envelope(db):
    engine.run_all(db)
    result = rag.answer(db, "why is productivity low?", EchoProvider())
    for key in ("answer", "reason", "evidence", "recommended_action",
                "confidence", "last_updated"):
        assert key in result
    assert result["confidence"] in {"Low", "Medium", "High"}
    assert isinstance(result["evidence"], list) and result["evidence"]


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
