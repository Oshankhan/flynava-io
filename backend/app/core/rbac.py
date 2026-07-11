"""Role-Based Access Control matrix (PRD section 12).

Levels are qualitative scopes. `NONE` means no access. `access_level()` returns
the scope string so endpoints and the frontend can tailor what is shown; the
`has_access()` helper is the coarse allow/deny gate used by route dependencies.
"""
from __future__ import annotations

NONE = "none"

# Roles
ROLES = [
    "super_admin",
    "leadership",
    "manager",
    "team_lead",
    "hr",
    "employee",
    "marketing",
    "investor",
    "partner",
]

# Org hierarchy levels (PRD hierarchy: L4 CEO/founder → L3 dept heads →
# L2 team leads → L1 executives). Stored per user; these are the defaults a
# role gets when a user document carries no explicit `level`. External roles
# (investor/partner) sit outside the ladder → level 0.
DEFAULT_LEVEL = {
    "super_admin": 4,
    "leadership": 4,
    "manager": 3,
    "hr": 3,
    "marketing": 3,
    "team_lead": 2,
    "employee": 1,
    "investor": 0,
    "partner": 0,
}


def user_level(user: dict) -> int:
    lvl = user.get("level")
    return lvl if isinstance(lvl, int) else DEFAULT_LEVEL.get(user.get("role", ""), 1)

# Modules
MODULES = [
    "operations",
    "hr",
    "finance",
    "marketing_sales",
    "recruitment",
    "compliance",
    "customer_support",
    "product_dev",
    "awards",
    "ai_insights",
    "admin_panel",
]

# module -> role -> access level (verbatim from PRD RBAC matrix)
MATRIX: dict[str, dict[str, str]] = {
    "operations": {
        "super_admin": "full", "leadership": "full", "manager": "team",
        "team_lead": "team", "hr": "read", "employee": "own",
        "marketing": NONE, "investor": "summary", "partner": "project",
    },
    "hr": {
        "super_admin": "full", "leadership": "summary", "manager": "team",
        "team_lead": "own", "hr": "full", "employee": "own",
        "marketing": NONE, "investor": NONE, "partner": NONE,
    },
    "finance": {
        "super_admin": "full", "leadership": "full", "manager": "budget",
        "team_lead": NONE, "hr": NONE, "employee": NONE,
        "marketing": NONE, "investor": "summary", "partner": NONE,
    },
    "marketing_sales": {
        "super_admin": "full", "leadership": "full", "manager": "team",
        "team_lead": NONE, "hr": NONE, "employee": NONE,
        "marketing": "full", "investor": "summary", "partner": NONE,
    },
    "recruitment": {
        "super_admin": "full", "leadership": "summary", "manager": "team",
        "team_lead": "team", "hr": "full", "employee": "own",
        "marketing": NONE, "investor": NONE, "partner": NONE,
    },
    "compliance": {
        "super_admin": "full", "leadership": "summary", "manager": "alert",
        "team_lead": "own_tasks", "hr": "alert", "employee": "own_tasks",
        "marketing": NONE, "investor": NONE, "partner": NONE,
    },
    "customer_support": {
        "super_admin": "full", "leadership": "full", "manager": "team",
        "team_lead": NONE, "hr": NONE, "employee": NONE,
        "marketing": NONE, "investor": "summary", "partner": "sla",
    },
    "product_dev": {
        "super_admin": "full", "leadership": "full", "manager": "team",
        "team_lead": "team", "hr": NONE, "employee": "own",
        "marketing": NONE, "investor": "summary", "partner": "project",
    },
    "awards": {
        "super_admin": "full", "leadership": "full", "manager": "full",
        "team_lead": "full", "hr": "full", "employee": "read_react",
        "marketing": "read", "investor": NONE, "partner": NONE,
    },
    "ai_insights": {
        "super_admin": "full", "leadership": "full", "manager": "team",
        "team_lead": "team", "hr": "hr", "employee": "own",
        "marketing": "mkt", "investor": "summary", "partner": NONE,
    },
    "admin_panel": {
        "super_admin": "full", "leadership": NONE, "manager": NONE,
        "team_lead": NONE, "hr": NONE, "employee": NONE,
        "marketing": NONE, "investor": NONE, "partner": NONE,
    },
}


def access_level(role: str, module: str) -> str:
    return MATRIX.get(module, {}).get(role, NONE)


def has_access(role: str, module: str) -> bool:
    return access_level(role, module) != NONE


def accessible_modules(role: str) -> dict[str, str]:
    """Map of module -> level for every module the role can see (drives nav)."""
    return {m: access_level(role, m) for m in MODULES if has_access(role, m)}
