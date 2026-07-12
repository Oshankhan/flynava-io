from app.config import settings
from app.core.middleware import reset_rate_limit


def test_security_headers_and_request_id(client):
    r = client.get("/api/v1/health")
    assert r.headers["X-Content-Type-Options"] == "nosniff"
    assert r.headers["X-Frame-Options"] == "DENY"
    assert r.headers["Referrer-Policy"] == "no-referrer"
    assert r.headers.get("X-Request-ID")


def test_rate_limit_returns_429_when_exceeded(client):
    reset_rate_limit()
    settings.rate_limit_enabled = True
    settings.rate_limit_per_min = 3
    try:
        codes = [client.get("/api/v1/health").status_code for _ in range(5)]
        assert codes.count(429) >= 1
        assert 429 in codes
    finally:
        settings.rate_limit_enabled = False
        settings.rate_limit_per_min = 100
        reset_rate_limit()


def test_audit_trail_written_on_login(client, db):
    client.post("/api/v1/auth/login",
                json={"email": "harsha.varlani@flynava.ai", "password": "Passw0rd!"})
    assert db.audit_logs.count_documents({"action": "login"}) >= 1
