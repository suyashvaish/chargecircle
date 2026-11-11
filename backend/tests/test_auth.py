from fastapi.testclient import TestClient


def test_user_registration_and_login(client: TestClient):
    # 1. Register new driver
    register_payload = {
        "email": "tester@chargecircle.in",
        "password": "Password1234!",
        "full_name": "Test Driver",
        "phone_number": "+91 99999 11111",
        "role": "driver"
    }
    res = client.post("/api/v1/auth/register", json=register_payload)
    assert res.status_code == 201, res.text
    data = res.json()
    assert data["email"] == "tester@chargecircle.in"
    assert any(r["role_name"] == "driver" for r in data["roles"])

    # 2. Duplicate registration refusal
    res_dup = client.post("/api/v1/auth/register", json=register_payload)
    assert res_dup.status_code == 400
    assert "already exists" in res_dup.json()["detail"]

    # 3. Login with valid credentials
    login_payload = {
        "email": "tester@chargecircle.in",
        "password": "Password1234!"
    }
    res_login = client.post("/api/v1/auth/login", json=login_payload)
    assert res_login.status_code == 200
    token_data = res_login.json()
    assert "access_token" in token_data
    token = token_data["access_token"]

    # 4. Access protected profile route
    res_me = client.get(
        "/api/v1/auth/me",
        headers={"Authorization": f"Bearer {token}"}
    )
    assert res_me.status_code == 200
    assert res_me.json()["email"] == "tester@chargecircle.in"

    # 5. Invalid password login
    res_bad = client.post("/api/v1/auth/login", json={"email": "tester@chargecircle.in", "password": "WrongPassword!"})
    assert res_bad.status_code == 401
