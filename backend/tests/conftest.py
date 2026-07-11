"""Shared test fixtures: mongomock DB + seeded TestClient."""
from __future__ import annotations

import tempfile

import mongomock
import pytest
from fastapi.testclient import TestClient

from app.config import settings
from app.api.deps import get_db
from app.main import app
from app.services.seed import DEMO_PASSWORD, seed

# Fast hashes in tests (real runtime uses cost 12 per SEC-003).
settings.bcrypt_rounds = 4
# Rate limiting off by default in tests (a dedicated test re-enables it).
settings.rate_limit_enabled = False
# Uploads land in a temp dir, never in the repo.
settings.upload_dir = tempfile.mkdtemp(prefix="io_uploads_")
# Tests never call live AI providers.
settings.openai_api_key = ""
settings.anthropic_api_key = ""


@pytest.fixture()
def db():
    database = mongomock.MongoClient()["io_test"]
    seed(database)
    return database


@pytest.fixture()
def client(db):
    app.dependency_overrides[get_db] = lambda: db
    yield TestClient(app)
    app.dependency_overrides.clear()


def login(client: TestClient, email: str, password: str = DEMO_PASSWORD) -> str:
    r = client.post("/api/v1/auth/login", json={"email": email, "password": password})
    assert r.status_code == 200, r.text
    return r.json()["access_token"]


@pytest.fixture()
def auth_header(client):
    def _make(email: str) -> dict:
        return {"Authorization": f"Bearer {login(client, email)}"}

    return _make
