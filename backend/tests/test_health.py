from fastapi.testclient import TestClient

from app import db
from app.main import app

client = TestClient(app)


def test_health_ok_when_mongo_up(monkeypatch):
    monkeypatch.setattr(db, "ping", lambda: None)
    r = client.get("/api/v1/health")
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "ok"
    assert body["mongo"] == "up"
    assert body["service"] == "io-api"
    assert body["version"]


def test_health_degraded_when_mongo_down(monkeypatch):
    def boom():
        raise RuntimeError("no mongo")

    monkeypatch.setattr(db, "ping", boom)
    r = client.get("/api/v1/health")
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "degraded"
    assert body["mongo"] == "down"
