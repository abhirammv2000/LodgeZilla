"""Shared fixtures.

These used to be integration tests against a real, manually-seeded MongoDB:
a broken login endpoint made every test SKIP rather than fail, which is
exactly the kind of thing a CI gate must not do (a real regression would
still show green). mongomock replaces that with an in-memory MongoDB the
test process owns end to end, so the suite runs the same way on a laptop
with no services running as it does in CI.

pymongo.MongoClient and redis.StrictRedis are both patched before app.db (and
everything that imports it) is ever imported, so its module-level client
constructions transparently get the fakes instead. app/db.py itself is not
touched: the fakes are injected at the boundary, not built into production
code. Redis specifically matters for test speed, not just isolation: with no
real Redis running, every push_to_redis call was retrying a refused
connection before giving up, which is what made the previous, live-service
version of this suite take minutes instead of seconds.
"""
from __future__ import annotations

import fakeredis
import mongomock
import pymongo
import redis

pymongo.MongoClient = mongomock.MongoClient
redis.StrictRedis = fakeredis.FakeStrictRedis

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from app.db import user_collection  # noqa: E402
from app.main import app  # noqa: E402

TEST_USER_ID = 1
TEST_USER_NAME = "test_user"
TEST_USER_PASSWORD = "correct horse battery staple"


@pytest.fixture(scope="session", autouse=True)
def seed_user():
    """One known account, seeded with a plaintext password on purpose.

    Plaintext, not pre-hashed: the first successful login is what exercises
    the lazy migration to Argon2 in auth.get_user, the same path a real
    leftover account from before that change would take.
    """
    user_collection.insert_one(
        {
            "user_id": TEST_USER_ID,
            "name": TEST_USER_NAME,
            "password": TEST_USER_PASSWORD,
            "userType": "host",
            "trips": {},
        }
    )


@pytest.fixture(scope="session")
def client():
    return TestClient(app)


@pytest.fixture(scope="session")
def access_token(client, seed_user):
    response = client.post(
        "/api/auth/token", json={"name": TEST_USER_NAME, "password": TEST_USER_PASSWORD}
    )
    assert response.status_code == 200, response.text
    return response.json()["access_token"]


@pytest.fixture(scope="session")
def auth_headers(access_token):
    return {"Authorization": f"Bearer {access_token}"}
