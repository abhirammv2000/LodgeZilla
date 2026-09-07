import pytest

TEST_LISTING = {
    "property_id": 1234,
    "title": "Test Property",
    "host": 456,
    "location": "Test Location",
    "price": 100,
    "rating": 4.5,
    "summary": "Test Summary",
    "booking_history": [],
}


@pytest.fixture
def listing(client, auth_headers):
    """Add the test listing, then remove it once the test is done."""
    response = client.post("/api/listings/add", json=TEST_LISTING, headers=auth_headers)
    assert response.status_code == 200
    yield response.json()
    client.delete(
        f"/api/listings/delete/{TEST_LISTING['property_id']}", headers=auth_headers
    )


def test_get_listings(client, auth_headers, listing):
    response = client.get("/api/listings/list", headers=auth_headers)
    assert response.status_code == 200


def test_get_listings_by_host(client, auth_headers, listing):
    response = client.get(
        f"/api/listings/list/{TEST_LISTING['host']}", headers=auth_headers
    )
    assert response.status_code == 200


def test_update_listing(client, auth_headers, listing):
    response = client.put(
        f"/api/listings/update/{TEST_LISTING['property_id']}",
        json={**TEST_LISTING, "price": 150},
        headers=auth_headers,
    )
    assert response.status_code == 200
    assert response.json()["price"] == 150


def test_delete_listing(client, auth_headers, listing):
    property_id = TEST_LISTING["property_id"]
    response = client.delete(f"/api/listings/delete/{property_id}", headers=auth_headers)
    assert response.status_code == 200
    assert response.json()["status"] == "success"

    # Deleting again must report the listing as gone.
    response = client.delete(f"/api/listings/delete/{property_id}", headers=auth_headers)
    assert response.status_code == 404
