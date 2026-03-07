from __future__ import annotations

from weave import event_policy
from weave.core import get_db_connection, serialize_activity_row
from weave.time_utils import activity_start_date_local


def list_activities_items(include_all, start_date, end_date):
    conn = get_db_connection()
    rows = conn.execute(
        """
                SELECT a.*
                FROM activities a
                JOIN users u ON u.id = a.created_by
                WHERE a.is_cancelled = 0
                    AND UPPER(COALESCE(u.role, '')) IN ('EXECUTIVE', 'LEADER', 'VICE_LEADER', 'ADMIN')
        ORDER BY start_at ASC
        """,
    ).fetchall()
    conn.close()

    if include_all:
        filtered_rows = rows
    else:
        filtered_rows = []
        for row in rows:
            activity_date = activity_start_date_local(row["start_at"])
            if activity_date and start_date <= activity_date <= end_date:
                filtered_rows.append(row)

    return [serialize_activity_row(row) for row in filtered_rows]


def get_active_activity_ids_by_group(group_id):
    conn = get_db_connection()
    rows = conn.execute(
        "SELECT id FROM activities WHERE recurrence_group_id = ? AND is_cancelled = 0",
        (group_id,),
    ).fetchall()
    conn.close()
    return [row["id"] for row in rows]


def recurrence_group_impact_data(group_id):
    conn = get_db_connection()
    activity_count = conn.execute(
        "SELECT COUNT(*) AS c FROM activities WHERE recurrence_group_id = ? AND is_cancelled = 0",
        (group_id,),
    ).fetchone()["c"]
    application_count = conn.execute(
        """
        SELECT COUNT(*) AS c
        FROM activity_applications ap
        JOIN activities a ON a.id = ap.activity_id
        WHERE a.recurrence_group_id = ?
          AND a.is_cancelled = 0
          AND ap.status IN ('waiting', 'confirmed')
        """,
        (group_id,),
    ).fetchone()["c"]

    preview_rows = conn.execute(
        """
        SELECT
            a.id,
            a.title,
            a.start_at,
            a.end_at,
            a.place,
            (
                SELECT COUNT(*)
                FROM activity_applications ap
                WHERE ap.activity_id = a.id
                  AND ap.status IN ('waiting', 'confirmed')
            ) AS active_applications
        FROM activities a
        WHERE a.recurrence_group_id = ?
          AND a.is_cancelled = 0
        ORDER BY a.start_at ASC
        LIMIT 5
        """,
        (group_id,),
    ).fetchall()
    conn.close()

    return {
        "activityCount": int(activity_count or 0),
        "applicationCount": int(application_count or 0),
        "previewItems": [
            {
                "id": row["id"],
                "title": row["title"],
                "startAt": row["start_at"],
                "endAt": row["end_at"],
                "place": row["place"],
                "applicationCount": int(row["active_applications"] or 0),
            }
            for row in preview_rows
        ],
    }


def events_page_data(me_id, page, page_size):
    offset = (page - 1) * page_size
    conn = get_db_connection()
    total = conn.execute("SELECT COUNT(*) AS c FROM events").fetchone()["c"]
    rows = conn.execute(
        """
        SELECT e.*, u.username AS author_username,
               (SELECT COUNT(*) FROM event_participants p WHERE p.event_id = e.id AND p.status='registered') AS participant_count,
               (SELECT status FROM event_participants p2 WHERE p2.event_id = e.id AND p2.user_id = ? LIMIT 1) AS my_status
        FROM events e
        LEFT JOIN users u ON u.id = e.created_by
        ORDER BY COALESCE(e.start_datetime, e.event_date) ASC
        LIMIT ? OFFSET ?
        """,
        (me_id, page_size, offset),
    ).fetchall()
    conn.close()

    return {
        "items": [event_policy.serialize_event_list_item(row) for row in rows],
        "pagination": {
            "total": int(total or 0),
            "page": page,
            "pageSize": page_size,
            "totalPages": max(1, (int(total or 0) + page_size - 1) // page_size),
        },
    }


def event_detail_data(event_id, me_id):
    conn = get_db_connection()
    row = conn.execute(
        """
        SELECT e.*, u.username AS author_username,
               (SELECT COUNT(*) FROM event_participants p WHERE p.event_id = e.id AND p.status = 'registered') AS participant_count,
               (SELECT status FROM event_participants p2 WHERE p2.event_id = e.id AND p2.user_id = ? LIMIT 1) AS my_status
        FROM events e
        LEFT JOIN users u ON u.id = e.created_by
        WHERE e.id = ?
        """,
        (me_id, event_id),
    ).fetchone()
    if not row:
        conn.close()
        return None

    participants = conn.execute(
        """
        SELECT ep.user_id, ep.status, ep.created_at,
               u.username, u.nickname, u.role
        FROM event_participants ep
        JOIN users u ON u.id = ep.user_id
        WHERE ep.event_id = ? AND ep.status = 'registered'
        ORDER BY ep.created_at ASC
        """,
        (event_id,),
    ).fetchall()
    conn.close()

    return event_policy.serialize_event_detail(row, participants)
