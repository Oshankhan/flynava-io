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


app.include_router(api_router)
