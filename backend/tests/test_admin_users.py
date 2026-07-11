def test_admin_creates_user_who_can_login(client, auth_header):
    r = client.post("/api/v1/admin/users", headers=auth_header("admin@flynava.ai"),
                    json={"name": "Nina New", "email": "nina@flynava.ai",
                          "role": "manager", "password": "S3cret!pw"})
    assert r.status_code == 200, r.text
    assert "password_hash" not in r.json()
    login = client.post("/api/v1/auth/login",
                        json={"email": "nina@flynava.ai", "password": "S3cret!pw"})
    assert login.status_code == 200
    assert login.json()["user"]["role"] == "manager"


def test_duplicate_email_conflict(client, auth_header):
    r = client.post("/api/v1/admin/users", headers=auth_header("admin@flynava.ai"),
                    json={"name": "Dup", "email": "hr@flynava.ai",
                          "role": "hr", "password": "x1234567"})
    assert r.status_code == 409


def test_deactivate_blocks_login(client, auth_header):
    client.post("/api/v1/admin/users", headers=auth_header("admin@flynava.ai"),
                json={"name": "Tim Temp", "email": "tim@flynava.ai",
                      "role": "employee", "password": "S3cret!pw"})
    uid = [u for u in client.get("/api/v1/users",
                                 headers=auth_header("admin@flynava.ai")).json()
           if u["email"] == "tim@flynava.ai"][0]["user_id"]
    r = client.patch(f"/api/v1/admin/users/{uid}",
                     headers=auth_header("admin@flynava.ai"),
                     json={"status": "inactive"})
    assert r.status_code == 200
    login = client.post("/api/v1/auth/login",
                        json={"email": "tim@flynava.ai", "password": "S3cret!pw"})
    assert login.status_code == 403


def test_invalid_role_rejected(client, auth_header):
    r = client.post("/api/v1/admin/users", headers=auth_header("admin@flynava.ai"),
                    json={"name": "Bad", "email": "bad@flynava.ai",
                          "role": "wizard", "password": "x1234567"})
    assert r.status_code == 400


def test_non_admin_cannot_manage_users(client, auth_header):
    r = client.post("/api/v1/admin/users", headers=auth_header("hr@flynava.ai"),
                    json={"name": "X", "email": "x@flynava.ai",
                          "role": "employee", "password": "x1234567"})
    assert r.status_code == 403
