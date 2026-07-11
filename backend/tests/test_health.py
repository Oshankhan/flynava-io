from fastapi.testclient import TestClient

from app import db
from app.api.deps import get_db
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
    assert body["mongo_error"] == "RuntimeError: no mongo"


def test_bootstrap_seed_populates_empty_db_once(db):
    app.dependency_overrides[get_db] = lambda: db
    try:
        db.users.delete_many({})
        assert db.users.count_documents({}) == 0

        r = client.post("/api/v1/bootstrap-seed")
        assert r.status_code == 200
        assert r.json()["status"] == "seeded"
        assert db.users.count_documents({}) > 0

        again = client.post("/api/v1/bootstrap-seed")
        assert again.status_code == 409
    finally:
        app.dependency_overrides.clear()
