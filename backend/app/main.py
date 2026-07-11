"""IO API entrypoint. All endpoints versioned under /api/v1 (PRD ARCH-007)."""
from __future__ import annotations

import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from . import __version__, db
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
    from .core.tls import use_os_trust_store
    use_os_trust_store()
    try:
        db.ensure_indexes(db.get_db())
    except Exception as exc:  # noqa: BLE001 - don't crash boot if Mongo is down
        log.warning("index setup skipped: %s", exc)


@app.get("/api/v1/health")
def health() -> dict:
    mongo, status = "up", "ok"
    try:
        db.ping()
    except Exception:  # noqa: BLE001
        mongo, status = "down", "degraded"
    return {"status": status, "service": "io-api", "version": __version__, "mongo": mongo}


app.include_router(api_router)
