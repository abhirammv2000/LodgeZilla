import os
import random

from locust import HttpUser, between, task

TEST_USER_NAME = os.getenv("TEST_USER_NAME", "AnirudhMaiya")
TEST_USER_PASSWORD = os.getenv("TEST_USER_PASSWORD", "123456")
LOGIN_URL = "/api/auth/token"
LOGIN_BODY = {"name": TEST_USER_NAME, "password": TEST_USER_PASSWORD}


class MyUser(HttpUser):
    wait_time = between(1, 3)  # Random wait time between 1 and 3 seconds

    def on_start(self):
        # A distinct id per virtual user, not a shared literal: two users
        # both inserting property_id 1234 concurrently previously collided
        # on the unique index, which measured lock contention on a bad test
        # rather than realistic traffic.
        self.property_id = random.randint(10_000_000, 99_999_999)

    @task
    def create_property(self):
        # Simulate login
        response = self.client.post(LOGIN_URL, json=LOGIN_BODY)
        access_token = response.json().get("access_token", "")
        # Simulate creating a property
        headers = {"Authorization": "Bearer "+access_token}
        property_data = {
            "title": "NewProperty",
            "location": "TestLocation",
            "price": 100,
            "rating": 4.5,
            "summary": "TestSummary",
            "property_id": self.property_id,
            "booking_history": []
        }
        self.client.post("/api/listings/add", headers=headers, json=property_data)

    @task
    def login_and_reserve(self):
        # Simulate login
        response = self.client.post(LOGIN_URL, json=LOGIN_BODY)
        access_token = response.json().get("access_token", "")

        # Simulate reserving a property
        response = self.client.post(
        f"/api/bookings/reserve/{self.property_id}",
        json={"start_date": "2023-01-05", "end_date": "2023-01-10"},
        headers={"Authorization": "Bearer " + access_token}  # Replace with a valid access token
    )

    @task
    def create_user(self):
        # Simulate creating a user
        user_data = {
            "name": "new_user",
            "password": "new_password",
            "userType": "host",
            "user_id": 456
        }
        self.client.post("/api/auth/create", json=user_data)

    @task
    def search_properties(self):
        # Simulate login
        response = self.client.post(LOGIN_URL, json=LOGIN_BODY)
        access_token = response.json().get("access_token", "")
        # Simulate searching for properties
        self.client.get("/api/bookings/search?destination=TestLocation&from_date=2023-12-01&to_date=2023-12-07", headers = {"Authorization": f"Bearer {access_token}"})

    @task
    def list_properties_for_user(self):
        # Simulate login
        response = self.client.post(LOGIN_URL, json=LOGIN_BODY)
        access_token = response.json().get("access_token", "")
        # Simulate listing properties for a particular user
        user_id = 123  # Replace with a valid user_id
        self.client.get(f"/api/listings/list/{user_id}", headers = {"Authorization": f"Bearer {access_token}"})
