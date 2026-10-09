"""Many people reserving the same dates at the same moment, against a real MongoDB.

mongomock cannot answer this. It runs inside the test process and says nothing about whether
MongoDB applies the conditional update atomically, which is the whole defence against double
booking. So these tests need a server:

    docker run -d -p 27017:27017 mongo:7
    LODGEZILLA_TEST_MONGO_URI=mongodb://localhost:27017 pytest tests/test_booking_concurrency.py

They are skipped when the variable is not set. CI sets it with a MongoDB service container.

The first test is a control. It runs the old behaviour (an unconditional push) through the same
harness and expects it to double-book. If that ever stops happening, the harness is no longer
racing anything and the tests after it prove nothing.
"""
import os
import threading
from concurrent.futures import ThreadPoolExecutor

import pytest
from fastapi.testclient import TestClient

# conftest replaces pymongo.MongoClient with mongomock's, but not this module's own name for it
from pymongo.mongo_client import MongoClient as RealMongoClient

from .conftest import TEST_USER_ID, TEST_USER_NAME

MONGO_URI = os.environ.get("LODGEZILLA_TEST_MONGO_URI")
pytestmark = pytest.mark.skipif(
    not MONGO_URI, reason="set LODGEZILLA_TEST_MONGO_URI to run against a real MongoDB"
)

CALLERS = 24
ROUNDS = 15


@pytest.fixture
def real_collections(monkeypatch):
    client = RealMongoClient(MONGO_URI, serverSelectionTimeoutMS=3000)
    database = client["lodgezilla_concurrency_test"]
    listings, users = database["listings"], database["users"]
    listings.drop()
    users.drop()
    users.insert_one(
        {"user_id": TEST_USER_ID, "name": TEST_USER_NAME, "userType": "host", "trips": {}}
    )
    monkeypatch.setattr("app.routes.bookings.listing_collection", listings)
    monkeypatch.setattr("app.routes.bookings.user_collection", users)
    yield listings
    client.drop_database("lodgezilla_concurrency_test")
    client.close()


def _race(callers, work):
    """Run work(i) on `callers` threads that all start at the same moment; return the results."""
    barrier = threading.Barrier(callers)

    def run(i):
        barrier.wait()
        return work(i)

    with ThreadPoolExecutor(max_workers=callers) as pool:
        return list(pool.map(run, range(callers)))


def _reserve(property_id, start, end, headers):
    from app.main import app

    client = TestClient(app)  # one per thread, they are not meant to be shared
    response = client.post(
        f"/api/bookings/reserve/{property_id}",
        json={"start_date": start, "end_date": end},
        headers=headers,
    )
    return response.status_code


def test_control_an_unconditional_push_double_books(real_collections):
    """The old behaviour. Every caller is told yes."""
    doubled = 0
    for round_number in range(ROUNDS):
        property_id = 40000 + round_number
        real_collections.insert_one({"property_id": property_id, "booking_history": []})

        def old_reserve(i):
            entry = {"user_id": i, "start_date": "2031-01-01", "end_date": "2031-01-05"}
            real_collections.find_one_and_update(
                {"property_id": property_id}, {"$push": {"booking_history": entry}}
            )

        _race(CALLERS, old_reserve)
        history = real_collections.find_one({"property_id": property_id})["booking_history"]
        if len(history) > 1:
            doubled += 1
    assert doubled == ROUNDS


def test_exactly_one_of_many_simultaneous_reservations_wins(real_collections, auth_headers):
    for round_number in range(ROUNDS):
        property_id = 41000 + round_number
        # alternate the two stored shapes of an empty history, so both go through the same path
        empty = [] if round_number % 2 else None
        real_collections.insert_one({"property_id": property_id, "booking_history": empty})

        codes = _race(
            CALLERS, lambda i: _reserve(property_id, "2031-01-01", "2031-01-05", auth_headers)
        )

        assert codes.count(200) == 1, f"round {round_number}: {sorted(codes)}"
        assert codes.count(409) == CALLERS - 1, f"round {round_number}: {sorted(codes)}"
        history = real_collections.find_one({"property_id": property_id})["booking_history"]
        assert len(history) == 1


def test_different_overlapping_ranges_still_allow_no_overlap(real_collections, auth_headers):
    property_id = 42000
    real_collections.insert_one({"property_id": property_id, "booking_history": []})
    ranges = [
        ("2031-02-01", "2031-02-05"),
        ("2031-02-04", "2031-02-09"),
        ("2031-02-03", "2031-02-04"),
        ("2031-01-30", "2031-02-02"),
    ]

    def reserve(i):
        start, end = ranges[i % len(ranges)]
        return _reserve(property_id, start, end, auth_headers)

    codes = _race(CALLERS, reserve)

    # whichever got in first, nothing in the history may overlap anything else in it
    history = real_collections.find_one({"property_id": property_id})["booking_history"]
    assert codes.count(200) == len(history) >= 1
    for i, a in enumerate(history):
        for b in history[i + 1 :]:
            assert not (a["start_date"] < b["end_date"] and a["end_date"] > b["start_date"]), (a, b)


def test_non_overlapping_reservations_all_succeed_together(real_collections, auth_headers):
    property_id = 43000
    real_collections.insert_one({"property_id": property_id, "booking_history": []})

    codes = _race(
        12,
        lambda i: _reserve(
            property_id, f"2032-{i + 1:02d}-01", f"2032-{i + 1:02d}-10", auth_headers
        ),
    )

    assert codes == [200] * 12
    assert len(real_collections.find_one({"property_id": property_id})["booking_history"]) == 12
