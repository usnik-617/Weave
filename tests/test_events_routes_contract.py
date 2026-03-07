from __future__ import annotations

import pytest
from weave import error_messages

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
    assert payload.get("error") == error_messages.EVENT_VIEW_FORBIDDEN


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


def test_events_list_permission_contract_by_role(
    role_matrix_cases,
    client,
    create_user,
    login_as,
    sample_event,
):
    manager = create_user(role="LEADER")
    sample_event(author_id=manager["id"])

    for role, expected_status in role_matrix_cases:
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


def test_events_list_cache_invalidation_after_event_create(
    client, create_user, login_as, csrf_headers
):
    manager = create_user(role="VICE_LEADER")
    member = create_user(role="MEMBER")

    login_as(member)
    baseline = client.get("/api/events?page=1&pageSize=100")
    assert baseline.status_code == 200
    baseline_items = ((baseline.get_json() or {}).get("data") or {}).get("items") or []
    baseline_count = len(baseline_items)

    login_as(manager)
    created = client.post(
        "/api/events",
        json={
            "title": "cache-event",
            "start_datetime": "2099-01-01T10:00:00",
            "end_datetime": "2099-01-01T11:00:00",
            "capacity": 10,
        },
        headers=csrf_headers(),
    )
    assert created.status_code == 201

    login_as(member)
    refreshed = client.get("/api/events?page=1&pageSize=100")
    assert refreshed.status_code == 200
    refreshed_items = ((refreshed.get_json() or {}).get("data") or {}).get("items") or []
    assert len(refreshed_items) >= baseline_count + 1


def test_events_list_cache_invalidation_after_event_update(
    client, create_user, login_as, csrf_headers
):
    manager = create_user(role="VICE_LEADER")
    member = create_user(role="MEMBER")

    login_as(manager)
    created = client.post(
        "/api/events",
        json={
            "title": "cache-event-before",
            "start_datetime": "2099-02-01T10:00:00",
            "end_datetime": "2099-02-01T11:00:00",
            "capacity": 15,
        },
        headers=csrf_headers(),
    )
    assert created.status_code == 201
    event_id = int(((created.get_json() or {}).get("data") or {}).get("event_id") or 0)
    assert event_id > 0

    login_as(member)
    warm = client.get("/api/events?page=1&pageSize=100")
    assert warm.status_code == 200

    login_as(manager)
    updated = client.put(
        f"/api/events/{event_id}",
        json={
            "title": "cache-event-after",
            "start_datetime": "2099-02-01T10:00:00",
            "end_datetime": "2099-02-01T11:30:00",
        },
        headers=csrf_headers(),
    )
    assert updated.status_code == 200

    login_as(member)
    refreshed = client.get("/api/events?page=1&pageSize=100")
    assert refreshed.status_code == 200
    items = ((refreshed.get_json() or {}).get("data") or {}).get("items") or []
    target = next((item for item in items if int(item.get("id") or 0) == event_id), None)
    assert target is not None
    assert target.get("title") == "cache-event-after"
