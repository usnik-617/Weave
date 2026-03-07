from __future__ import annotations

from datetime import datetime, timedelta

import pytest
from weave import error_messages

from contract_assertions import assert_item_has_keys, assert_paginated_items_contract


def _future_iso(hours=72):
    return (datetime.now() + timedelta(hours=hours)).replace(microsecond=0).isoformat()


def test_posts_list_contract_keeps_endpoint_and_core_response_keys(
    client,
    create_user,
    create_post_record,
    login_as,
):
    author = create_user(role="EXECUTIVE")
    create_post_record(
        category="notice",
        author_id=author["id"],
        title="contract-notice-post",
    )
    general = create_user(role="GENERAL")
    login_as(general)

    response = client.get("/api/posts?type=notice&page=1&pageSize=20")

    assert response.status_code == 200
    payload = response.get_json() or {}
    assert payload.get("success") is True

    data = payload.get("data") or {}
    assert_paginated_items_contract(data)

    items = data.get("items") or []

    if items:
        sample = items[0]
        assert_item_has_keys(
            sample,
            (
                "id",
                "category",
                "type",
                "title",
                "status",
                "author",
                "created_at",
                "updated_at",
            ),
        )


@pytest.mark.parametrize(
    "role, should_see_scheduled",
    [
        ("GENERAL", False),
        ("MEMBER", False),
        ("EXECUTIVE", False),
        ("LEADER", True),
        ("ADMIN", True),
    ],
)
def test_scheduled_notice_visibility_contract_by_role(
    role,
    should_see_scheduled,
    client,
    create_user,
    create_post_record,
    login_as,
):
    author = create_user(role="EXECUTIVE")
    post_id = create_post_record(
        category="notice",
        author_id=author["id"],
        publish_at=_future_iso(),
        title="contract-scheduled-notice",
    )

    viewer = create_user(role=role)
    login_as(viewer)

    detail_response = client.get(f"/api/posts/{post_id}")
    expected_detail_status = 200 if should_see_scheduled else 404
    assert detail_response.status_code == expected_detail_status

    list_response = client.get(
        "/api/posts?type=notice&pageSize=200&include_scheduled=true"
    )
    assert list_response.status_code == 200

    payload = list_response.get_json() or {}
    data = payload.get("data") or {}
    items = data.get("items") or []
    listed_ids = {int(item.get("id") or 0) for item in items}

    if should_see_scheduled:
        assert post_id in listed_ids
    else:
        assert post_id not in listed_ids


def test_post_templates_contract_and_unsupported_type_error(client, csrf_headers):
    template_list = client.get("/api/templates")
    assert template_list.status_code == 200
    list_payload = template_list.get_json() or {}
    assert list_payload.get("ok") is True
    items = list_payload.get("items") or []
    assert isinstance(items, list)
    assert {item.get("type") for item in items} >= {"notice", "review", "minutes"}

    generated = client.post(
        "/api/templates/generate",
        json={"type": "notice", "title": "계약테스트"},
        headers=csrf_headers(),
    )
    assert generated.status_code == 200
    generated_payload = generated.get_json() or {}
    assert generated_payload.get("ok") is True
    content = str(generated_payload.get("content") or "")
    assert "계약테스트" in content

    invalid = client.post(
        "/api/templates/generate",
        json={"type": "unknown-template"},
        headers=csrf_headers(),
    )
    assert invalid.status_code == 400
    invalid_payload = invalid.get_json() or {}
    assert invalid_payload.get("ok") is False
    assert invalid_payload.get("message") == error_messages.POST_TEMPLATE_UNSUPPORTED


def test_posts_list_cache_invalidation_after_create(
    client, create_user, login_as, csrf_headers
):
    exec_user = create_user(role="EXECUTIVE")
    login_as(exec_user)

    first = client.post(
        "/api/posts",
        json={
            "category": "notice",
            "title": "cache-first",
            "content": "first",
        },
        headers=csrf_headers(),
    )
    assert first.status_code == 201

    warm = client.get("/api/posts?type=notice&page=1&pageSize=100")
    assert warm.status_code == 200

    second = client.post(
        "/api/posts",
        json={
            "category": "notice",
            "title": "cache-second",
            "content": "second",
        },
        headers=csrf_headers(),
    )
    assert second.status_code == 201

    refreshed = client.get("/api/posts?type=notice&page=1&pageSize=100")
    assert refreshed.status_code == 200
    items = ((refreshed.get_json() or {}).get("data") or {}).get("items") or []
    titles = {str(item.get("title") or "") for item in items}
    assert "cache-first" in titles
    assert "cache-second" in titles


def test_posts_list_cache_invalidation_after_update_and_delete(
    client, create_user, login_as, csrf_headers
):
    exec_user = create_user(role="EXECUTIVE")
    login_as(exec_user)

    created = client.post(
        "/api/posts",
        json={"category": "notice", "title": "cache-update-before", "content": "x"},
        headers=csrf_headers(),
    )
    assert created.status_code == 201
    post_id = int(((created.get_json() or {}).get("data") or {}).get("post_id") or 0)
    assert post_id > 0

    warm = client.get("/api/posts?type=notice&page=1&pageSize=100")
    assert warm.status_code == 200

    updated = client.put(
        f"/api/posts/{post_id}",
        json={"title": "cache-update-after", "content": "y", "category": "notice"},
        headers=csrf_headers(),
    )
    assert updated.status_code == 200

    refreshed = client.get("/api/posts?type=notice&page=1&pageSize=100")
    assert refreshed.status_code == 200
    refreshed_items = ((refreshed.get_json() or {}).get("data") or {}).get("items") or []
    refreshed_titles = {str(item.get("title") or "") for item in refreshed_items}
    assert "cache-update-after" in refreshed_titles

    deleted = client.delete(f"/api/posts/{post_id}", headers=csrf_headers())
    assert deleted.status_code == 200

    after_delete = client.get("/api/posts?type=notice&page=1&pageSize=100")
    assert after_delete.status_code == 200
    items = ((after_delete.get_json() or {}).get("data") or {}).get("items") or []
    ids = {int(item.get("id") or 0) for item in items}
    assert post_id not in ids
