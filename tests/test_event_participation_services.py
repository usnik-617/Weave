from __future__ import annotations

from weave import event_participation_policy as policy


def test_event_participation_policy_transitions():
    assert policy.is_account_blocked({"status": "suspended"}) is True
    assert policy.is_account_blocked({"status": "active"}) is False

    assert policy.can_reapply_activity(None) is True
    assert policy.can_reapply_activity({"status": "cancelled"}) is True
    assert policy.can_reapply_activity({"status": "noshow"}) is True
    assert policy.can_reapply_activity({"status": "confirmed"}) is False

    assert policy.event_capacity_reached(10, 10) is True
    assert policy.event_capacity_reached(10, 9) is False

    assert policy.next_activity_status(0, 999) == "confirmed"
    assert policy.next_activity_status(10, 9) == "confirmed"
    assert policy.next_activity_status(10, 10) == "waiting"


def test_event_participation_command_service_mutations(app, create_user):
    from weave.core import get_db_connection
    from weave import event_participation_command_service as svc
    from weave.time_utils import now_iso

    user = create_user(role="MEMBER")
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute(
        """
        INSERT INTO events (
            title, description, location, event_date, start_datetime, end_datetime,
            max_participants, capacity, supplies, notice_post_id, created_by, created_at, updated_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            "svc-event",
            "desc",
            "loc",
            "2099-01-01T10:00:00",
            "2099-01-01T10:00:00",
            "2099-01-01T12:00:00",
            10,
            10,
            "",
            None,
            user["id"],
            now_iso(),
            now_iso(),
        ),
    )
    event_id = cur.lastrowid

    cur.execute(
        """
        INSERT INTO activities (
            title, description, start_at, end_at, place, supplies, gather_time,
            manager_name, recruitment_limit, recurrence_group_id, created_by, created_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            "svc-activity",
            "desc",
            "2099-01-01T10:00:00",
            "2099-01-01T11:00:00",
            "loc",
            "",
            "",
            "mgr",
            5,
            "",
            user["id"],
            now_iso(),
        ),
    )
    activity_id = cur.lastrowid
    conn.commit()

    svc.upsert_event_participation(conn, event_id, user["id"], now_iso)
    row = conn.execute(
        "SELECT * FROM event_participants WHERE event_id = ? AND user_id = ?",
        (event_id, user["id"]),
    ).fetchone()
    assert row is not None

    svc.cancel_event_participation(conn, row["id"], now_iso)
    cancelled = conn.execute(
        "SELECT status FROM event_participants WHERE id = ?",
        (row["id"],),
    ).fetchone()
    assert str(cancelled["status"]).lower() == "cancelled"

    svc.upsert_activity_application(conn, activity_id, user["id"], "confirmed", None, now_iso)
    app_row = conn.execute(
        "SELECT * FROM activity_applications WHERE activity_id = ? AND user_id = ?",
        (activity_id, user["id"]),
    ).fetchone()
    assert app_row is not None

    svc.cancel_activity_application(conn, app_row["id"], now_iso)
    app_cancelled = conn.execute(
        "SELECT status FROM activity_applications WHERE id = ?",
        (app_row["id"],),
    ).fetchone()
    assert str(app_cancelled["status"]).lower() == "cancelled"

    conn.commit()
    conn.close()
