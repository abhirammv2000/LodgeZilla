from app.db import user_collection

from .conftest import TEST_USER_NAME, TEST_USER_PASSWORD


def test_login_with_valid_credentials(client, seed_user):
    response = client.post(
        "/api/auth/token", json={"name": TEST_USER_NAME, "password": TEST_USER_PASSWORD}
    )
    assert response.status_code == 200
    assert "access_token" in response.json()


def test_login_with_invalid_credentials(client, seed_user):
    response = client.post(
        "/api/auth/token", json={"name": "invalid_user", "password": "invalid_password"}
    )
    assert response.status_code == 401
    assert "access_token" not in response.json()


def test_login_requires_both_name_and_password(client):
    assert client.post("/api/auth/token", json={"name": "x"}).status_code == 422
    assert client.post("/api/auth/token", json={"password": "x"}).status_code == 422


def test_login_upgrades_a_plaintext_password_to_argon2(client):
    """A fresh user of its own, not the shared session-scoped seed_user: that
    account gets logged into by other tests too, and the first successful
    login of *any* test would already have upgraded it, making a shared user
    unsuitable for asserting on the "before" state."""
    user_collection.insert_one(
        {"user_id": 2, "name": "legacy_plaintext_user", "password": "hunter2", "trips": {}}
    )
    before = user_collection.find_one({"user_id": 2})
    assert before["password"] == "hunter2"

    response = client.post(
        "/api/auth/token", json={"name": "legacy_plaintext_user", "password": "hunter2"}
    )
    assert response.status_code == 200

    after = user_collection.find_one({"user_id": 2})
    assert after["password"].startswith("$argon2")
    assert after["password"] != "hunter2"

    # And the upgraded hash still logs the account in on the next attempt.
    response = client.post(
        "/api/auth/token", json={"name": "legacy_plaintext_user", "password": "hunter2"}
    )
    assert response.status_code == 200


def test_create_user(client):
    user_data = {
        "user_id": 999,
        "name": "brand_new_user",
        "password": "test_password",
        "userType": "regular",
    }
    response = client.post("/api/auth/create", json=user_data)
    assert response.status_code == 200
    assert response.json()["id"] is not None
    assert "password" not in response.json()

    stored = user_collection.find_one({"user_id": 999})
    assert stored["password"].startswith("$argon2")
    assert stored["password"] != "test_password"
