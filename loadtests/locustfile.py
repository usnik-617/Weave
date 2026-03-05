import time
from itertools import count

from locust import HttpUser, between, task


_unique_counter = count(int(time.time() * 1000))


class WeaveUser(HttpUser):
    wait_time = between(0.1, 0.5)

    def on_start(self):
        self.login()

    def login(self):
        with self.client.post(
            "/api/auth/login",
            json={"username": "admin", "password": "Weave!2026"},
            name="POST /api/auth/login",
            catch_response=True,
        ) as response:
            if response.status_code != 200:
                response.failure(
                    f"login failed: {response.status_code} {response.text}"
                )

    @task(3)
    def healthz(self):
        with self.client.get(
            "/healthz", name="GET /healthz", catch_response=True
        ) as response:
            if response.status_code != 200:
                response.failure(f"healthz failed: {response.status_code}")

    @task(4)
    def auth_me(self):
        with self.client.get(
            "/api/auth/me", name="GET /api/auth/me", catch_response=True
        ) as response:
            if response.status_code != 200:
                response.failure(f"auth/me failed: {response.status_code}")

    @task(1)
    def signup_unique(self):
        uid = next(_unique_counter)
        with self.client.post(
            "/api/auth/signup",
            json={
                "name": f"load-{uid}",
                "email": f"load-{uid}@example.com",
                "birthDate": "2000.01.01",
                "phone": f"010-{uid % 10000:04d}-{(uid // 10000) % 10000:04d}",
                "username": f"load{uid}",
                "password": "Password!123",
            },
            name="POST /api/auth/signup",
            catch_response=True,
        ) as response:
            if response.status_code not in (200, 201):
                response.failure(
                    f"signup failed: {response.status_code} {response.text}"
                )
