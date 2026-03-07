from __future__ import annotations

from datetime import datetime, timedelta

import pytest


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
    assert "items" in data
    assert "pagination" in data

    items = data.get("items") or []
    pagination = data.get("pagination") or {}
    for key in ("total", "page", "pageSize", "totalPages"):
        assert key in pagination

    if items:
        sample = items[0]
        for key in (
            "id",
            "category",
            "type",
            "title",
            "status",
            "author",
            "created_at",
            "updated_at",
        ):
            assert key in sample


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
