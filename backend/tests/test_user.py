from .conftest import TEST_USER_NAME, TEST_USER_PASSWORD


def test_login_with_valid_credentials(client):
    response = client.post(
        f"/api/auth/token?name={TEST_USER_NAME}&password={TEST_USER_PASSWORD}"
    )
    assert response.status_code == 200
    assert "access_token" in response.json()


def test_login_with_invalid_credentials(client):
    response = client.post(
        "/api/auth/token?name=invalid_user&password=invalid_password"
    )
    assert response.status_code == 401
    assert "access_token" not in response.json()


def test_login_requires_both_name_and_password(client):
    assert client.post("/api/auth/token?name=test_user").status_code == 422
    assert client.post("/api/auth/token?password=test_password").status_code == 422


def test_create_user(client):
    user_data = {
        "name": "test_user",
        "password": "test_password",
        "userType": "regular",
    }
    response = client.post("/api/auth/create", json=user_data)
    assert response.status_code == 200
    assert response.json()["id"] is not None
