"""Reserving dates that are already taken, and the inputs that used to slip through.

Before this, POST /bookings/reserve pushed a booking without looking at the existing ones, so
the same dates could be sold twice, and a listing created through the API (booking_history
null) could not be reserved at all on a real MongoDB. Search has always excluded booked
listings, so the two endpoints disagreed.

These tests run on mongomock, which is enough for the rules. Whether two simultaneous requests
can both win is a question about MongoDB itself, and test_booking_concurrency.py asks it of a
real server.
"""
import pytest

from app.db import listing_collection, user_collection
from app.routes.auth import create_jwt_token

PROPERTY_ID = 31001


def _listing(booking_history):
    return {
        "property_id": PROPERTY_ID,
        "title": "Conflict test",
        "host": 1,
        "location": "ConflictTown",
        "price": 90,
        "rating": 4.0,
        "summary": "x",
        "booking_history": booking_history,
    }


@pytest.fixture
def free_listing():
    listing_collection.delete_many({"property_id": PROPERTY_ID})
    listing_collection.insert_one(_listing([]))
    yield PROPERTY_ID
    listing_collection.delete_many({"property_id": PROPERTY_ID})


def _reserve(client, headers, start, end, property_id=PROPERTY_ID):
    return client.post(
        f"/api/bookings/reserve/{property_id}",
        json={"start_date": start, "end_date": end},
        headers=headers,
    )


def _history():
    return listing_collection.find_one({"property_id": PROPERTY_ID})["booking_history"]


def test_the_same_dates_cannot_be_reserved_twice(client, auth_headers, free_listing):
    assert _reserve(client, auth_headers, "2030-06-01", "2030-06-05").status_code == 200

    second = _reserve(client, auth_headers, "2030-06-01", "2030-06-05")

    assert second.status_code == 409
    assert "already booked" in second.json()["detail"]
    assert len(_history()) == 1


@pytest.mark.parametrize(
    "start,end,label",
    [
        ("2030-06-03", "2030-06-08", "overlaps the end"),
        ("2030-05-28", "2030-06-02", "overlaps the start"),
        ("2030-06-02", "2030-06-04", "sits inside"),
        ("2030-05-20", "2030-06-20", "contains it"),
    ],
)
def test_every_kind_of_overlap_is_refused(client, auth_headers, free_listing, start, end, label):
    assert _reserve(client, auth_headers, "2030-06-01", "2030-06-05").status_code == 200

    response = _reserve(client, auth_headers, start, end)

    assert response.status_code == 409, label
    assert len(_history()) == 1


def test_back_to_back_stays_are_allowed(client, auth_headers, free_listing):
    """Checking out the day the next guest checks in is not a conflict (search agrees)."""
    assert _reserve(client, auth_headers, "2030-06-05", "2030-06-08").status_code == 200
    assert _reserve(client, auth_headers, "2030-06-01", "2030-06-05").status_code == 200
    assert _reserve(client, auth_headers, "2030-06-08", "2030-06-10").status_code == 200
    assert len(_history()) == 3


def test_a_refused_reservation_changes_nothing(client, auth_headers, free_listing):
    assert _reserve(client, auth_headers, "2030-06-01", "2030-06-05").status_code == 200
    before = listing_collection.find_one({"property_id": PROPERTY_ID})

    assert _reserve(client, auth_headers, "2030-06-02", "2030-06-03").status_code == 409

    assert listing_collection.find_one({"property_id": PROPERTY_ID}) == before


def test_search_and_reserve_agree(client, auth_headers, free_listing):
    url = "/api/bookings/search?destination=ConflictTown&from_date=2030-06-02&to_date=2030-06-04"
    assert [p["property_id"] for p in client.get(url, headers=auth_headers).json()] == [PROPERTY_ID]

    assert _reserve(client, auth_headers, "2030-06-01", "2030-06-05").status_code == 200

    assert client.get(url, headers=auth_headers).json() == []


# A listing added through POST /listings/add has booking_history null (Property's default), and
# $push onto null fails on a real MongoDB. A listing with no such field at all is the other
# shape old data can have.
@pytest.mark.parametrize("stored", [None, "missing"])
def test_listings_without_a_history_list_can_be_reserved(client, auth_headers, stored):
    listing_collection.delete_many({"property_id": PROPERTY_ID})
    document = _listing(None)
    if stored == "missing":
        del document["booking_history"]
    listing_collection.insert_one(document)
    try:
        assert _reserve(client, auth_headers, "2030-07-01", "2030-07-03").status_code == 200
        assert len(_history()) == 1
        assert _reserve(client, auth_headers, "2030-07-02", "2030-07-04").status_code == 409
    finally:
        listing_collection.delete_many({"property_id": PROPERTY_ID})


def test_an_unknown_property_is_404_not_409(client, auth_headers):
    response = _reserve(client, auth_headers, "2030-06-01", "2030-06-05", property_id=99999998)
    assert response.status_code == 404


def test_an_unknown_user_cannot_leave_a_booking_behind(client, free_listing):
    ghost = create_jwt_token({"sub": "424242", "userType": "tourist"})
    assert user_collection.find_one({"user_id": 424242}) is None

    response = _reserve(client, {"Authorization": f"Bearer {ghost}"}, "2030-06-01", "2030-06-05")

    assert response.status_code == 404
    assert response.json()["detail"] == "User not found"
    assert _history() == []


@pytest.mark.parametrize(
    "start,end",
    [
        ("next week", "2030-06-05"),
        ("2030-06-01", "soon"),
        ("2030-6-1", "2030-06-05"),  # not zero padded, so string comparison would be wrong
        ("20300601", "20300605"),
        ("2030-02-30", "2030-03-02"),  # no such day
        ("2030-06-05", "2030-06-01"),  # ends before it starts
        ("", ""),
    ],
)
def test_bad_dates_are_422_and_change_nothing(client, auth_headers, free_listing, start, end):
    response = _reserve(client, auth_headers, start, end)

    assert response.status_code == 422, response.text
    assert _history() == []


def test_a_one_day_range_is_accepted(client, auth_headers, free_listing):
    """The tourist page starts with today as both dates, so equal dates must not be an error."""
    assert _reserve(client, auth_headers, "2030-06-01", "2030-06-01").status_code == 200
