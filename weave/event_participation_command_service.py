from __future__ import annotations


def upsert_event_participation(conn, event_id, user_id, now_iso_func):
    existing = conn.execute(
        "SELECT * FROM event_participants WHERE event_id = ? AND user_id = ?",
        (event_id, user_id),
    ).fetchone()
    now = now_iso_func()
    if existing:
        conn.execute(
            "UPDATE event_participants SET status = 'registered', updated_at = ? WHERE id = ?",
            (now, existing["id"]),
        )
        return "updated"

    conn.execute(
        "INSERT INTO event_participants (event_id, user_id, status, created_at, updated_at) VALUES (?, ?, 'registered', ?, ?)",
        (event_id, user_id, now, now),
    )
    return "created"


def cancel_event_participation(conn, row_id, now_iso_func):
    conn.execute(
        "UPDATE event_participants SET status = 'cancelled', updated_at = ? WHERE id = ?",
        (now_iso_func(), row_id),
    )


def upsert_activity_application(
    conn,
    activity_id,
    user_id,
    next_status,
    existing,
    now_iso_func,
):
    now = now_iso_func()
    if existing:
        conn.execute(
            """
            UPDATE activity_applications
            SET status = ?, attendance_status = 'pending', attendance_method = '',
                updated_at = ?, hours = 0, points = 0, penalty_points = 0
            WHERE id = ?
            """,
            (next_status, now, existing["id"]),
        )
        return

    conn.execute(
        """
        INSERT INTO activity_applications (
            activity_id, user_id, status, attendance_status, attendance_method,
            hours, points, penalty_points, applied_at, updated_at
        )
        VALUES (?, ?, ?, 'pending', '', 0, 0, 0, ?, ?)
        """,
        (activity_id, user_id, next_status, now, now),
    )


def cancel_activity_application(conn, row_id, now_iso_func):
    conn.execute(
        "UPDATE activity_applications SET status = 'cancelled', updated_at = ? WHERE id = ?",
        (now_iso_func(), row_id),
    )
