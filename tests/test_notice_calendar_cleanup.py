from __future__ import annotations


def test_delete_notice_cleans_linked_calendar_items(client, create_user, login_as, csrf_headers):
    from weave.core import get_db_connection
    from weave.time_utils import now_iso

    executive = create_user(role="EXECUTIVE")
    login_as(executive)

    create_payload = {
        "category": "notice",
        "title": "연동 공지 삭제 테스트",
        "content": "캘린더 연동 확인",
        "volunteerStartDate": "2099-05-10",
        "volunteerEndDate": "2099-05-11",
    }
    created = client.post(
        "/api/posts",
        json=create_payload,
        headers=csrf_headers(),
    )
    assert created.status_code == 201
    post_id = int(((created.get_json() or {}).get("data") or {}).get("post_id") or 0)
    assert post_id > 0

    conn = get_db_connection()
    post_row = conn.execute("SELECT * FROM posts WHERE id = ?", (post_id,)).fetchone()
    assert post_row is not None

    linked_activity = conn.execute(
        "SELECT * FROM activities WHERE notice_post_id = ? LIMIT 1",
        (post_id,),
    ).fetchone()
    assert linked_activity is not None

    # legacy-style notice calendar row without notice_post_id (for backward compatibility cleanup)
    conn.execute(
        """
        INSERT INTO activities (
            title, description, start_at, end_at, place, supplies, gather_time,
            manager_name, recruitment_limit, created_by, created_at, notice_post_id
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            str(post_row["title"]),
            "legacy row",
            "2099-05-10T09:00:00",
            "2099-05-11T18:00:00",
            "공지사항",
            "",
            "",
            "관리자",
            0,
            int(post_row["author_id"] or 0),
            now_iso(),
            None,
        ),
    )

    # linked event row
    conn.execute(
        """
        INSERT INTO events (
            title, description, location, event_date, max_participants,
            supplies, notice_post_id, start_datetime, end_datetime, capacity,
            created_by, created_at, updated_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            "연동 이벤트",
            "desc",
            "장소",
            "2099-05-10T09:00:00",
            10,
            "",
            post_id,
            "2099-05-10T09:00:00",
            "2099-05-11T18:00:00",
            10,
            int(post_row["author_id"] or 0),
            now_iso(),
            now_iso(),
        ),
    )
    conn.commit()
    conn.close()

    deleted = client.delete(f"/api/posts/{post_id}", headers=csrf_headers())
    assert deleted.status_code == 200

    conn = get_db_connection()
    assert conn.execute("SELECT id FROM posts WHERE id = ?", (post_id,)).fetchone() is None
    assert conn.execute("SELECT id FROM activities WHERE notice_post_id = ?", (post_id,)).fetchone() is None
    assert conn.execute("SELECT id FROM events WHERE notice_post_id = ?", (post_id,)).fetchone() is None

    legacy_left = conn.execute(
        """
        SELECT id FROM activities
        WHERE title = ?
          AND place = '공지사항'
          AND start_at LIKE ?
          AND end_at LIKE ?
        """,
        (
            "연동 공지 삭제 테스트",
            "2099-05-10%",
            "2099-05-11%",
        ),
    ).fetchone()
    conn.close()
    assert legacy_left is None
