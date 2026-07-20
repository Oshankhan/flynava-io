"""Retrieval-augmented Ask IO (PRD section 9.3).

Hybrid retrieval: a handful of always-live structured facts (aggregate counts
that change too often to keep re-embedding — at-risk projects, overdue/bug
counts, latest KPI values, open alerts) plus semantic top-k recall over the
embedded chunk index (`services/rag_index.py` builds it; `ai/vectorstore.py`
searches it) covering tasks/bugs, projects, compliance, recruitment,
contacts, invoices, and documents. Always returns the required envelope:
Answer / Reason / Evidence / Recommended Action / Confidence / Last Updated.
"""
from __future__ import annotations

import datetime as dt

from pymongo.database import Database

from ..config import settings
from ..kpi.engine import TERMINAL_STATUSES
from .embeddings import get_embedder
from .narrate import as_text, confidence_from_evidence, parse_llm_json
from .provider import LLMProvider
from .vectorstore import get_store

SYSTEM = (
    "You are Ask IO, FlyNava's organizational intelligence assistant. "
    "Answer ONLY from the provided evidence. If the evidence is insufficient, "
    "say so — never invent facts. Respond as a compact JSON object with keys "
    "'answer', 'reason', 'recommended_action'. Each of those three values must "
    "be plain prose text (a string) — if you're listing multiple items (e.g. "
    "several bugs), write them as a single readable sentence or a dash-"
    "separated list inside that string, never as a nested JSON array or object. "
    "If conversation history is provided, use it to resolve references like "
    "'those bugs' or 'that project' in the current question. When the "
    "evidence has both an org-wide aggregate (e.g. 'all projects combined') "
    "and a per-project breakdown, and the question names a specific project, "
    "use ONLY that project's number from the per-project line — never quote "
    "the org-wide total as if it belonged to one project."
)

# History is client-supplied (the frontend already holds the full turn list)
# and re-capped here regardless of what's sent — keeps the prompt small and
# the cost identical to a single-turn ask (still one LLM call per question;
# the history just rides along in the same prompt).
MAX_HISTORY_TURNS = 5
MAX_HISTORY_Q_CHARS = 300
MAX_HISTORY_A_CHARS = 500

# Live facts are capped tightly and semantic hits get their own reserved
# budget on top — otherwise a data-rich org (many active projects, many KPIs)
# fills the whole evidence list with aggregate counts before semantic search
# ever gets a chance to contribute, and open-ended questions ("any fare
# management issues?") come back "insufficient evidence" despite a matching
# chunk sitting right there in the index. Verified against live data: this
# is exactly the failure mode without the reserved budget.
MAX_LIVE_FACTS = 10
MAX_EVIDENCE = MAX_LIVE_FACTS + 10  # live facts + up to rag_top_k semantic hits


def _bug_facts(db: Database, bug_q: dict) -> list[str]:
    """Per-project bug counts + open-bug status breakdown. Without these, the
    only bug numbers available were global aggregates — verified live: asking
    "how many bugs are open in the KQ project" returned the org-wide open
    count (179 across ALL projects) mislabeled as KQ-specific, because
    nothing in the evidence was actually scoped per project. Same root cause
    as the earlier per-project task-count fix, just for bugs specifically."""
    op_projects = list(db.projects.find({"source_system": "openproject"}))
    if not op_projects:
        return []

    count_lines = []
    status_lines = []
    for p in op_projects:
        q = {**bug_q, "project_source_id": p["source_id"]}
        total = db.tasks.count_documents(q)
        if not total:
            continue
        open_q = {**q, "status": {"$nin": TERMINAL_STATUSES}}
        open_n = db.tasks.count_documents(open_q)
        crit_n = db.tasks.count_documents(
            {**open_q, "priority": {"$in": ["Immediate", "High"]}})
        count_lines.append(f"{p.get('name')}: {total} total, {open_n} open, "
                           f"{crit_n} critical")

        status_counts: dict[str, int] = {}
        for t in db.tasks.find(open_q, {"status": 1}):
            s = t.get("status") or "Unknown"
            status_counts[s] = status_counts.get(s, 0) + 1
        if status_counts:
            breakdown = ", ".join(
                f"{s} {n}" for s, n in sorted(status_counts.items(), key=lambda kv: -kv[1]))
            status_lines.append(f"{p.get('name')}: {breakdown}")

    facts = []
    if count_lines:
        facts.append("Bug counts by project — " + "; ".join(count_lines) + ".")
    if status_lines:
        facts.append("Open bug status breakdown by project — " + "; ".join(status_lines) + ".")
    return facts


