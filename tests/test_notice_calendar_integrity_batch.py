from __future__ import annotations


def test_notice_update_syncs_linked_activity_window(
    client, create_user, login_as, csrf_headers
):
    from weave.core import get_db_connection

    executive = create_user(role="EXECUTIVE")
    login_as(executive)

    created = client.post(
        "/api/posts",
        json={
            "category": "notice",
            "title": "봉사 일정 연동 공지",
            "content": "초기 일정",
            "volunteerStartDate": "2099-07-01",
            "volunteerEndDate": "2099-07-02",
        },
        headers=csrf_headers(),
    )
    assert created.status_code == 201
    post_id = int(((created.get_json() or {}).get("data") or {}).get("post_id") or 0)
    assert post_id > 0

    updated = client.put(
        f"/api/posts/{post_id}",
        json={
            "category": "notice",
            "title": "봉사 일정 연동 공지(수정)",
            "content": "수정 일정",
            "volunteerStartDate": "2099-08-10",
            "volunteerEndDate": "2099-08-11",
        },
        headers=csrf_headers(),
    )
    assert updated.status_code == 200

    conn = get_db_connection()
    rows = conn.execute(
        "SELECT id, title, start_at, end_at FROM activities WHERE notice_post_id = ? ORDER BY id ASC",
        (post_id,),
    ).fetchall()
    conn.close()
    assert len(rows) == 1
    row = rows[0]
    assert str(row["title"] or "").strip() == "봉사 일정 연동 공지(수정)"
    assert str(row["start_at"] or "").startswith("2099-08-10")
    assert str(row["end_at"] or "").startswith("2099-08-11")


def test_admin_integrity_batch_cleans_orphan_and_duplicate_rows(
    client, create_user, login_as, csrf_headers
):
    from weave.core import get_db_connection
    from weave.time_utils import now_iso

    executive = create_user(role="EXECUTIVE")
    login_as(executive)

    created = client.post(
        "/api/posts",
        json={
            "category": "notice",
            "title": "무결성 점검 대상",
            "content": "본문",
            "volunteerStartDate": "2099-09-01",
            "volunteerEndDate": "2099-09-01",
        },
        headers=csrf_headers(),
    )
    assert created.status_code == 201
    post_id = int(((created.get_json() or {}).get("data") or {}).get("post_id") or 0)
    assert post_id > 0

    conn = get_db_connection()
    # Duplicate linked activity for same notice_post_id
    conn.execute(
        """
        INSERT INTO activities (
            title, description, start_at, end_at, place, supplies, gather_time,
            manager_name, recruitment_limit, notice_post_id, created_by, created_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            "무결성 점검 대상",
            "dup",
            "2099-09-01T09:00:00",
            "2099-09-01T18:00:00",
            "공지사항",
            "",
            "",
            "관리자",
            0,
            post_id,
            int(executive["id"]),
            now_iso(),
        ),
    )
    # Orphan rows with invalid notice_post_id
    conn.execute(
        """
        INSERT INTO activities (
            title, description, start_at, end_at, place, supplies, gather_time,
            manager_name, recruitment_limit, notice_post_id, created_by, created_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            "고아 활동",
            "orphan",
            "2099-09-03T09:00:00",
            "2099-09-03T18:00:00",
            "공지사항",
            "",
            "",
            "관리자",
            0,
            999999,
            int(executive["id"]),
            now_iso(),
        ),
    )
    conn.execute(
        """
        INSERT INTO events (
            title, description, location, event_date, max_participants,
            supplies, notice_post_id, start_datetime, end_datetime, capacity,
            created_by, created_at, updated_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            "고아 이벤트",
            "orphan",
            "장소",
            "2099-09-03T09:00:00",
            10,
            "",
            999999,
            "2099-09-03T09:00:00",
            "2099-09-03T18:00:00",
            10,
            int(executive["id"]),
            now_iso(),
            now_iso(),
        ),
    )
    conn.commit()
    conn.close()

    run_res = client.post(
        "/api/admin/maintenance/notice-calendar-integrity",
        headers=csrf_headers(),
    )
    assert run_res.status_code == 200
    data = ((run_res.get_json() or {}).get("data") or {}).get("summary") or {}
    assert int(data.get("checkedNotices") or 0) >= 1
    assert int(data.get("orphanActivitiesDeleted") or 0) >= 1
    assert int(data.get("orphanEventsDeleted") or 0) >= 1
    assert int(data.get("activityDeduped") or 0) >= 1

    conn = get_db_connection()
    orphan_activity = conn.execute(
        "SELECT id FROM activities WHERE notice_post_id = 999999 LIMIT 1"
    ).fetchone()
    orphan_event = conn.execute(
        "SELECT id FROM events WHERE notice_post_id = 999999 LIMIT 1"
    ).fetchone()
    linked_count = conn.execute(
        "SELECT COUNT(*) AS c FROM activities WHERE notice_post_id = ?",
        (post_id,),
    ).fetchone()["c"]
    conn.close()
    assert orphan_activity is None
    assert orphan_event is None
    assert int(linked_count or 0) == 1

