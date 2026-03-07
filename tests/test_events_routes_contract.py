from __future__ import annotations

import pytest

from contract_assertions import assert_item_has_keys, assert_paginated_items_contract


def test_general_user_cannot_list_events(
    client,
    create_user,
    login_as,
):
    general = create_user(role="GENERAL")
    login_as(general)

    response = client.get("/api/events")

    assert response.status_code == 403
    payload = response.get_json() or {}
    assert payload.get("success") is False


def test_member_event_list_exposes_capacity_and_participant_status(
    client,
    create_user,
    login_as,
    csrf_headers,
    sample_event,
):
    manager = create_user(role="VICE_LEADER")
    member = create_user(role="MEMBER")
    event_id = sample_event(author_id=manager["id"])

    login_as(member)
    join_response = client.post(f"/api/events/{event_id}/join", headers=csrf_headers())
    assert join_response.status_code == 200

    list_response = client.get("/api/events?page=1&pageSize=10")
    assert list_response.status_code == 200

    payload = list_response.get_json() or {}
    data = payload.get("data") or {}
    items = data.get("items") or []
    target = next((item for item in items if item.get("id") == event_id), None)

    assert target is not None
    assert_item_has_keys(target, ("id", "title", "capacity", "participantCount", "myStatus"))
    assert int(target.get("capacity") or 0) >= 0
    assert int(target.get("participantCount") or 0) >= 1
    assert target.get("myStatus") == "registered"


@pytest.mark.parametrize(
    "role, expected_status",
    [
        (None, 401),
        ("GENERAL", 403),
        ("MEMBER", 200),
        ("EXECUTIVE", 200),
        ("LEADER", 200),
        ("ADMIN", 200),
    ],
)
def test_events_list_permission_contract_by_role(
    role,
    expected_status,
    client,
    create_user,
    login_as,
    sample_event,
):
    manager = create_user(role="LEADER")
    sample_event(author_id=manager["id"])

    if role is None:
        login_as(None)
    else:
        user = create_user(role=role)
        login_as(user)

    response = client.get("/api/events?page=1&pageSize=5")

    assert response.status_code == expected_status
    payload = response.get_json() or {}

    if expected_status == 200:
        assert payload.get("success") is True
        data = payload.get("data") or {}
        assert_paginated_items_contract(data)
        items = data.get("items") or []
        if items:
            assert_item_has_keys(
                items[0],
                ("id", "title", "capacity", "participantCount", "myStatus"),
            )
    else:
        assert payload.get("success") is False
