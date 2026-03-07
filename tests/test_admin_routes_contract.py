from __future__ import annotations

from contract_assertions import assert_error_contract, assert_success_contract


def test_admin_pending_users_returns_canonical_success_contract(
    client, create_user, login_as
):
    manager = create_user(role="VICE_LEADER")
    login_as(manager)

    response = client.get("/api/admin/pending-users")

    assert response.status_code == 200
    payload = response.get_json() or {}
    assert_success_contract(payload)
    data = payload.get("data") or {}
    assert "items" in data
    assert "pagination" in data


def test_admin_approve_user_returns_canonical_success_contract(
    client, create_user, login_as, csrf_headers
):
    manager = create_user(role="ADMIN")
    target = create_user(role="GENERAL", status="pending")
    login_as(manager)

    response = client.post(
        f"/api/admin/users/{target['id']}/approve",
        json={"role": "MEMBER"},
        headers=csrf_headers(),
    )

    assert response.status_code == 200
    payload = response.get_json() or {}
    assert_success_contract(payload)
    data = payload.get("data") or {}
    assert "message" in data
    assert "user" in data


def test_admin_pending_users_requires_auth_contract(client, login_as):
    login_as(None)
    response = client.get("/api/admin/pending-users")

    assert response.status_code == 401
    assert_error_contract(response.get_json() or {})
