"""Security middleware: hardening headers, request_id, per-identity rate limit.

Covers PRD SEC (clickjacking/XSS/MIME hardening), API-004 (rate limiting), and
API-005 (request_id for traceability). SQLi is mitigated by pymongo/pydantic;
IDOR by the RBAC + JWT layer.

Also home to AuditMiddleware (SEC-008 / analytics): every authenticated
mutating API call lands in `audit_logs` with actor + org dimensions, so the
analytics dataset is complete even where endpoints don't audit explicitly.
"""
from __future__ import annotations

import logging
import time
import uuid
from collections import defaultdict

import jwt as pyjwt
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse

from ..config import settings

SECURITY_HEADERS = {
    "X-Content-Type-Options": "nosniff",
    "X-Frame-Options": "DENY",
    "Referrer-Policy": "no-referrer",
    "X-XSS-Protection": "1; mode=block",
    "Strict-Transport-Security": "max-age=31536000; includeSubDomains",
}

_hits: dict[str, list[float]] = defaultdict(list)


def reset_rate_limit() -> None:
    _hits.clear()


class SecurityMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        if settings.rate_limit_enabled:
            ident = request.headers.get("authorization") or (
                request.client.host if request.client else "anon")
            cutoff = time.time() - 60
            recent = [t for t in _hits[ident] if t > cutoff]
            if len(recent) >= settings.rate_limit_per_min:
                return JSONResponse({"detail": "rate limit exceeded"}, status_code=429)
            recent.append(time.time())
            _hits[ident] = recent

        request_id = uuid.uuid4().hex
        response = await call_next(request)
        for key, value in SECURITY_HEADERS.items():
            response.headers[key] = value
        response.headers["X-Request-ID"] = request_id
        return response


_MUTATING = {"POST", "PATCH", "PUT", "DELETE"}
_AUDIT_SKIP = ("/api/v1/auth/",)  # login already audited; refresh is noise

log = logging.getLogger("io.audit")


class AuditMiddleware(BaseHTTPMiddleware):
    """Auto-audit every authenticated mutating API call.

    Resolves the DB through the app's dependency_overrides so tests (mongomock)
    and runtime share the same wiring. Auditing must never break a request —
    failures are logged and swallowed.
    """

    async def dispatch(self, request: Request, call_next):
        response = await call_next(request)
        path = request.url.path
        if (request.method not in _MUTATING or not path.startswith("/api/v1")
                or path.startswith(_AUDIT_SKIP)):
            return response
        try:
            self._record(request, response.status_code)
        except Exception as exc:  # noqa: BLE001 - audit is best-effort
            log.warning("audit skipped: %s", exc)
        return response

    def _record(self, request: Request, status_code: int) -> None:
        from ..core.security import decode_token
        from ..db import get_db

        auth = request.headers.get("authorization", "")
        actor_id = role = None
        if auth.lower().startswith("bearer "):
            try:
                payload = decode_token(auth.split(" ", 1)[1].strip())
                actor_id, role = payload.get("sub"), payload.get("role")
            except pyjwt.PyJWTError:
                pass

        provider = request.app.dependency_overrides.get(get_db, get_db)
        db = provider()
        meta = {"method": request.method, "path": path_template(request),
                "raw_path": request.url.path, "status_code": status_code,
                "role": role}
        if actor_id:
            u = db.users.find_one({"user_id": actor_id},
                                  {"level": 1, "team_id": 1, "department": 1})
            if u:
                meta.update({"level": u.get("level"), "team_id": u.get("team_id"),
                             "department": u.get("department")})
        from . import audit
        audit.record(db, actor_id=actor_id, action="api_call",
                     entity_type="http", entity_id=request.url.path, meta=meta)


def path_template(request: Request) -> str:
    """Route template (e.g. /api/v1/requests/{req_id}/approve) when resolvable,
    else the raw path — keeps analytics group-bys clean of ids."""
    route = request.scope.get("route")
    return getattr(route, "path", request.url.path)
