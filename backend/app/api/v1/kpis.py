"""KPI endpoints: snapshot read + recalculation trigger."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from pymongo.database import Database

from ...core import audit, rbac
from ...kpi import engine
from ..deps import get_current_user, get_db, require_role

router = APIRouter(tags=["kpis"])

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


@router.get("/kpis")
def snapshot(module: str | None = None, user: dict = Depends(get_current_user),
             db: Database = Depends(get_db)) -> list[dict]:
    """Latest KPI values, filtered to modules the caller may access."""
    allowed = [m for m in rbac.accessible_modules(user["role"])]
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
    own_dept = d["module"] in DEPT_MODULES.get(user.get("department") or "", set())
    if user["role"] not in ELEVATED_ROLES and not own_dept:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "no access to this KPI")
    return {"kpi_id": kpi_id, "name": d["name"], "unit": d.get("unit"),
            "points": engine.history(db, kpi_id)}


@router.post("/kpis/recalculate")
def recalculate(module: str | None = None,
                user: dict = Depends(require_role("super_admin")),
                db: Database = Depends(get_db)) -> list[dict]:
    result = engine.run_all(db, module)
    audit.record(db, actor_id=user["user_id"], action="kpi_recalculate",
                 meta={"module": module, "count": len(result)})
    return result
