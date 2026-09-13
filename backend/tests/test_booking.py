import base64
import json

import pytest

from .conftest import TEST_USER_ID

TEST_LISTING = {
    "property_id": 123,
    "title": "TestProperty",
    "host": TEST_USER_ID,
    "location": "TestLocation",
    "price": 100,
    "rating": 4.5,
    "summary": "TestSummary",
    "booking_history": [],
}


@pytest.fixture
def listing(client, auth_headers):
    response = client.post("/api/listings/add", json=TEST_LISTING, headers=auth_headers)
    assert response.status_code == 200
    yield response.json()
    client.delete(
        f"/api/listings/delete/{TEST_LISTING['property_id']}", headers=auth_headers
    )


def test_search_properties(client, auth_headers, listing):
    response = client.get(
        "/api/bookings/search"
        "?destination=TestLocation&from_date=2023-01-01&to_date=2023-01-10",
        headers=auth_headers,
    )
    assert response.status_code == 200
    assert len(response.json()) > 0


def test_reserve_property(client, auth_headers, access_token, listing):
    # The reservation is recorded against whoever the token belongs to.
    payload = access_token.split(".")[1]
    payload += "=" * (-len(payload) % 4)
    user_id = int(json.loads(base64.urlsafe_b64decode(payload))["sub"])

    response = client.post(
        f"/api/bookings/reserve/{TEST_LISTING['property_id']}",
        json={"start_date": "2023-01-05", "end_date": "2023-01-10"},
        headers=auth_headers,
    )
    assert response.status_code == 200
    data = response.json()
    assert data["message"] == "Reservation successful"

    booking_entry = {
        "user_id": user_id,
        "start_date": "2023-01-05",
        "end_date": "2023-01-10",
    }
    assert booking_entry in data["updated_property"]["booking_history"]
    assert str(TEST_LISTING["property_id"]) in data["updated_user"]["trips"]


def test_reserve_missing_property_returns_404(client, auth_headers):
    response = client.post(
        "/api/bookings/reserve/99999999",
        json={"start_date": "2023-01-05", "end_date": "2023-01-10"},
        headers=auth_headers,
    )
    assert response.status_code == 404


# --- The one piece of real business logic in the app: does the overlap
# query in search_properties actually separate a free listing from a
# booked one, on every boundary that matters. Previously the only test
# touching this endpoint used an empty booking_history and never checked
# that an overlapping booking is excluded, which is the entire point of the
# query. ---


def _listing_with_booking(property_id, start_date, end_date):
    return {
        "property_id": property_id,
        "title": "OverlapTest",
        "host": TEST_USER_ID,
        "location": "OverlapCity",
        "price": 100,
        "rating": 4.0,
        "summary": "s",
        "booking_history": [
            {"user_id": TEST_USER_ID, "start_date": start_date, "end_date": end_date}
        ],
    }


def _search(client, auth_headers, from_date="2024-06-05", to_date="2024-06-10"):
    response = client.get(
        "/api/bookings/search"
        f"?destination=OverlapCity&from_date={from_date}&to_date={to_date}",
        headers=auth_headers,
    )
    assert response.status_code == 200
    return {p["property_id"] for p in response.json()}


@pytest.fixture
def overlap_listings(client, auth_headers):
    from app.db import listing_collection

    ids = {
        "overlapping": 20001,
        "adjacent_before": 20002,
        "adjacent_after": 20003,
        "empty_history": 20004,
        "null_history_field": 20005,
        "no_history_key_at_all": 20006,
    }
    listing_collection.insert_one(
        _listing_with_booking(ids["overlapping"], "2024-06-07", "2024-06-08")
    )
    # Touches the search window's edges without overlapping it: a booking
    # that ends exactly when the search starts, or starts exactly when the
    # search ends, must not count as a conflict.
    listing_collection.insert_one(
        _listing_with_booking(ids["adjacent_before"], "2024-06-01", "2024-06-05")
    )
    listing_collection.insert_one(
        _listing_with_booking(ids["adjacent_after"], "2024-06-10", "2024-06-15")
    )
    empty = _listing_with_booking(ids["empty_history"], "x", "x")
    empty["booking_history"] = []
    listing_collection.insert_one(empty)
    # What create_item (POST /listings/add) actually produces when a caller
    # omits booking_history: Property defaults it to None, so the key is
    # present with a null value, not absent. This is the realistic case.
    null_field = _listing_with_booking(ids["null_history_field"], "x", "x")
    null_field["booking_history"] = None
    listing_collection.insert_one(null_field)
    # A truly absent key is a different state a Property-model-backed insert
    # never produces, but old, pre-schema data plausibly could. $exists:
    # False sits inside $nor here, so this ends up requiring the field to be
    # PRESENT to match, excluding a document that lacks the key entirely,
    # the opposite of what that condition reads like it is trying to do.
    # Documented as-is rather than "fixed" on a guess about intent: it is a
    # real, narrow edge case with no realistic path through the app today.
    no_key = _listing_with_booking(ids["no_history_key_at_all"], "x", "x")
    del no_key["booking_history"]
    listing_collection.insert_one(no_key)

    yield ids

    for property_id in ids.values():
        listing_collection.delete_one({"property_id": property_id})


def test_overlapping_booking_is_excluded(client, auth_headers, overlap_listings):
    found = _search(client, auth_headers)
    assert overlap_listings["overlapping"] not in found


def test_adjacent_non_overlapping_bookings_are_included(client, auth_headers, overlap_listings):
    found = _search(client, auth_headers)
    assert overlap_listings["adjacent_before"] in found
    assert overlap_listings["adjacent_after"] in found


def test_empty_booking_history_is_included(client, auth_headers, overlap_listings):
    found = _search(client, auth_headers)
    assert overlap_listings["empty_history"] in found


def test_null_booking_history_is_included(client, auth_headers, overlap_listings):
    """The realistic case: a listing added without booking_history has the
    key present with value None (Property's default), not the key missing."""
    found = _search(client, auth_headers)
    assert overlap_listings["null_history_field"] in found


def test_a_key_missing_entirely_is_excluded(client, auth_headers, overlap_listings):
    """Documents the query's actual behavior for a state the app itself
    cannot produce (see the comment on no_history_key_at_all above)."""
    found = _search(client, auth_headers)
    assert overlap_listings["no_history_key_at_all"] not in found
