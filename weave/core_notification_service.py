from __future__ import annotations

from datetime import datetime, timedelta
import json


def send_event_change_notifications(conn, event_id, title):
    from weave import core

    users = conn.execute(
        """
        SELECT u.email, u.id
        FROM event_participants p
        JOIN users u ON u.id = p.user_id
        WHERE p.event_id = ? AND p.status = 'registered'
        """,
        (event_id,),
    ).fetchall()
    sent = 0
    for user in users:
        key_target = f"{event_id}:{user['id']}"
        if core.notification_already_sent(conn, "event_changed", "event_user", key_target):
            continue
        if core.send_email(
            user["email"], "[Weave] 일정 변경 안내", f"일정이 변경되었습니다: {title}"
        ):
            core.mark_notification_sent(
                conn, "event_changed", "event_user", key_target, user["email"]
            )
            sent += 1
    return sent


def send_due_event_reminders(reference_time=None):
    return send_event_reminders(reference_time)


def send_event_reminders(reference_time=None):
    from weave import core

    now = reference_time or datetime.now()
    start = now.isoformat()
    end = (now + timedelta(hours=24)).isoformat()
    conn = core.get_db_connection()
    events = conn.execute(
        "SELECT id, title, event_date FROM events WHERE event_date >= ? AND event_date <= ?",
        (start, end),
    ).fetchall()
    sent_count = 0
    for event in events:
        recipients = conn.execute(
            """
            SELECT u.id, u.email
            FROM event_participants p
            JOIN users u ON u.id = p.user_id
            WHERE p.event_id = ? AND p.status = 'registered'
            """,
            (event["id"],),
        ).fetchall()
        for user in recipients:
            already_sent = conn.execute(
                "SELECT id FROM email_notifications WHERE user_id = ? AND event_id = ? AND type = 'event_reminder_24h'",
                (user["id"], event["id"]),
            ).fetchone()
            if already_sent:
                continue
            if core.send_email(
                user["email"],
                "[Weave] 활동 리마인더",
                f"내일 예정된 일정 안내: {event['title']} ({event['event_date']})",
            ):
                conn.execute(
                    "INSERT OR IGNORE INTO email_notifications (user_id, event_id, type, sent_at) VALUES (?, ?, 'event_reminder_24h', ?)",
                    (user["id"], event["id"], core.now_iso()),
                )
                sent_count += 1
            else:
                core.logger.error(
                    json.dumps(
                        {
                            "action": "send_event_reminder_failed",
                            "user_id": user["id"],
                            "event_id": event["id"],
                        },
                        ensure_ascii=False,
                    )
                )
    conn.commit()
    conn.close()
    return sent_count
