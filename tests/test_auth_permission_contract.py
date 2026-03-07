from __future__ import annotations

import pytest


@pytest.mark.parametrize(
    "role, expected_status",
    [
        (None, 401),
        ("GENERAL", 403),
        ("MEMBER", 403),
        ("EXECUTIVE", 201),
        ("LEADER", 201),
        ("ADMIN", 201),
    ],
)
def test_create_notice_permission_contract_by_role(
    role,
    expected_status,
    client,
    create_user,
    login_as,
    csrf_headers,
):
    if role is None:
        login_as(None)
    else:
        user = create_user(role=role)
        login_as(user)

    response = client.post(
        "/api/posts",
        json={"category": "notice", "title": "contract-notice", "content": "body"},
        headers=csrf_headers(),
    )

    assert response.status_code == expected_status
    payload = response.get_json() or {}

    if expected_status == 201:
        assert payload.get("success") is True
        assert int(((payload.get("data") or {}).get("post_id") or 0)) > 0
    else:
        assert payload.get("success") is False


@pytest.mark.parametrize(
    "role, expected_status",
    [
        (None, 401),
        ("GENERAL", 403),
        ("MEMBER", 403),
        ("EXECUTIVE", 403),
        ("LEADER", 201),
        ("ADMIN", 201),
    ],
)
def test_create_event_permission_contract_by_role(
    role,
    expected_status,
    client,
    create_user,
    login_as,
    csrf_headers,
):
    if role is None:
        login_as(None)
    else:
        user = create_user(role=role)
        login_as(user)

    payload = {
        "title": "contract-event",
        "start_datetime": "2099-01-10T10:00:00",
        "end_datetime": "2099-01-10T12:00:00",
        "capacity": 10,
    }
    response = client.post("/api/events", json=payload, headers=csrf_headers())

    assert response.status_code == expected_status
    body = response.get_json() or {}

    if expected_status == 201:
        assert body.get("success") is True
        assert int(((body.get("data") or {}).get("event_id") or 0)) > 0
    else:
        assert body.get("success") is False
