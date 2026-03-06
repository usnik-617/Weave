from __future__ import annotations

import pytest


# A) Authorization tests


def test_general_user_permissions(
    client,
    create_user,
    login_as,
    csrf_headers,
    create_post_record,
    sample_event,
):
    general = create_user(role="GENERAL")
    notice_id = create_post_record(category="notice", author_id=general["id"])
    gallery_id = create_post_record(category="gallery", author_id=general["id"])
    event_id = sample_event(author_id=general["id"])

    login_as(general)

    public_posts = client.get("/api/posts?type=notice")
    comment_notice = client.post(
        f"/api/posts/{notice_id}/comments",
        json={"content": "댓글"},
        headers=csrf_headers(),
    )
    comment_gallery = client.post(
        f"/api/posts/{gallery_id}/comments",
        json={"content": "댓글"},
        headers=csrf_headers(),
    )
    event_detail = client.get(f"/api/events/{event_id}")
    join_event = client.post(f"/api/events/{event_id}/join", headers=csrf_headers())
    create_notice = client.post(
        "/api/posts",
        json={"category": "notice", "title": "공지", "content": "본문"},
        headers=csrf_headers(),
    )
    create_gallery = client.post(
        "/api/posts",
        json={"category": "gallery", "title": "갤러리", "content": "본문"},
        headers=csrf_headers(),
    )

    assert public_posts.status_code == 200
    assert comment_notice.status_code == 403
    assert comment_gallery.status_code == 403
    assert event_detail.status_code == 403
    assert join_event.status_code == 403
    assert create_notice.status_code == 403
    assert create_gallery.status_code == 403


def test_member_permissions(
    client,
    create_user,
    login_as,
    csrf_headers,
    create_post_record,
    sample_event,
):
    member = create_user(role="MEMBER")
    notice_id = create_post_record(category="notice")
    gallery_id = create_post_record(category="gallery")
    event_id = sample_event(author_id=member["id"])

    login_as(member)

    event_detail = client.get(f"/api/events/{event_id}")
    join_event = client.post(f"/api/events/{event_id}/join", headers=csrf_headers())
    cancel_event = client.post(
        f"/api/events/{event_id}/cancel", headers=csrf_headers()
    )
    comment_notice = client.post(
        f"/api/posts/{notice_id}/comments",
        json={"content": "단원 댓글"},
        headers=csrf_headers(),
    )
    comment_gallery = client.post(
        f"/api/posts/{gallery_id}/comments",
        json={"content": "단원 댓글"},
        headers=csrf_headers(),
    )
    create_notice = client.post(
        "/api/posts",
        json={"category": "notice", "title": "공지", "content": "본문"},
        headers=csrf_headers(),
    )
    create_gallery = client.post(
        "/api/posts",
        json={"category": "gallery", "title": "갤러리", "content": "본문"},
        headers=csrf_headers(),
    )

    assert event_detail.status_code == 200
    assert join_event.status_code == 200
    assert cancel_event.status_code == 200
    assert comment_notice.status_code == 201
    assert comment_gallery.status_code == 201
    assert create_notice.status_code == 403
    assert create_gallery.status_code == 403


def test_executive_permissions(
    client,
    create_user,
    login_as,
    csrf_headers,
    create_post_record,
    sample_event,
):
    executive = create_user(role="EXECUTIVE")
    notice_id = create_post_record(category="notice", author_id=executive["id"])
    event_id = sample_event(author_id=executive["id"])

    login_as(executive)

    create_notice = client.post(
        "/api/posts",
        json={"category": "notice", "title": "임원 공지", "content": "본문"},
        headers=csrf_headers(),
    )
    create_gallery = client.post(
        "/api/posts",
        json={"category": "gallery", "title": "임원 갤러리", "content": "본문"},
        headers=csrf_headers(),
    )
    comment_notice = client.post(
        f"/api/posts/{notice_id}/comments",
        json={"content": "임원 댓글"},
        headers=csrf_headers(),
    )
    event_detail = client.get(f"/api/events/{event_id}")
    event_join = client.post(f"/api/events/{event_id}/join", headers=csrf_headers())
    admin_pending = client.get("/api/admin/pending-users")

    assert create_notice.status_code == 201
    assert create_gallery.status_code == 201
    assert comment_notice.status_code == 201
    assert event_detail.status_code == 200
    assert event_join.status_code == 200
    assert admin_pending.status_code == 403


@pytest.mark.parametrize("role", ["LEADER", "VICE_LEADER", "ADMIN"])
def test_admin_like_roles_can_access_admin_endpoints(role, client, create_user, login_as):
    manager = create_user(role=role)
    login_as(manager)

    pending_users = client.get("/api/admin/pending-users")
    dashboard = client.get("/api/admin/dashboard")

    assert pending_users.status_code == 200
    assert dashboard.status_code == 200


@pytest.mark.parametrize("role", ["LEADER", "VICE_LEADER", "ADMIN"])
def test_admin_like_roles_can_manage_users_content_and_attendance(
    role,
    client,
    create_user,
    login_as,
    csrf_headers,
    sample_event,
):
    manager = create_user(role=role)
    target_member = create_user(role="MEMBER")
    event_id = sample_event(author_id=manager["id"])

    login_as(target_member)
    join_res = client.post(f"/api/events/{event_id}/join", headers=csrf_headers())
    assert join_res.status_code == 200

    login_as(manager)
    suspend_res = client.post(
        f"/api/admin/users/{target_member['id']}/suspend", headers=csrf_headers()
    )
    about_update = client.put(
        "/api/about/sections",
        json={"key": "history", "contentHtml": "updated"},
        headers=csrf_headers(),
    )
    attendance_res = client.post(
        f"/api/events/{event_id}/attendance",
        json={"user_id": target_member["id"], "status": "attended"},
        headers=csrf_headers(),
    )

    assert suspend_res.status_code == 200
    assert about_update.status_code == 200
    assert attendance_res.status_code == 200


def test_unauthenticated_endpoints_return_401(client, login_as):
    login_as(None)

    events_list = client.get("/api/events")
    admin_pending = client.get("/api/admin/pending-users")
    me_activity = client.get("/api/me/activity")

    assert events_list.status_code == 401
    assert admin_pending.status_code == 401
    assert me_activity.status_code == 401
