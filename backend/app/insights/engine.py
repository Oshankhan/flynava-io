"""Insight detector registry + runner.

Each department has a small set of `@detector` functions — deterministic
Mongo queries that mine for a *specific, named problem* ("which bugs keep
reopening", "who is overburdened", ...) rather than just exposing a metric.
A detector returns a `Finding` dict when its problem is present, or `None`
when it isn't. `run_dept()` runs every detector for a department, narrates
each finding into the PRD RAG envelope (Answer/Reason/Action/Confidence —
`ai/narrate.py`), and persists cards in `ai_insights` so re-opening a
dashboard doesn't re-run detectors or re-call the LLM until either the cache
expires or a caller forces a refresh.

Finding shape (what a detector returns):
    {
        "severity": "high" | "medium" | "low" | "info",
        "problem": str,                       # plain-language problem statement
        "metrics": [{"label", "value", "unit"}],
        "entities": [{"kind", "id", "label", "extra"}],
        "evidence": [str, ...],               # <=8, fed to the LLM + shown on the card
        "chart": {"kind": "bars", "points": [{"label", "value"}]} | None,
        "action_hint": str,                   # deterministic fallback recommendation
    }

Every detector takes an optional `project` (an OpenProject `source_id`,
e.g. "52" for KQ Module wise Issues) — `None` means "every project". Only
the operations detectors act on it (they query OP-synced tasks/projects,
which carry `project_source_id`/`source_id`); finance/hr/marketing detectors
accept the parameter for signature uniformity but ignore it, since their
data isn't OP-project-shaped. Cards are cached per (dept, project) pair so
switching the dropdown doesn't clobber another scope's cache.
"""
from __future__ import annotations

import datetime as dt
from typing import Callable

from pymongo.database import Database

from ..ai.narrate import echo_envelope, narrate
from ..ai.provider import LLMProvider
from ..config import settings

Detector = Callable[[Database, str | None], dict | None]
_DETECTORS: dict[str, list[tuple[str, str, Detector]]] = {}

MAX_LLM_CARDS_PER_DEPT = 6  # cost guard — narrate the rest deterministically
SEVERITY_ORDER = {"high": 0, "medium": 1, "low": 2, "info": 3}

# dept key (as used in URLs / dashboards.py) -> RBAC module it's gated behind.
DEPT_MODULE = {
    "operations": "operations",
    "finance": "finance",
    "hr": "hr",
    "marketing": "marketing_sales",
}
DEPT_TITLE = {
    "operations": "Operations", "finance": "Finance", "hr": "HR",
    "marketing": "Marketing & Sales",
}

SYSTEM = (
    "You are Ask IO, FlyNava's organizational intelligence assistant. An "
    "automated detector has already found a specific problem in the "
    "company's data — you are not answering an open question, you are "
    "narrating that finding into a clear, executive-facing card. Answer "
    "ONLY from the provided problem statement, metrics, and evidence — "
    "never invent facts or numbers not present below. Respond as a compact "
    "JSON object with keys 'answer', 'reason', 'recommended_action'."
)


def detector(finding_id: str, dept: str, title: str):
    """Register a detector under `dept`, keyed by a stable `finding_id`
    (used as half of the persisted card's natural key: `{dept}:{finding_id}`)."""

    def wrap(fn: Detector) -> Detector:
        _DETECTORS.setdefault(dept, []).append((finding_id, title, fn))
        return fn

    return wrap


def detectors_for(dept: str) -> list[tuple[str, str, Detector]]:
    return _DETECTORS.get(dept, [])


def _aware(d: dt.datetime) -> dt.datetime:
    # Mongo (real or mongomock) round-trips datetimes as naive UTC.
    return d if d.tzinfo else d.replace(tzinfo=dt.timezone.utc)


def _user_prompt(title: str, finding: dict) -> str:
    lines = [f"Detector: {title}", f"Problem: {finding['problem']}"]
    for m in finding.get("metrics", []):
        unit = m.get("unit") or ""
        lines.append(f"Metric — {m.get('label')}: {m.get('value')}{unit}")
    if finding.get("action_hint"):
        lines.append(f"Suggested action if nothing better applies: {finding['action_hint']}")
    evidence = finding.get("evidence") or []
    context = "\n".join(f"- {e}" for e in evidence) or "- (no additional evidence rows)"
    return "\n".join(lines) + f"\n\nEvidence:\n{context}"


