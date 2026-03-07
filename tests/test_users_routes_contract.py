from __future__ import annotations

from contract_assertions import (
    assert_error_contract,
    assert_success_contract,
    assert_user_contract,
)
from weave import error_messages


def test_user_profile_contract_returns_user_or_null(client, create_user, login_as):
    login_as(None)
    unauth = client.get("/api/user/profile")
    assert unauth.status_code == 200
    unauth_payload = unauth.get_json() or {}
    assert_success_contract(unauth_payload)
    assert (unauth_payload.get("data") or {}).get("user") is None

    member = create_user(role="MEMBER")
    login_as(member)
    auth = client.get("/api/user/profile")
    assert auth.status_code == 200
    auth_payload = auth.get_json() or {}
    assert_success_contract(auth_payload)
    data = auth_payload.get("data") or {}
    assert "user" in data
    assert_user_contract(data.get("user") or {})
    assert "volunteerSummary" in data


def test_me_activity_contract_requires_auth_and_keeps_keys(client, create_user, login_as):
    login_as(None)
    unauth = client.get("/api/me/activity")
    assert unauth.status_code == 401
    assert_error_contract(unauth.get_json() or {})

    member = create_user(role="MEMBER")
    login_as(member)
    auth = client.get("/api/me/activity")
    assert auth.status_code == 200
    payload = auth.get_json() or {}
    assert_success_contract(payload)
    data = payload.get("data") or {}
    assert "items" in data


def test_role_request_contract_requires_auth_and_valid_transition(
    client, create_user, login_as, csrf_headers
):
    login_as(None)
    unauth = client.post("/api/role/request", json={"to_role": "MEMBER"}, headers=csrf_headers())
    assert unauth.status_code == 401
    unauth_payload = unauth.get_json() or {}
    assert_error_contract(unauth_payload)
    assert unauth_payload.get("error") == error_messages.UNAUTHORIZED

    member = create_user(role="MEMBER")
    login_as(member)
    invalid = client.post(
        "/api/role/request",
        json={"to_role": "GENERAL"},
        headers=csrf_headers(),
    )
    assert invalid.status_code == 400
    invalid_payload = invalid.get_json() or {}
    assert_error_contract(invalid_payload)
    assert invalid_payload.get("error") == error_messages.ROLE_REQUEST_INVALID_TRANSITION


def test_me_history_contract_requires_auth_and_keeps_summary_keys(
    client, create_user, login_as
):
    login_as(None)
    unauth = client.get("/api/me/history")
    assert unauth.status_code == 401
    payload = unauth.get_json() or {}
    assert payload.get("ok") is False

    member = create_user(role="MEMBER")
    login_as(member)
    auth = client.get("/api/me/history")
    assert auth.status_code == 200
    body = auth.get_json() or {}
    assert body.get("ok") is True
    assert "summary" in body
    summary = body.get("summary") or {}
    for key in ("totalHours", "totalPoints", "certificateDownloadUrl"):
        assert key in summary


def test_me_certificate_csv_contract_requires_auth_and_returns_csv(
    client, create_user, login_as
):
    login_as(None)
    unauth = client.get("/api/me/certificate.csv")
    assert unauth.status_code == 401
    body = unauth.get_json() or {}
    assert body.get("ok") is False

    member = create_user(role="MEMBER")
    login_as(member)
    auth = client.get("/api/me/certificate.csv")
    assert auth.status_code == 200
    assert "text/csv" in str(auth.headers.get("Content-Type") or "")
    assert "attachment" in str(auth.headers.get("Content-Disposition") or "").lower()
