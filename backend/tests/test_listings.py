import pytest

from .conftest import TEST_USER_ID

TEST_LISTING = {
    "property_id": 1234,
    "title": "Test Property",
    "host": TEST_USER_ID,
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
    # The body is a plain JSON array - one client.json() call, not a JSON
    # string that itself needs a second parse (see _serialize's docstring).
    body = response.json()
    assert isinstance(body, list)
    assert any(item["property_id"] == TEST_LISTING["property_id"] for item in body)


def test_get_listings_by_host(client, auth_headers, listing):
    response = client.get(
        f"/api/listings/list/{TEST_LISTING['host']}", headers=auth_headers
    )
    assert response.status_code == 200
    body = response.json()
    assert isinstance(body, list)
    assert all(item["host"] == TEST_LISTING["host"] for item in body)


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


def test_cannot_update_someone_elses_listing(client, auth_headers, listing):
    """The authenticated user (TEST_USER_ID) does not own property_id 9999
    (host below is a different, unrelated id), so this must be refused."""
    other_property_id = 9999
    client.post(
        "/api/listings/add",
        json={**TEST_LISTING, "property_id": other_property_id, "host": TEST_USER_ID + 1},
        headers=auth_headers,
    )
    try:
        response = client.put(
            f"/api/listings/update/{other_property_id}",
            json={**TEST_LISTING, "price": 1},
            headers=auth_headers,
        )
        assert response.status_code == 403
    finally:
        # Cleanup has to go around the ownership check too, from a client
        # that actually owns it; there is no such client in this test, so
        # this is a direct collection delete, not an API call.
        from app.db import listing_collection

        listing_collection.delete_one({"property_id": other_property_id})


def test_cannot_delete_someone_elses_listing(client, auth_headers):
    other_property_id = 9998
    from app.db import listing_collection

    listing_collection.insert_one(
        {**TEST_LISTING, "property_id": other_property_id, "host": TEST_USER_ID + 1}
    )
    try:
        response = client.delete(
            f"/api/listings/delete/{other_property_id}", headers=auth_headers
        )
        assert response.status_code == 403
        assert listing_collection.find_one({"property_id": other_property_id}) is not None
    finally:
        listing_collection.delete_one({"property_id": other_property_id})
