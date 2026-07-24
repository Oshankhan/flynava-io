"""Shared LLM narration helpers (Answer / Reason / Action / Confidence envelope).

Ask IO (`ai/rag.py`) originated the JSON-parsing + confidence-scoring logic;
this module lifts it out so the two newer AI-first surfaces — KPI
explainability (`kpi/explain.py`) and department insight detectors
(`insights/engine.py`) — share one implementation instead of duplicating it.

`narrate()` is the single entrypoint those two use: on the deterministic
EchoProvider (no API key configured) it builds the envelope directly from the
caller-supplied text instead of calling `provider.complete()`, so insight/KPI
cards are still useful with zero API keys — the whole point of a detector
producing structured findings before an LLM ever gets involved. With a real
provider it calls the model and never raises (a bad/unavailable LLM degrades
to a clear message, it doesn't 500 the dashboard).
"""
from __future__ import annotations

import json

from .provider import LLMProvider


def _unwrap_double_wrapped(parsed: dict) -> dict:
    """Verified live: a large evidence payload (14 items for one assignee)
    made the model stringify its WHOLE envelope again as the value of the
    outer "answer" key, leaving reason/recommended_action empty — instead of
    plain prose for "answer" as instructed. Bounded one-level unwrap: if
    "answer" is a string that itself parses as a dict with its own "answer"
    key, prefer that inner envelope."""
    inner = parsed.get("answer")
    if not isinstance(inner, str):
        return parsed
    stripped = inner.strip()
    if not (stripped.startswith("{") and '"answer"' in stripped):
        return parsed
    try:
        nested = json.loads(stripped)
    except (json.JSONDecodeError, TypeError):
        return parsed
    if not isinstance(nested, dict) or "answer" not in nested:
        return parsed
    return {
        "answer": nested.get("answer", ""),
        "reason": nested.get("reason") or parsed.get("reason", ""),
        "recommended_action": nested.get("recommended_action") or parsed.get("recommended_action", ""),
    }


def parse_llm_json(raw: str) -> dict:
    """Parse model output; tolerate ```json fences and an occasional
    double-wrapped envelope (see `_unwrap_double_wrapped`)."""
    cleaned = raw.strip()
    if cleaned.startswith("```"):
        first_newline = cleaned.find("\n")
        cleaned = cleaned[first_newline + 1:] if first_newline != -1 else cleaned
        cleaned = cleaned.rsplit("```", 1)[0].strip()
    try:
        parsed = json.loads(cleaned)
    except (json.JSONDecodeError, TypeError):
        return {"answer": raw, "reason": "", "recommended_action": ""}
    return _unwrap_double_wrapped(parsed) if isinstance(parsed, dict) else parsed


def confidence_from_evidence(evidence: list[str]) -> str:
    if len(evidence) >= 3:
        return "High"
    return "Medium" if evidence else "Low"


def as_text(value) -> str:
    """Coerce a parsed JSON field to a plain string. The envelope's contract
    with the frontend is that answer/reason/recommended_action are always
    strings — but nothing stops a model from nesting an object or list under
    one of those keys instead of writing prose (seen live: a bug-list
    question got an `answer` value shaped like a single bug record). Without
    this, that object passes straight through to React as a raw child and
    crashes the page. JSON-stringify anything that isn't already text."""
    if isinstance(value, str):
        return value
    if value is None:
        return ""
    try:
        return json.dumps(value, ensure_ascii=False)
    except (TypeError, ValueError):
        return str(value)


def echo_envelope(answer: str, reason: str, action: str, evidence: list[str]) -> dict:
    return {
        "answer": answer, "reason": reason, "recommended_action": action,
        "confidence": confidence_from_evidence(evidence), "provider": "echo",
    }


def llm_envelope(system: str, user: str, evidence: list[str], provider: LLMProvider) -> dict:
    """Calls `provider.complete()`, parses the JSON envelope, never raises."""
    try:
        parsed = parse_llm_json(provider.complete(system, user))
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
        "recommended_action": as_text(parsed.get("recommended_action", "")),
        "confidence": confidence_from_evidence(evidence),
        "provider": provider.name,
    }


def narrate(system: str, user: str, evidence: list[str], provider: LLMProvider,
            *, echo_answer: str, echo_reason: str, echo_action: str) -> dict:
    """Route to a deterministic envelope on EchoProvider, a real LLM call
    otherwise. `echo_*` should already be fully-formed, useful text derived
    from the caller's structured data (a KPI's computation trace, a
    detector's finding) — not a generic "AI is disabled" placeholder."""
    if provider.name == "echo":
        return echo_envelope(echo_answer, echo_reason, echo_action, evidence)
    return llm_envelope(system, user, evidence, provider)
