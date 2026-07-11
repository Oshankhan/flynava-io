from app.core.security import (
    create_refresh_token,
    hash_password,
    verify_password,
)


def test_password_hash_roundtrip():
    h = hash_password("secret123", rounds=4)
    assert h != "secret123"
    assert verify_password("secret123", h)
    assert not verify_password("wrong", h)


def test_login_success_returns_tokens_and_user(client):
    r = client.post("/api/v1/auth/login",
                    json={"email": "leadership@flynava.ai", "password": "Passw0rd!"})
    assert r.status_code == 200
    body = r.json()
    assert body["access_token"] and body["refresh_token"]
    assert body["user"]["role"] == "leadership"


def test_login_wrong_password_401(client):
    r = client.post("/api/v1/auth/login",
                    json={"email": "leadership@flynava.ai", "password": "nope"})
    assert r.status_code == 401


def test_me_requires_auth(client):
    assert client.get("/api/v1/auth/me").status_code == 401


def test_me_returns_modules_for_role(client, auth_header):
    r = client.get("/api/v1/auth/me", headers=auth_header("marketing@flynava.ai"))
    assert r.status_code == 200
    mods = r.json()["modules"]
    assert mods.get("marketing_sales") == "full"
    assert "finance" not in mods  # marketing has no finance access


def test_refresh_issues_new_access_token(client):
    token = create_refresh_token("u_lead")
    r = client.post("/api/v1/auth/refresh", json={"refresh_token": token})
    assert r.status_code == 200
    assert r.json()["access_token"]


def test_access_token_rejected_as_refresh(client):
    login = client.post("/api/v1/auth/login",
                        json={"email": "leadership@flynava.ai", "password": "Passw0rd!"})
    access = login.json()["access_token"]
    r = client.post("/api/v1/auth/refresh", json={"refresh_token": access})
    assert r.status_code == 401
