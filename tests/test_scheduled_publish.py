from __future__ import annotations

from datetime import datetime, timedelta


def _future_iso(hours=24):
    return (datetime.now() + timedelta(hours=hours)).replace(microsecond=0).isoformat()


def _past_iso(hours=24):
    return (datetime.now() - timedelta(hours=hours)).replace(microsecond=0).isoformat()


def _extract_items(response):
    payload = response.get_json() or {}
    data = payload.get("data") or {}
    return data.get("items") or payload.get("items") or []


def test_future_posts_hidden_from_normal_users(client, create_user, create_post_record, login_as):
    author = create_user(role="EXECUTIVE")
    general = create_user(role="GENERAL")
    future_at = _future_iso()

    notice_id = create_post_record(
        category="notice", author_id=author["id"], publish_at=future_at, title="future-notice"
    )
    gallery_id = create_post_record(
        category="gallery", author_id=author["id"], publish_at=future_at, title="future-gallery"
    )

    login_as(general)

    notice_list = client.get("/api/posts?type=notice&pageSize=200")
    gallery_list = client.get("/api/posts?type=gallery&pageSize=200")
    notice_items = _extract_items(notice_list)
    gallery_items = _extract_items(gallery_list)

    assert notice_list.status_code == 200
    assert gallery_list.status_code == 200
    assert all(int(item.get("id") or 0) != notice_id for item in notice_items)
    assert all(int(item.get("id") or 0) != gallery_id for item in gallery_items)


def test_future_posts_visible_to_admin_like_with_include_scheduled(
    client, create_user, create_post_record, login_as
):
    author = create_user(role="EXECUTIVE")
    admin_like = create_user(role="ADMIN")
    future_at = _future_iso()

    notice_id = create_post_record(
        category="notice", author_id=author["id"], publish_at=future_at, title="future-visible-notice"
    )

    login_as(admin_like)
    list_default = client.get("/api/posts?type=notice&pageSize=200")
    list_with_scheduled = client.get(
        "/api/posts?type=notice&pageSize=200&include_scheduled=true"
    )

    default_items = _extract_items(list_default)
    scheduled_items = _extract_items(list_with_scheduled)

    assert list_default.status_code == 200
    assert list_with_scheduled.status_code == 200
    assert all(int(item.get("id") or 0) != notice_id for item in default_items)
    assert any(int(item.get("id") or 0) == notice_id for item in scheduled_items)


def test_post_becomes_visible_when_publish_at_is_past(
    client, create_user, create_post_record, login_as
):
    author = create_user(role="EXECUTIVE")
    general = create_user(role="GENERAL")

    post_id = create_post_record(
        category="notice", author_id=author["id"], publish_at=_past_iso(), title="past-notice"
    )

    login_as(general)
    list_res = client.get("/api/posts?type=notice&pageSize=200")
    detail_res = client.get(f"/api/posts/{post_id}")

    assert list_res.status_code == 200
    assert detail_res.status_code == 200
    items = _extract_items(list_res)
    assert any(int(item.get("id") or 0) == post_id for item in items)


def test_detail_endpoint_matches_list_visibility_for_scheduled_post(
    client, create_user, create_post_record, login_as
):
    author = create_user(role="EXECUTIVE")
    general = create_user(role="GENERAL")
    admin_like = create_user(role="ADMIN")

    post_id = create_post_record(
        category="notice", author_id=author["id"], publish_at=_future_iso(), title="future-detail"
    )

    login_as(general)
    general_list = client.get("/api/posts?type=notice&pageSize=200")
    general_detail = client.get(f"/api/posts/{post_id}")

    login_as(admin_like)
    admin_list = client.get(
        "/api/posts?type=notice&pageSize=200&include_scheduled=true"
    )
    admin_detail = client.get(f"/api/posts/{post_id}")

    assert general_list.status_code == 200
    assert general_detail.status_code == 404
    assert all(int(item.get("id") or 0) != post_id for item in _extract_items(general_list))

    assert admin_list.status_code == 200
    assert admin_detail.status_code == 200
    assert any(int(item.get("id") or 0) == post_id for item in _extract_items(admin_list))


def test_scheduled_notice_and_gallery_follow_same_policy(
    client, create_user, create_post_record, login_as
):
    author = create_user(role="EXECUTIVE")
    general = create_user(role="GENERAL")
    admin_like = create_user(role="VICE_LEADER")
    future_at = _future_iso()

    notice_id = create_post_record(
        category="notice", author_id=author["id"], publish_at=future_at, title="scheduled-notice"
    )
    gallery_id = create_post_record(
        category="gallery", author_id=author["id"], publish_at=future_at, title="scheduled-gallery"
    )

    login_as(general)
    general_notice = client.get("/api/posts?type=notice&pageSize=200")
    general_gallery = client.get("/api/posts?type=gallery&pageSize=200")

    login_as(admin_like)
    admin_notice = client.get(
        "/api/posts?type=notice&pageSize=200&include_scheduled=true"
    )
    admin_gallery = client.get(
        "/api/posts?type=gallery&pageSize=200&include_scheduled=true"
    )

    assert all(
        int(item.get("id") or 0) != notice_id for item in _extract_items(general_notice)
    )
    assert all(
        int(item.get("id") or 0) != gallery_id for item in _extract_items(general_gallery)
    )
    assert any(
        int(item.get("id") or 0) == notice_id for item in _extract_items(admin_notice)
    )
    assert any(
        int(item.get("id") or 0) == gallery_id for item in _extract_items(admin_gallery)
    )
