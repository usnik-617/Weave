from __future__ import annotations

import pytest

from weave.authz import role_at_least


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
    create_qna = client.post(
        "/api/posts",
        json={"category": "qna", "title": "질문", "content": "질문 본문"},
        headers=csrf_headers(),
    )

    assert public_posts.status_code == 200
    assert comment_notice.status_code == 403
    assert comment_gallery.status_code == 403
    assert event_detail.status_code == 403
    assert join_event.status_code == 403
    assert create_notice.status_code == 403
    assert create_gallery.status_code == 403
    expected_qna_status = 201 if role_at_least(general["role"], "GENERAL") else 403
    assert create_qna.status_code == expected_qna_status


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


def test_executive_cannot_approve_user_via_admin_approve_endpoint(
    client, create_user, login_as, csrf_headers
):
    executive = create_user(role="EXECUTIVE")
    target = create_user(role="GENERAL", status="pending")
    login_as(executive)

    response = client.post(
        f"/api/admin/users/{target['id']}/approve",
        json={"role": "MEMBER"},
        headers=csrf_headers(),
    )

    assert response.status_code == 403


def test_admin_stats_counts_event_participants_table(
    client, create_user, login_as, csrf_headers, sample_event
):
    manager = create_user(role="VICE_LEADER")
    member = create_user(role="MEMBER")
    event_id = sample_event(author_id=manager["id"])

    login_as(member)
    join_res = client.post(f"/api/events/{event_id}/join", headers=csrf_headers())
    assert join_res.status_code == 200

    login_as(manager)
    stats_res = client.get("/api/admin/stats")

    assert stats_res.status_code == 200
    payload = (stats_res.get_json() or {}).get("data") or {}
    assert int(payload.get("total_participants") or 0) >= 1


@pytest.mark.parametrize("status", ["suspended", "deleted"])
def test_non_active_member_cannot_join_or_cancel_event(
    status, client, create_user, login_as, csrf_headers, sample_event
):
    non_active_member = create_user(role="MEMBER", status=status)
    event_id = sample_event(author_id=non_active_member["id"])
    login_as(non_active_member)

    join_res = client.post(f"/api/events/{event_id}/join", headers=csrf_headers())
    cancel_res = client.post(
        f"/api/events/{event_id}/cancel", headers=csrf_headers()
    )

    assert join_res.status_code == 403
    assert cancel_res.status_code == 403


def test_activity_apply_and_cancel_use_success_error_schema(
    client, create_user, login_as, csrf_headers
):
    from weave.core import get_db_connection
    from weave.time_utils import now_iso

    member = create_user(role="MEMBER")
    login_as(member)

    conn = get_db_connection()
    cur = conn.cursor()
    now = now_iso()
    cur.execute(
        """
        INSERT INTO activities (
            title, description, start_at, end_at, place, supplies, gather_time,
            manager_name, recruitment_limit, recurrence_group_id, created_by, created_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            "스키마 테스트 활동",
            "설명",
            "2099-01-02T10:00:00",
            "2099-01-02T12:00:00",
            "장소",
            "준비물",
            "09:50",
            "매니저",
            5,
            "",
            member["id"],
            now,
        ),
    )
    activity_id = cur.lastrowid
    conn.commit()
    conn.close()

    apply_res = client.post(
        f"/api/activities/{activity_id}/apply", headers=csrf_headers()
    )
    assert apply_res.status_code == 200
    apply_payload = apply_res.get_json() or {}
    assert apply_payload.get("success") is True
    assert isinstance(apply_payload.get("data"), dict)
    assert "status" in (apply_payload.get("data") or {})

    cancel_res = client.post(
        f"/api/activities/{activity_id}/cancel", headers=csrf_headers()
    )
    assert cancel_res.status_code == 200
    cancel_payload = cancel_res.get_json() or {}
    assert cancel_payload.get("success") is True
    assert isinstance(cancel_payload.get("data"), dict)
    assert (cancel_payload.get("data") or {}).get("status") == "cancelled"


def test_activity_qr_attendance_endpoints_use_success_error_schema(
    client, create_user, login_as, csrf_headers
):
    from weave.core import get_db_connection
    from weave.time_utils import now_iso

    member = create_user(role="MEMBER")
    login_as(member)

    conn = get_db_connection()
    cur = conn.cursor()
    now = now_iso()
    cur.execute(
        """
        INSERT INTO activities (
            title, description, start_at, end_at, place, supplies, gather_time,
            manager_name, recruitment_limit, recurrence_group_id, created_by, created_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            "QR 테스트 활동",
            "설명",
            "2099-01-03T10:00:00",
            "2099-01-03T12:00:00",
            "장소",
            "준비물",
            "09:50",
            "매니저",
            5,
            "",
            member["id"],
            now,
        ),
    )
    activity_id = cur.lastrowid
    cur.execute(
        """
        INSERT INTO activity_applications (
            activity_id, user_id, status, attendance_status, attendance_method,
            hours, points, penalty_points, applied_at, updated_at
        ) VALUES (?, ?, 'confirmed', 'pending', '', 0, 0, 0, ?, ?)
        """,
        (activity_id, member["id"], now, now),
    )
    conn.commit()
    conn.close()

    qr_token_res = client.post(
        f"/api/activities/{activity_id}/attendance/qr-token",
        headers=csrf_headers(),
    )
    assert qr_token_res.status_code == 200
    qr_token_payload = qr_token_res.get_json() or {}
    assert qr_token_payload.get("success") is True
    qr_data = qr_token_payload.get("data") or {}
    assert isinstance(qr_data.get("token"), str)
    assert qr_data.get("token")

    qr_check_res = client.post(
        f"/api/activities/{activity_id}/attendance/qr-check",
        json={"token": qr_data.get("token")},
        headers=csrf_headers(),
    )
    assert qr_check_res.status_code == 200
    qr_check_payload = qr_check_res.get_json() or {}
    assert qr_check_payload.get("success") is True
    assert isinstance((qr_check_payload.get("data") or {}).get("hours"), (int, float))
