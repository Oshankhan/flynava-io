"""Expose the RBAC matrix (super_admin only) for the admin UI."""
from __future__ import annotations

from fastapi import APIRouter, Depends

from ...core import rbac as rbac_core
from ..deps import require_role

router = APIRouter(tags=["rbac"])


@router.get("/rbac/matrix")
def matrix(_: dict = Depends(require_role("super_admin"))) -> dict:
    return {
        "roles": rbac_core.ROLES,
        "modules": rbac_core.MODULES,
        "matrix": rbac_core.MATRIX,
        "department_modules": {
            dept: sorted(modules)
            for dept, modules in rbac_core.DEPARTMENT_MODULES.items()
        },
        "role_home_modules": {
            role: sorted(modules)
            for role, modules in rbac_core.ROLE_HOME_MODULES.items()
        },
    }
