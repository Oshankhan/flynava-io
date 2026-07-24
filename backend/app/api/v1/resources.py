"""Resource Management dashboard — team capacity, workload heatmap, top
performers, at-risk resources, project resource status, department work
lifecycles, and derived AI insights. See services/resource_mgmt.py for the
derivation logic (there is no stored utilization/capacity metric anywhere in
this DB — every number here is computed live from users/teams/tasks/
projects)."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from pymongo.database import Database

from ...core.rbac import user_level
from ...services import resource_mgmt
from ..deps import get_current_user, get_db

router = APIRouter(tags=["resources"])


@router.get("/resources/dashboard")
def dashboard(user: dict = Depends(get_current_user), db: Database = Depends(get_db)) -> dict:
    if user_level(user) < 3:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "department heads and above only")
    return resource_mgmt.build_dashboard(db, user)
