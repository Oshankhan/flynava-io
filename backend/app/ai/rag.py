"""Retrieval-augmented Ask IO (PRD section 9.3).

Retrieves structured evidence from Mongo (projects, tasks/bugs, KPI values,
compliance items, recruitment positions, pending documents, alerts), asks the
LLM for a grounded answer, and always returns the required envelope:
Answer / Reason / Evidence / Recommended Action / Confidence / Last Updated.
"""
from __future__ import annotations

import datetime as dt
import json

from pymongo.database import Database

from .provider import LLMProvider

SYSTEM = (
    "You are Ask IO, FlyNava's organizational intelligence assistant. "
    "Answer ONLY from the provided evidence. If the evidence is insufficient, "
    "say so — never invent facts. Respond as a compact JSON object with keys "
    "'answer', 'reason', 'recommended_action'."
)

MAX_EVIDENCE = 16  # keeps prompt small — cost guard
CLOSED = {"Closed", "Rejected", "Resolved"}


def retrieve(db: Database, question: str) -> list[str]:
    """Gather evidence snippets relevant to the question (keyword-lite for v1)."""
    evidence: list[str] = []

    for p in db.projects.find({"status": "active"}).limit(8):
        exp = p.get("expected_progress")
        flag = " (AT RISK)" if exp and p.get("progress", 0) < 0.7 * exp else ""
        evidence.append(
            f"Project {p.get('name')}: {p.get('progress', 0)}% complete"
            f"{f', expected {exp}%' if exp else ''}{flag}."
        )

    today = dt.date.today().isoformat()
    overdue = db.tasks.count_documents(
        {"due_date": {"$lt": today, "$ne": None}, "progress": {"$lt": 100}}
    )
    if overdue:
        evidence.append(f"{overdue} task(s)/work item(s) are overdue.")

    # Bug picture (from OpenProject work packages)
    bug_q = {"wp_type": {"$regex": "bug", "$options": "i"}}
    total_bugs = db.tasks.count_documents(bug_q)
    if total_bugs:
        open_bugs = db.tasks.count_documents({**bug_q, "status": {"$nin": list(CLOSED)}})
        crit = db.tasks.count_documents(
            {**bug_q, "priority": {"$in": ["Immediate", "High"]},
             "status": {"$nin": list(CLOSED)}})
        evidence.append(
            f"Bugs: {total_bugs} total, {open_bugs} still open, "
            f"{crit} open at High/Immediate priority.")

    for c in db.compliance_items.find({"status": {"$ne": "done"}}).limit(3):
        evidence.append(
            f"Compliance: '{c.get('title')}' due {c.get('due_date')} "
            f"(owner {c.get('owner')}, {c.get('status')}).")

    open_pos = db.positions.count_documents({"status": "open"})
    if open_pos:
        evidence.append(f"Recruitment: {open_pos} open position(s).")

    pending_docs = db.documents.count_documents({"status": "pending"})
    if pending_docs:
        evidence.append(f"{pending_docs} document(s) awaiting approval.")

    for k in db.kpi_values.find().sort("calculated_at", -1).limit(6):
        evidence.append(
            f"KPI {k['kpi_id']} = {k.get('value')} "
            f"(computed {k['calculated_at']:%Y-%m-%d}).")

    for a in db.alerts.find({"status": "open"}).limit(3):
        evidence.append(f"Alert: {a.get('message')}")

    return evidence[:MAX_EVIDENCE]


def _confidence(evidence: list[str]) -> str:
    if len(evidence) >= 3:
        return "High"
    return "Medium" if evidence else "Low"


def _parse(raw: str) -> dict:
    """Parse model output; tolerate ```json fences."""
    cleaned = raw.strip()
    if cleaned.startswith("```"):
        first_newline = cleaned.find("\n")
        cleaned = cleaned[first_newline + 1:] if first_newline != -1 else cleaned
        cleaned = cleaned.rsplit("```", 1)[0].strip()
    try:
        return json.loads(cleaned)
    except (json.JSONDecodeError, TypeError):
        return {"answer": raw, "reason": "", "recommended_action": ""}


def answer(db: Database, question: str, provider: LLMProvider) -> dict:
    evidence = retrieve(db, question)
    context = "\n".join(f"- {e}" for e in evidence) or "- (no matching records)"
    user = f"Question: {question}\n\nEvidence:\n{context}"

    try:
        parsed = _parse(provider.complete(SYSTEM, user))
    except Exception as exc:  # noqa: BLE001 - never 500 the dashboard on LLM errors
        parsed = {
            "answer": "The AI provider is unavailable right now; the retrieved "
                      "evidence below is still current.",
            "reason": f"Provider error: {type(exc).__name__}",
            "recommended_action": "Retry shortly or check the AI provider key.",
        }

    return {
        "answer": parsed.get("answer", ""),
        "reason": parsed.get("reason", ""),
        "evidence": evidence,
        "recommended_action": parsed.get("recommended_action", ""),
        "confidence": _confidence(evidence),
        "last_updated": dt.datetime.now(dt.timezone.utc).isoformat(),
    }