def _live_facts(db: Database) -> list[str]:
    facts: list[str] = []

    active_projects = list(db.projects.find({"status": "active"}))
    if active_projects:
        facts.append(f"{len(active_projects)} active project(s).")

    # Per-project task counts — same query the AI Insights project dropdown
    # uses (api/v1/insights.py:list_insight_projects), so "how many tasks are
    # in project X" always matches what the dropdown shows, instead of the
    # model guessing from whatever semantic-search chunks happen to mention
    # that project's name.
    op_projects = list(db.projects.find({"source_system": "openproject"}))
    if op_projects:
        counts = []
        for p in op_projects:
            n = db.tasks.count_documents(
                {"source_system": "openproject", "project_source_id": p["source_id"]})
            counts.append(f"{p.get('name')}: {n} task(s)")
        facts.append("OpenProject task counts by project — " + "; ".join(counts) + ".")

    # Bug picture — global aggregate AND per-project breakdown. The global
    # line alone is what caused per-project bug questions to get answered
    # with the org-wide number (see _bug_facts docstring) — both are kept
    # since "how many bugs total" and "how many in project X" are both real
    # questions, and placed early so they survive the MAX_LIVE_FACTS cap.
    bug_q = {"wp_type": {"$regex": "bug", "$options": "i"}}
    total_bugs = db.tasks.count_documents(bug_q)
    if total_bugs:
        open_bugs = db.tasks.count_documents({**bug_q, "status": {"$nin": TERMINAL_STATUSES}})
        crit = db.tasks.count_documents(
            {**bug_q, "priority": {"$in": ["Immediate", "High"]},
             "status": {"$nin": TERMINAL_STATUSES}})
        facts.append(
            f"Bugs (all projects combined): {total_bugs} total, {open_bugs} still open, "
            f"{crit} open at High/Immediate priority.")
    facts.extend(_bug_facts(db, bug_q))

    today = dt.date.today().isoformat()
    overdue = db.tasks.count_documents(
        {"due_date": {"$lt": today, "$ne": None}, "progress": {"$lt": 100}}
    )
    if overdue:
        facts.append(f"{overdue} task(s)/work item(s) are overdue.")

    at_risk = [p for p in active_projects
              if p.get("expected_progress") and p.get("progress", 0) < 0.7 * p["expected_progress"]]
    for p in at_risk[:3]:
        facts.append(
            f"Project {p.get('name')}: {p.get('progress', 0)}% complete, "
            f"expected {p['expected_progress']}% (AT RISK)."
        )

    for c in db.compliance_items.find({"status": {"$ne": "done"}}).limit(2):
        facts.append(
            f"Compliance: '{c.get('title')}' due {c.get('due_date')} "
            f"(owner {c.get('owner')}, {c.get('status')}).")

    open_pos = db.positions.count_documents({"status": "open"})
    if open_pos:
        facts.append(f"Recruitment: {open_pos} open position(s).")

    pending_docs = db.documents.count_documents({"status": "pending"})
    if pending_docs:
        facts.append(f"{pending_docs} document(s) awaiting approval.")

    for k in db.kpi_values.find().sort("calculated_at", -1).limit(3):
        facts.append(
            f"KPI {k['kpi_id']} = {k.get('value')} "
            f"(computed {k['calculated_at']:%Y-%m-%d}).")

    for a in db.alerts.find({"status": "open"}).limit(2):
        facts.append(f"Alert: {a.get('message')}")

    return facts[:MAX_LIVE_FACTS]


def _cap_history(history: list[dict] | None) -> list[dict]:
    """Trim to the last N turns and truncate each field — the client may
    send its whole conversation, but the prompt budget is fixed regardless."""
    if not history:
        return []
    capped = []
    for turn in history[-MAX_HISTORY_TURNS:]:
        q = as_text(turn.get("q", ""))[:MAX_HISTORY_Q_CHARS]
        a = as_text(turn.get("a", ""))[:MAX_HISTORY_A_CHARS]
        if q or a:
            capped.append({"q": q, "a": a})
    return capped


def retrieve(db: Database, question: str, history: list[dict] | None = None) -> list[str]:
    """Live structured facts (aggregate counts) + semantic recall from the
    embedded chunk index — this is what actually answers open-ended
    questions ("which bugs keep reopening for Kenya Airways") rather than
    just the counts above. Semantic search no-ops gracefully to an empty
    index (nothing reindexed yet); the live facts still carry the answer.

    When history is given, the embedded query is enriched with the last
    couple of prior questions so anaphoric follow-ups ("what about the
    high-priority ones?") still retrieve the right chunks — the live facts
    and embedding model are unchanged, this only widens the search text."""
    evidence = _live_facts(db)
    seen = set(evidence)

    query_text = question
    if history:
        prior_qs = [t["q"] for t in history[-2:] if t.get("q")]
        if prior_qs:
            query_text = "\n".join([*prior_qs, question])

    embedder = get_embedder()
    query_vec = embedder.embed([query_text])[0]
    hits = get_store().search(db, query_vec, k=settings.rag_top_k, min_score=settings.rag_min_score)
    for h in hits:
        if h.text not in seen:
            evidence.append(h.text)
            seen.add(h.text)

    return evidence[:MAX_EVIDENCE]


def answer(db: Database, question: str, provider: LLMProvider,
          history: list[dict] | None = None) -> dict:
    history = _cap_history(history)
    evidence = retrieve(db, question, history)
    context = "\n".join(f"- {e}" for e in evidence) or "- (no matching records)"

    if history:
        convo = "\n".join(f"Q: {t['q']}\nA: {t['a']}" for t in history)
        user = f"Conversation so far:\n{convo}\n\nQuestion: {question}\n\nEvidence:\n{context}"
    else:
        user = f"Question: {question}\n\nEvidence:\n{context}"

    try:
        parsed = parse_llm_json(provider.complete(SYSTEM, user))
    except Exception as exc:  # noqa: BLE001 - never 500 the dashboard on LLM errors
        parsed = {
            "answer": "The AI provider is unavailable right now; the retrieved "
                      "evidence below is still current.",
            "reason": f"Provider error: {type(exc).__name__}",
            "recommended_action": "Retry shortly or check the AI provider key.",
        }

    return {
        "answer": as_text(parsed.get("answer", "")),
        "reason": as_text(parsed.get("reason", "")),
        "evidence": evidence,
        "recommended_action": as_text(parsed.get("recommended_action", "")),
        "confidence": confidence_from_evidence(evidence),
        "last_updated": dt.datetime.now(dt.timezone.utc).isoformat(),
    }
