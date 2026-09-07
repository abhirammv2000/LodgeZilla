"""Shared fixtures.

These are integration tests: they expect a running API backed by a seeded
MongoDB. Override the seeded account with TEST_USER_NAME / TEST_USER_PASSWORD.
"""
import os

import pytest
from fastapi.testclient import TestClient

from app.main import app

TEST_USER_NAME = os.getenv("TEST_USER_NAME", "AnirudhMaiya")
TEST_USER_PASSWORD = os.getenv("TEST_USER_PASSWORD", "123456")


@pytest.fixture(scope="session")
def client():
    return TestClient(app)


@pytest.fixture(scope="session")
def access_token(client):
    response = client.post(
        f"/api/auth/token?name={TEST_USER_NAME}&password={TEST_USER_PASSWORD}"
    )
    if response.status_code != 200:
        pytest.skip(f"could not log in as {TEST_USER_NAME}; is the database seeded?")
    return response.json()["access_token"]


@pytest.fixture(scope="session")
def auth_headers(access_token):
    return {"Authorization": f"Bearer {access_token}"}
