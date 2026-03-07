from __future__ import annotations

from datetime import datetime, timedelta
import uuid


def _set_user_nickname_state(user_id, nickname=None, nickname_updated_at=None):
    from weave.core import get_db_connection

    conn = get_db_connection()
    if nickname is not None and nickname_updated_at is not None:
        conn.execute(
            "UPDATE users SET nickname = ?, nickname_updated_at = ? WHERE id = ?",
            (nickname, nickname_updated_at, user_id),
        )
    elif nickname is not None:
        conn.execute("UPDATE users SET nickname = ? WHERE id = ?", (nickname, user_id))
    elif nickname_updated_at is not None:
        conn.execute(
            "UPDATE users SET nickname_updated_at = ? WHERE id = ?",
            (nickname_updated_at, user_id),
        )
    conn.commit()
    conn.close()


def _iso_days_ago(days):
    return (datetime.now() - timedelta(days=days)).replace(microsecond=0).isoformat()


def _signup_payload(nickname, suffix=None):
    token = suffix or uuid.uuid4().hex[:8]
    return {
        "name": f"Tester{token}",
        "nickname": nickname,
        "email": f"u{token}@example.com",
        "birthDate": "2000.01.01",
        "phone": f"010-12{token[:2]}-{token[2:6]}",
        "username": f"user_{token}",
        "password": "Password!123",
    }


def test_valid_nickname_change_is_allowed(client, create_user, login_as, csrf_headers):
    user = create_user(role="MEMBER")
    # Allow change by moving last nickname change outside 180-day window.
    _set_user_nickname_state(user["id"], nickname_updated_at=_iso_days_ago(181))
    login_as(user)

    response = client.patch(
        "/api/me/nickname",
        json={"nickname": "새닉123"},
        headers=csrf_headers(),
    )

    assert response.status_code == 200
    payload = response.get_json() or {}
    assert payload.get("success") is True
    data = payload.get("data") or {}
    assert isinstance(data.get("message"), str)
    user_data = data.get("user") or {}
    assert user_data.get("nickname") == "새닉123"


def test_invalid_nickname_format_is_rejected(
    client, create_user, login_as, csrf_headers
):
    user = create_user(role="MEMBER")
    login_as(user)

    response = client.patch(
        "/api/me/nickname",
        json={"nickname": "bad nick!"},
        headers=csrf_headers(),
    )

    assert response.status_code == 400
    payload = response.get_json() or {}
    assert payload.get("success") is False
    assert isinstance(payload.get("error"), str)


def test_duplicate_nickname_is_rejected(client, create_user, login_as, csrf_headers):
    owner = create_user(role="MEMBER")
    target = create_user(role="MEMBER")

    _set_user_nickname_state(target["id"], nickname="중복닉77")
    _set_user_nickname_state(owner["id"], nickname_updated_at=_iso_days_ago(181))

    login_as(owner)
    response = client.patch(
        "/api/me/nickname",
        json={"nickname": "중복닉77"},
        headers=csrf_headers(),
    )

    assert response.status_code == 409
    payload = response.get_json() or {}
    assert payload.get("success") is False
    assert "닉네임" in str(payload.get("error") or "")


def test_nickname_change_within_180_days_is_rejected(
    client, create_user, login_as, csrf_headers
):
    user = create_user(role="MEMBER")
    # Fixture user defaults nickname_updated_at to now, so this should be blocked.
    login_as(user)

    response = client.patch(
        "/api/me/nickname",
        json={"nickname": "재변경55"},
        headers=csrf_headers(),
    )

    assert response.status_code == 403
    payload = response.get_json() or {}
    assert payload.get("success") is False
    details = payload.get("details") or {}
    assert isinstance(details.get("next_allowed_at"), str)


def test_nickname_change_after_180_days_is_allowed(
    client, create_user, login_as, csrf_headers
):
    user = create_user(role="MEMBER")
    _set_user_nickname_state(user["id"], nickname_updated_at=_iso_days_ago(181))
    login_as(user)

    response = client.patch(
        "/api/me/nickname",
        json={"nickname": "허용변경9"},
        headers=csrf_headers(),
    )

    assert response.status_code == 200
    payload = response.get_json() or {}
    assert payload.get("success") is True
    data = payload.get("data") or {}
    user_data = data.get("user") or {}
    assert user_data.get("nickname") == "허용변경9"


def test_legacy_nickname_endpoint_keeps_180_day_policy_contract(
    client, create_user, login_as, csrf_headers
):
    user = create_user(role="MEMBER")
    _set_user_nickname_state(user["id"], nickname_updated_at=_iso_days_ago(181))
    login_as(user)

    first = client.post(
        "/api/user/nickname",
        json={"nickname": "레거시11"},
        headers=csrf_headers(),
    )
    assert first.status_code == 200
    first_payload = first.get_json() or {}
    assert first_payload.get("success") is True
    first_data = first_payload.get("data") or {}
    first_user = first_data.get("user") or {}
    assert first_user.get("nickname") == "레거시11"

    second = client.post(
        "/api/user/nickname",
        json={"nickname": "레거시22"},
        headers=csrf_headers(),
    )
    assert second.status_code == 403
    second_payload = second.get_json() or {}
    assert second_payload.get("success") is False
    second_details = second_payload.get("details") or {}
    assert isinstance(second_details.get("next_allowed_at"), str)


def test_signup_rejects_invalid_nickname_format(client, csrf_headers):
    payload = _signup_payload("bad nick!")

    response = client.post(
        "/api/auth/signup",
        json=payload,
        headers=csrf_headers(),
    )

    assert response.status_code == 400
    body = response.get_json() or {}
    assert body.get("success") is False
    assert isinstance(body.get("error"), str)


def test_signup_rejects_duplicate_nickname(client, csrf_headers, monkeypatch):
    from weave import core

    monkeypatch.setattr(core, "WEAVE_ENV", "development")

    nickname = "가입중복88"
    first_suffix = uuid.uuid4().hex[:8]
    second_suffix = uuid.uuid4().hex[:8]

    first = client.post(
        "/api/auth/signup",
        json=_signup_payload(nickname, suffix=first_suffix),
        headers=csrf_headers(),
    )
    assert first.status_code == 200

    second = client.post(
        "/api/auth/signup",
        json=_signup_payload(nickname, suffix=second_suffix),
        headers=csrf_headers(),
    )

    assert second.status_code in {409, 429}
    body = second.get_json() or {}
    assert body.get("success") is False
    if second.status_code == 409:
        assert "닉네임" in str(body.get("error") or "")


def test_modern_and_legacy_nickname_endpoints_keep_error_schema_consistent(
    client, create_user, login_as, csrf_headers
):
    user = create_user(role="MEMBER")
    login_as(user)

    modern = client.patch(
        "/api/me/nickname",
        json={"nickname": "재검증11"},
        headers=csrf_headers(),
    )
    legacy = client.post(
        "/api/user/nickname",
        json={"nickname": "재검증22"},
        headers=csrf_headers(),
    )

    assert modern.status_code == 403
    assert legacy.status_code == 403

    modern_body = modern.get_json() or {}
    legacy_body = legacy.get_json() or {}

    for body in (modern_body, legacy_body):
        assert body.get("success") is False
        assert isinstance(body.get("error"), str)
        details = body.get("details") or {}
        assert isinstance(details.get("next_allowed_at"), str)
