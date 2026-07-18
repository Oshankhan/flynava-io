"""KPI endpoints: snapshot read + recalculation trigger."""
from __future__ import annotations

import datetime as dt

from fastapi import APIRouter, Depends, HTTPException, status
from pymongo.database import Database

from ...ai.narrate import narrate
from ...ai.provider import get_provider
from ...core import audit, rbac
from ...kpi import engine
from ...kpi import explain as kpi_explain
from ..deps import get_current_user, get_db, require_role

router = APIRouter(tags=["kpis"])

EXPLAIN_SYSTEM = (
    "You are Ask IO, FlyNava's organizational intelligence assistant. You are "
    "explaining exactly how one KPI number was computed to a non-technical "
    "executive who asked 'how did you come up with this number?'. Answer ONLY "
    "from the provided formula, computation, and evidence — never invent "
    "facts or numbers not present below. Respond as a compact JSON object "
    "with keys 'answer', 'reason', 'recommended_action'."
)

# The RBAC MATRIX gates modules by literal role name (a "marketing" role,
# an "hr" role, ...) — a holdover from the flat-role dashboards. Team leads
# and executives are `team_lead`/`employee` with a `department` instead, so
# module access for THEM is department-based: an eng dev sees ops/product KPIs,
# a marketing exec sees marketing_sales, etc. Elevated roles see everything.
DEPT_MODULES = {
    "eng": {"operations", "product_dev"},
    "fin": {"finance"},
    "hr": {"hr", "recruitment"},
    "mkt": {"marketing_sales"},
}
ELEVATED_ROLES = ("super_admin", "leadership", "manager")


def _require_kpi_access(user: dict, d: dict) -> None:
    own_dept = d["module"] in DEPT_MODULES.get(user.get("department") or "", set())
    if user["role"] not in ELEVATED_ROLES and not own_dept:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "no access to this KPI")


@router.get("/kpis")
def snapshot(module: str | None = None, user: dict = Depends(get_current_user),
             db: Database = Depends(get_db)) -> list[dict]:
    """Latest KPI values, filtered to modules the caller may access."""
    allowed = list(rbac.accessible_modules_for_user(user))
    modules = [module] if module and module in allowed else allowed
    return engine.latest_snapshot(db, modules)


@router.get("/kpis/{kpi_id}/history")
def kpi_history(kpi_id: str, user: dict = Depends(get_current_user),
                db: Database = Depends(get_db)) -> dict:
    """12-month trend for one KPI (e.g. a Finance TL's revenue/expense card,
    or a Marketing exec's lead-volume trend) — reuses the same points shape
    dashboards embed. Access: elevated roles always; team_lead/employee only
    for their own department's modules (see DEPT_MODULES above)."""
    d = db.kpi_defs.find_one({"kpi_id": kpi_id})
    if not d:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "kpi not found")
    _require_kpi_access(user, d)
    return {"kpi_id": kpi_id, "name": d["name"], "unit": d.get("unit"),
            "points": engine.history(db, kpi_id)}


def _echo_action(exp: dict) -> str:
    src = exp["source"]
    if src["live"]:
        return "No action needed — this recomputes automatically on every OpenProject sync."
    if src["system"] == "None (demo)":
        return src["note"]
    return ("This reflects seed/demo data — connect the OpenProject integration "
            "(Admin → Integrations) for live numbers.")


def _evidence_lines(exp: dict) -> list[str]:
    lines = [exp["computation"]]
    for e in exp.get("evidence", []):
        extra = " · ".join(f"{k}: {v}" for k, v in (e.get("extra") or {}).items() if v)
        id_prefix = f"#{e['id']} " if e.get("id") else ""
        label = f"{id_prefix}{(e.get('kind') or 'item').title()}: {e.get('label')}"
        lines.append(f"{label} ({extra})" if extra else label)
    return lines


def _narrate_explanation(db: Database, kpi_id: str, value, exp: dict, provider) -> dict:
    """Cached per (kpi_id, value, provider) so re-opening the same card's
    drawer — or another viewer opening it — doesn't re-call the LLM until the
    underlying number actually changes."""
    cached = db.kpi_explanations.find_one({"kpi_id": kpi_id})
    if cached and cached.get("value") == value and cached.get("provider") == provider.name:
        return {"answer": cached["answer"], "reason": cached["reason"],
                "recommended_action": cached["recommended_action"],
                "confidence": cached["confidence"], "ai_provider": cached["provider"],
                "generated_at": cached["generated_at"].isoformat()}

    lines = _evidence_lines(exp)
    context = "\n".join(f"- {line}" for line in lines)
    user_msg = f"KPI formula: {exp['formula_text']}\n\nComputation & evidence:\n{context}"
    envelope = narrate(
        EXPLAIN_SYSTEM, user_msg, lines, provider,
        echo_answer=exp["computation"],
        echo_reason=exp["formula_text"],
        echo_action=_echo_action(exp),
    )
    now = dt.datetime.now(dt.timezone.utc)
    db.kpi_explanations.update_one(
        {"kpi_id": kpi_id},
        {"$set": {"kpi_id": kpi_id, "value": value, "provider": envelope["provider"],
                  "answer": envelope["answer"], "reason": envelope["reason"],
                  "recommended_action": envelope["recommended_action"],
                  "confidence": envelope["confidence"], "generated_at": now}},
        upsert=True,
    )
    return {"answer": envelope["answer"], "reason": envelope["reason"],
            "recommended_action": envelope["recommended_action"],
            "confidence": envelope["confidence"], "ai_provider": envelope["provider"],
            "generated_at": now.isoformat()}


@router.get("/kpis/{kpi_id}/explain")
def explain_kpi(kpi_id: str, user: dict = Depends(get_current_user),
                db: Database = Depends(get_db)) -> dict:
    """'How did you come up with this number?' — formula, real arithmetic,
    underlying evidence records, source/freshness, and an AI narrative for
    one KPI. Same RBAC scope as `/kpis/{kpi_id}/history`."""
    d = db.kpi_defs.find_one({"kpi_id": kpi_id})
    if not d:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "kpi not found")
    _require_kpi_access(user, d)

    # Recompute live (rather than reading the last stored kpi_values row) so
    # the headline value always matches the arithmetic and evidence shown
    # below it — a stale card (recalculate hasn't run since data changed)
    # would otherwise show one number while its own explanation justified a
    # different one.
    value = engine.compute(db, d)
    if value is None:
        row = db.kpi_values.find_one({"kpi_id": kpi_id}, sort=[("calculated_at", -1)])
        value = row["value"] if row else None
    rag = engine.rag_status(value, d.get("target"), d.get("direction", "higher"))

    exp = kpi_explain.explain(db, d, value)
    narrative = _narrate_explanation(db, kpi_id, value, exp, get_provider())

    return {
        "kpi_id": kpi_id, "name": d["name"], "module": d["module"],
        "unit": d.get("unit"), "target": d.get("target"),
        "direction": d.get("direction", "higher"), "value": value, "rag": rag,
        "formula_text": exp["formula_text"], "computation": exp["computation"],
        "inputs": exp["inputs"], "evidence": exp["evidence"], "source": exp["source"],
        "history": engine.history(db, kpi_id),
        **narrative,
    }


@router.post("/kpis/recalculate")
def recalculate(module: str | None = None,
                user: dict = Depends(require_role("super_admin")),
                db: Database = Depends(get_db)) -> list[dict]:
    result = engine.run_all(db, module)
    audit.record(db, actor_id=user["user_id"], action="kpi_recalculate",
                 meta={"module": module, "count": len(result)})
    return result
