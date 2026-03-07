from __future__ import annotations

import uuid

import pytest

from weave import core
from weave import error_messages

from contract_assertions import assert_error_contract


@pytest.fixture(autouse=True)
def _disable_rate_limit_for_auth_contracts(monkeypatch):
    monkeypatch.setattr(core, "WEAVE_ENV", "development")


def test_login_contract_missing_credentials_returns_400(client, csrf_headers):
    response = client.post("/api/auth/login", json={}, headers=csrf_headers())

    assert response.status_code == 400
    payload = response.get_json() or {}
    assert_error_contract(payload)
    assert payload.get("error") == "아이디와 비밀번호를 입력해주세요."
    assert "details" not in payload


def test_login_contract_unknown_user_returns_401(client, csrf_headers):
    response = client.post(
        "/api/auth/login",
        json={"username": "not_exists_user", "password": "Wrong!123"},
        headers=csrf_headers(),
    )

    assert response.status_code == 401
    payload = response.get_json() or {}
    assert_error_contract(payload)
    assert payload.get("error") == error_messages.AUTH_INVALID_CREDENTIALS


def test_login_contract_suspended_user_returns_403(client, create_user, csrf_headers):
    user = create_user(role="MEMBER", status="suspended")

    response = client.post(
        "/api/auth/login",
        json={"username": user["username"], "password": "anything"},
        headers=csrf_headers(),
    )

    assert response.status_code == 403
    payload = response.get_json() or {}
    assert_error_contract(payload)
    assert payload.get("error") == error_messages.AUTH_SUSPENDED


def test_signup_contract_invalid_nickname_returns_400(client, csrf_headers):
    token = uuid.uuid4().hex[:8]
    response = client.post(
        "/api/auth/signup",
        json={
            "name": "Auth Tester",
            "nickname": "bad nick!",
            "email": f"auth_contract_{token}@example.com",
            "birthDate": "2000.01.01",
            "phone": "010-1111-1111",
            "username": f"auth_contract_{token}",
            "password": "Password!123",
        },
        headers=csrf_headers(),
    )

    assert response.status_code == 400
    payload = response.get_json() or {}
    assert_error_contract(payload)
