from __future__ import annotations

from weave import core
from contract_assertions import assert_error_contract


def test_login_rate_limit_contract_returns_429_when_bucket_blocked(client, csrf_headers):
    original_env = core.WEAVE_ENV
    try:
        core.WEAVE_ENV = "production"
        username = "rate_limited_user"
        key = f"login:127.0.0.1:{username}"
        core.clear_all_rate_limit_state()
        for _ in range(int(core.LOGIN_RATE_LIMIT_COUNT)):
            core.register_login_failure(key)

        response = client.post(
            "/api/auth/login",
            json={"username": username, "password": "Wrong!123"},
            headers=csrf_headers(),
            environ_overrides={"REMOTE_ADDR": "127.0.0.1"},
        )

        assert response.status_code == 429
        payload = response.get_json() or {}
        assert_error_contract(payload)
        details = payload.get("details") or {}
        assert set(details.keys()) == {"blocked_until"}
        assert isinstance(details.get("blocked_until"), str)
    finally:
        core.WEAVE_ENV = original_env
        core.clear_all_rate_limit_state()