def _public_card(doc: dict, user_id: str | None) -> dict:
    useful_by = doc.get("useful_by", [])
    not_useful_by = doc.get("not_useful_by", [])
    mine = True if user_id in useful_by else False if user_id in not_useful_by else None
    return {
        "insight_id": doc["insight_id"], "dept": doc["dept"], "title": doc["title"],
        "severity": doc["severity"], "problem": doc["problem"],
        "metrics": doc.get("metrics", []), "entities": doc.get("entities", []),
        "evidence": doc.get("evidence", []), "chart": doc.get("chart"),
        "answer": doc["answer"], "reason": doc["reason"],
        "recommended_action": doc["recommended_action"], "confidence": doc["confidence"],
        "ai_provider": doc["ai_provider"],
        "generated_at": _aware(doc["updated_at"]).isoformat(),
        "feedback": {"useful": len(useful_by), "not_useful": len(not_useful_by), "mine": mine},
    }


def _read_cards(db: Database, dept: str, project_key: str, user_id: str | None) -> list[dict]:
    docs = list(db.ai_insights.find({"dept": dept, "project": project_key}))
    cards = [_public_card(d, user_id) for d in docs]
    cards.sort(key=lambda c: SEVERITY_ORDER.get(c["severity"], 9))
    return cards


def _is_stale(db: Database, dept: str, project_key: str) -> bool:
    latest = db.ai_insights.find_one({"dept": dept, "project": project_key},
                                      sort=[("updated_at", -1)])
    if not latest:
        return True
    age = dt.datetime.now(dt.timezone.utc) - _aware(latest["updated_at"])
    return age > dt.timedelta(hours=settings.insights_cache_hours)


def run_dept(db: Database, dept: str, provider: LLMProvider, user_id: str | None,
            force: bool = False, project: str | None = None) -> dict:
    title = DEPT_TITLE.get(dept, dept.title())
    project_key = project or "all"
    if not force and not _is_stale(db, dept, project_key):
        return {"dept": dept, "title": title, "project": project,
                "cards": _read_cards(db, dept, project_key, user_id),
                "generated_at": dt.datetime.now(dt.timezone.utc).isoformat(), "cached": True}

    findings: list[tuple[str, str, dict]] = []
    for finding_id, det_title, fn in detectors_for(dept):
        try:
            result = fn(db, project)
        except Exception:  # noqa: BLE001 - one bad detector must not kill the payload
            continue
        if result:
            findings.append((finding_id, det_title, result))

    now = dt.datetime.now(dt.timezone.utc)
    seen_ids: list[str] = []
    llm_calls = 0
    for finding_id, det_title, finding in findings:
        insight_id = f"{dept}:{project_key}:{finding_id}"
        seen_ids.append(insight_id)
        evidence = (finding.get("evidence") or [])[:8]

        if llm_calls < MAX_LLM_CARDS_PER_DEPT:
            envelope = narrate(
                SYSTEM, _user_prompt(det_title, finding), evidence, provider,
                echo_answer=finding["problem"],
                echo_reason=f"Detected by rule '{det_title}'.",
                echo_action=finding.get("action_hint", ""),
            )
            llm_calls += 1
        else:
            # Cost guard — beyond the per-run cap, narrate deterministically
            # regardless of provider rather than spend another LLM call.
            envelope = echo_envelope(
                finding["problem"], f"Detected by rule '{det_title}'.",
                finding.get("action_hint", ""), evidence)

        db.ai_insights.update_one(
            {"insight_id": insight_id},
            {"$set": {
                "insight_id": insight_id, "finding_id": finding_id, "dept": dept,
                "project": project_key,
                "title": det_title, "severity": finding.get("severity", "info"),
                "problem": finding["problem"], "metrics": finding.get("metrics", []),
                "entities": finding.get("entities", []), "evidence": evidence,
                "chart": finding.get("chart"), "action_hint": finding.get("action_hint", ""),
                "answer": envelope["answer"], "reason": envelope["reason"],
                "recommended_action": envelope["recommended_action"],
                "confidence": envelope["confidence"], "ai_provider": envelope["provider"],
                "updated_at": now,
            }, "$setOnInsert": {"useful_by": [], "not_useful_by": [], "created_at": now}},
            upsert=True,
        )

    # A detector that no longer fires means its problem is resolved — drop
    # the stale card, scoped to this (dept, project) pair only. `$nin` with
    # an empty list matches everything, so a scope with zero current
    # findings correctly clears every prior card for that scope.
    db.ai_insights.delete_many(
        {"dept": dept, "project": project_key, "insight_id": {"$nin": seen_ids}})

    return {"dept": dept, "title": title, "project": project,
            "cards": _read_cards(db, dept, project_key, user_id),
            "generated_at": now.isoformat(), "cached": False}
