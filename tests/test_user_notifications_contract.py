from __future__ import annotations

from contract_assertions import assert_error_contract, assert_success_contract


def test_my_notifications_requires_auth(client, login_as):
    login_as(None)
    response = client.get("/api/me/notifications")
    assert response.status_code == 401
    assert_error_contract(response.get_json() or {})


def test_my_notifications_create_list_and_mark_read_all(
    client, create_user, login_as, csrf_headers
):
    user = create_user(role="MEMBER")
    login_as(user)

    created = client.post(
        "/api/me/notifications",
        json={
            "title": "Q&A 답변 등록",
            "message": "테스트 답변 알림",
            "panel": "qna",
            "targetId": 11,
            "kind": "qna_answer",
            "meta": {"qnaId": 11, "anchorId": "qna-answer-anchor"},
        },
        headers=csrf_headers(),
    )
    assert created.status_code == 201
    created_payload = created.get_json() or {}
    assert_success_contract(created_payload)

    listed = client.get("/api/me/notifications")
    assert listed.status_code == 200
    listed_payload = listed.get_json() or {}
    assert_success_contract(listed_payload)
    listed_data = listed_payload.get("data") or {}
    items = listed_data.get("items") or []
    assert len(items) >= 1
    assert int(listed_data.get("unreadCount") or 0) >= 1

    marked = client.patch("/api/me/notifications/read-all", headers=csrf_headers())
    assert marked.status_code == 200
    marked_payload = marked.get_json() or {}
    assert_success_contract(marked_payload)
    marked_data = marked_payload.get("data") or {}
    assert int(marked_data.get("unreadCount") or 0) == 0

    unread_only = client.get("/api/me/notifications?filter=unread")
    assert unread_only.status_code == 200
    unread_payload = unread_only.get_json() or {}
    assert_success_contract(unread_payload)
    unread_items = ((unread_payload.get("data") or {}).get("items") or [])
    assert unread_items == []


def test_my_notifications_cleanup_old_records(
    client, create_user, login_as, csrf_headers
):
    from weave.core import get_db_connection

    user = create_user(role="MEMBER")
    login_as(user)
    conn = get_db_connection()
    conn.execute(
        """
        INSERT INTO in_app_notifications
        (user_id, kind, title, message, panel, target_id, meta_json, is_read, created_at, read_at)
        VALUES (?, 'general', 'old', 'old', '', 0, '{}', 0, datetime('now', '-100 day'), NULL)
        """,
        (user["id"],),
    )
    conn.commit()
    conn.close()

    response = client.get("/api/me/notifications")
    assert response.status_code == 200
    payload = response.get_json() or {}
    assert_success_contract(payload)
    data = payload.get("data") or {}
    assert all(str(item.get("title") or "") != "old" for item in (data.get("items") or []))

    # Ensure API still allows new inserts after cleanup.
    created = client.post(
        "/api/me/notifications",
        json={"title": "new", "message": "ok"},
        headers=csrf_headers(),
    )
    assert created.status_code == 201
    assert_success_contract(created.get_json() or {})
