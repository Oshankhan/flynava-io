"""IO API entrypoint. All endpoints versioned under /api/v1 (PRD ARCH-007)."""
from __future__ import annotations

import logging

from fastapi import Depends, FastAPI, HTTPException, status as http_status
from fastapi.middleware.cors import CORSMiddleware
from pymongo.database import Database

from . import __version__, db
from .api.deps import get_current_user, get_db
from .api.v1 import api_router
from .config import settings
from .core.middleware import AuditMiddleware, SecurityMiddleware

log = logging.getLogger("io")

app = FastAPI(title="IO API", version=__version__)

app.add_middleware(SecurityMiddleware)
app.add_middleware(AuditMiddleware)
app.add_middleware(
    CORSMiddleware,
    allow_origins=[o.strip() for o in settings.cors_origins.split(",")],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
def _startup() -> None:
    # NOTE: use_os_trust_store() is intentionally NOT called here. It patches
    # Python's *global* default SSLContext to trust the OS cert store instead
    # of certifi — needed only for the OpenProject connector (see
    # core/tls.py), which calls it itself, scoped to when a sync actually
    # runs. Calling it here affected every TLS connection in the process,
    # including MongoDB, and a minimal deploy container's OS trust store may
    # not have the CA that signs Atlas's certificate chain.
    try:
        db.ensure_indexes(db.get_db())
    except Exception as exc:  # noqa: BLE001 - don't crash boot if Mongo is down
        log.warning("index setup skipped: %s", exc)


@app.get("/api/v1/health")
def health() -> dict:
    mongo, status, mongo_error = "up", "ok", None
    try:
        db.ping()
    except Exception as exc:  # noqa: BLE001
        mongo, status = "down", "degraded"
        mongo_error = f"{type(exc).__name__}: {exc}"[:300]
    body = {"status": status, "service": "io-api", "version": __version__, "mongo": mongo}
    if mongo_error:
        body["mongo_error"] = mongo_error
    return body


@app.post("/api/v1/bootstrap-seed")
def bootstrap_seed(database: Database = Depends(get_db)) -> dict:
    """One-time demo-data seed for a freshly deployed, empty database.

    No auth required, because there are no users yet to authenticate as —
    safety comes from the guard below instead: it refuses to run against a
    database that already has users, so it can never be used to wipe or
    reset a live environment.
    """
    from .services.seed import seed

    if database.users.count_documents({}) > 0:
        raise HTTPException(http_status.HTTP_409_CONFLICT,
                            "already seeded (users collection is non-empty)")
    seed(database)
    return {"status": "seeded"}


@app.post("/api/v1/bootstrap-seed/refresh-demo")
def bootstrap_seed_refresh_demo(
    database: Database = Depends(get_db),
    user: dict = Depends(get_current_user),
) -> dict:
    """Refresh of the CEO-demo seed data against an already-seeded (live)
    database — departments/teams/users, projects/tasks, KPI values,
    automation scripts, product docs, attendance, and meetings.

    Unlike `seed()` (used by `/bootstrap-seed` above), this never touches
    payslips or leave requests — see `services.seed.seed_demo_extras` for
    why that distinction matters. Gated to super_admin since real users
    already exist at this point.
    """
    if user.get("role") != "super_admin":
        raise HTTPException(http_status.HTTP_403_FORBIDDEN, "super_admin only")
    from .services.seed import seed_demo_extras

    return {"status": "refreshed", **seed_demo_extras(database)}


app.include_router(api_router)
