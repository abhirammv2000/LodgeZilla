import base64
import json

import pytest

TEST_LISTING = {
    "property_id": 123,
    "title": "TestProperty",
    "host": 1702359326,
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
