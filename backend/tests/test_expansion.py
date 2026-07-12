"""Expansion coverage: bug KPIs, 8 dashboards, trend series, OpenAI provider."""
import httpx
import respx

from app.ai.provider import OpenAIProvider
from app.config import settings
from app.kpi import engine


def _seed_bugs(db):
    # the real roster's seed already carries ~40 synthetic KQ bugs, so clear
    # those out first — these tests want an exact, known bug population.
    db.tasks.delete_many({"wp_type": {"$regex": "bug", "$options": "i"}})
    bugs = [
        ("b1", "Closed", "Normal"), ("b2", "Closed", "Immediate"),
        ("b3", "Replica Done", "Normal"), ("b4", "In progress", "High"),
        ("b5", "New", "Immediate"),
    ]
    for sid, status, prio in bugs:
        db.tasks.insert_one({
            "source_system": "openproject", "source_id": sid, "title": sid,
            "wp_type": "BUG", "status": status, "priority": prio,
            "progress": 0, "project_source_id": "52",
        })


def test_bug_kpis_computed_from_openproject_tasks(db):
    _seed_bugs(db)
    snap = {r["kpi_id"]: r for r in engine.run_all(db, "product_dev")}
    assert snap["pd_open_bugs"]["value"] == 3        # 5 total - 2 closed
    assert snap["pd_critical_bugs"]["value"] == 2    # High + Immediate, open
    assert snap["pd_bug_closure"]["value"] == 40.0   # 2/5
    assert snap["pd_open_bugs"]["rag"] == "green"    # 3 <= target 25


def test_bug_kpis_grey_without_bug_data(db):
    # the real roster's seed carries synthetic KQ bugs AND a demo sparkline
    # history for the bug KPIs — clear both to exercise the genuinely
    # "no data yet" state (run_all keeps the last known value otherwise).
    db.tasks.delete_many({"wp_type": {"$regex": "bug", "$options": "i"}})
    db.kpi_values.delete_many({"kpi_id": {"$regex": "^pd_"}})
    snap = {r["kpi_id"]: r for r in engine.run_all(db, "product_dev")}
    assert snap["pd_open_bugs"]["value"] is None
    assert snap["pd_open_bugs"]["rag"] == "grey"


def test_all_eight_dashboards_render(client, auth_header):
    cases = {
        "leadership": "leadership@flynava.ai", "manager": "harsha.varlani@flynava.ai",
        "hr": "hr@flynava.ai", "finance": "leadership@flynava.ai",
        "marketing": "tanvi.gupta@flynava.ai", "employee": "manas.ankarla@flynava.ai",
        "investor": "investor@flynava.ai", "partner": "partner@flynava.ai",
    }
    for key, email in cases.items():
        r = client.get(f"/api/v1/dashboards/{key}", headers=auth_header(email))
        assert r.status_code == 200, f"{key}: {r.text}"
        assert len(r.json()["kpis"]) > 0, key


def test_dashboard_series_and_change_pct(client, auth_header):
    r = client.get("/api/v1/dashboards/finance",
                   headers=auth_header("leadership@flynava.ai"))
    body = r.json()
    # revenue has a seeded 12-month history -> a trend series exists
    assert any(s["kpi_id"] == "fin_revenue_mtd" for s in body["series"])
    rev = next(s for s in body["series"] if s["kpi_id"] == "fin_revenue_mtd")
    assert len(rev["points"]) >= 3
    # change arrow: 432000 vs 424000 previous month = +1.9%
    kpi = next(k for k in body["kpis"] if k["kpi_id"] == "fin_revenue_mtd")
    assert kpi["change_pct"] == 1.9


def test_bug_breakdown_on_manager_dashboard(client, auth_header, db):
    _seed_bugs(db)
    r = client.get("/api/v1/dashboards/manager",
                   headers=auth_header("harsha.varlani@flynava.ai"))
    breakdown = {row["status"]: row["count"] for row in r.json()["bug_breakdown"]}
    assert breakdown["Closed"] == 2
    assert breakdown["Replica Done"] == 1


def test_investor_sees_summary_not_hr(client, auth_header):
    r = client.get("/api/v1/dashboards/investor",
                   headers=auth_header("investor@flynava.ai"))
    modules = {k["module"] for k in r.json()["kpis"]}
    assert "finance" in modules
    assert "hr" not in modules  # investor has no HR access


@respx.mock
def test_openai_provider_calls_chat_completions(monkeypatch):
    monkeypatch.setattr(settings, "openai_api_key", "test-key")
    route = respx.post("https://api.openai.com/v1/chat/completions").mock(
        return_value=httpx.Response(200, json={
            "choices": [{"message": {"content":
                '{"answer":"A","reason":"R","recommended_action":"X"}'}}]}))
    out = OpenAIProvider().complete("sys", "user")
    assert route.called
    sent = route.calls[0].request
    assert b"gpt-4o-mini" in sent.content
    assert b'"max_tokens": 400' in sent.content or b'"max_tokens":400' in sent.content
    assert '"answer":"A"' in out


def test_rag_includes_bug_and_compliance_evidence(db):
    _seed_bugs(db)
    from app.ai import rag
    from app.ai.provider import EchoProvider
    result = rag.answer(db, "how are we doing on bugs?", EchoProvider())
    assert any("Bugs:" in e for e in result["evidence"])
    assert any("Compliance:" in e for e in result["evidence"])
    assert len(result["evidence"]) <= rag.MAX_EVIDENCE
