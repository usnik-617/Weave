from __future__ import annotations

from weave.core import (
    get_db_connection,
    log_audit,
    record_user_activity,
    send_event_change_notifications,
)
from weave.time_utils import now_iso


def create_activity_record(payload, me):
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute(
        """
        INSERT INTO activities (
            title, description, start_at, end_at, place, supplies, gather_time,
            manager_name, recruitment_limit, recurrence_group_id, created_by, created_at
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            str(payload.get("title", "")).strip(),
            str(payload.get("description", "")).strip(),
            str(payload.get("startAt", "")).strip(),
            str(payload.get("endAt", "")).strip(),
            str(payload.get("place", "")).strip(),
            str(payload.get("supplies", "")).strip(),
            str(payload.get("gatherTime", "")).strip(),
            str(payload.get("manager", me["name"])).strip(),
            int(payload.get("recruitmentLimit", 0) or 0),
            str(payload.get("recurrenceGroupId", "")).strip(),
            me["id"],
            now_iso(),
        ),
    )
    activity_id = cur.lastrowid
    conn.commit()
    row = conn.execute(
        "SELECT * FROM activities WHERE id = ?", (activity_id,)
    ).fetchone()
    conn.close()
    return row


def update_activity_record(activity_id, payload, target, me):
    conn = get_db_connection()
    conn.execute(
        """
        UPDATE activities
        SET title = ?, description = ?, start_at = ?, end_at = ?, place = ?, supplies = ?,
            gather_time = ?, manager_name = ?, recruitment_limit = ?
        WHERE id = ?
        """,
        (
            str(payload.get("title", target["title"] or "")).strip(),
            str(payload.get("description", target["description"] or "")).strip(),
            str(payload.get("startAt", target["start_at"] or "")).strip(),
            str(payload.get("endAt", target["end_at"] or "")).strip(),
            str(payload.get("place", target["place"] or "")).strip(),
            str(payload.get("supplies", target["supplies"] or "")).strip(),
            str(payload.get("gatherTime", target["gather_time"] or "")).strip(),
            str(payload.get("manager", target["manager_name"] or me["name"])).strip(),
            int(payload.get("recruitmentLimit", target["recruitment_limit"]) or 0),
            activity_id,
        ),
    )
    conn.commit()
    row = conn.execute(
        "SELECT * FROM activities WHERE id = ?", (activity_id,)
    ).fetchone()
    conn.close()
    return row


def cancel_activity_record(activity_id):
    conn = get_db_connection()
    conn.execute(
        "UPDATE activities SET is_cancelled = 1, cancelled_at = ? WHERE id = ?",
        (now_iso(), activity_id),
    )
    conn.execute(
        """
        UPDATE activity_applications
        SET status = 'cancelled', updated_at = ?
        WHERE activity_id = ?
          AND status IN ('waiting', 'confirmed')
        """,
        (now_iso(), activity_id),
    )
    conn.commit()
    conn.close()


def cancel_recurrence_group_records(activity_ids):
    conn = get_db_connection()
    placeholders = ",".join(["?"] * len(activity_ids))
    conn.execute(
        f"UPDATE activities SET is_cancelled = 1, cancelled_at = ? WHERE id IN ({placeholders})",
        [now_iso(), *activity_ids],
    )
    conn.execute(
        f"""
        UPDATE activity_applications
        SET status = 'cancelled', updated_at = ?
        WHERE activity_id IN ({placeholders})
          AND status IN ('waiting', 'confirmed')
        """,
        [now_iso(), *activity_ids],
    )
    conn.commit()
    conn.close()


def create_event_record(payload, me):
    conn = get_db_connection()
    cur = conn.cursor()
    title = str(payload.get("title", "")).strip()
    start_datetime = str(
        payload.get("start_datetime", payload.get("event_date", ""))
    ).strip()
    end_datetime = str(payload.get("end_datetime", start_datetime)).strip()
    cur.execute(
        """
        INSERT INTO events (
            title, description, location, event_date, start_datetime, end_datetime,
            max_participants, capacity, supplies, notice_post_id, created_by, created_at, updated_at
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            title,
            str(payload.get("description", "")).strip(),
            str(payload.get("location", "")).strip(),
            start_datetime,
            start_datetime,
            end_datetime,
            int(payload.get("max_participants", payload.get("capacity", 0)) or 0),
            int(payload.get("capacity", payload.get("max_participants", 0)) or 0),
            str(payload.get("supplies", "")).strip(),
            payload.get("notice_post_id"),
            me["id"],
            now_iso(),
            now_iso(),
        ),
    )
    event_id = cur.lastrowid
    log_audit(conn, "create_event", "event", event_id, me["id"])
    record_user_activity(conn, me["id"], "event_create", "event", event_id, {"title": title})
    conn.commit()
    conn.close()
    return event_id


def update_event_record(event_id, payload, target, me):
    conn = get_db_connection()
    title = str(payload.get("title", target["title"])).strip()
    description = str(payload.get("description", target["description"])).strip()
    location = str(payload.get("location", target["location"])).strip()
    supplies = str(payload.get("supplies", target["supplies"])).strip()
    notice_post_id = payload.get("notice_post_id", target["notice_post_id"])
    start_datetime = str(
        payload.get(
            "start_datetime",
            payload.get("event_date", target["start_datetime"] or target["event_date"]),
        )
    ).strip()
    end_datetime = str(
        payload.get("end_datetime", target["end_datetime"] or start_datetime)
    ).strip()
    capacity = int(
        payload.get(
            "capacity",
            payload.get(
                "max_participants", target["capacity"] or target["max_participants"]
            ),
        )
        or 0
    )

    conn.execute(
        """
        UPDATE events
        SET title = ?, description = ?, location = ?, supplies = ?, notice_post_id = ?,
            event_date = ?, start_datetime = ?, end_datetime = ?, max_participants = ?, capacity = ?, updated_at = ?
        WHERE id = ?
        """,
        (
            title,
            description,
            location,
            supplies,
            notice_post_id,
            start_datetime,
            start_datetime,
            end_datetime,
            capacity,
            capacity,
            now_iso(),
            event_id,
        ),
    )
    notified = send_event_change_notifications(conn, event_id, title)
    log_audit(conn, "update_event", "event", event_id, me["id"])
    conn.commit()
    conn.close()
    return notified


def upsert_event_vote(event_id, me, status):
    conn = get_db_connection()
    existing = conn.execute(
        "SELECT id FROM event_votes WHERE event_id = ? AND user_id = ?",
        (event_id, me["id"]),
    ).fetchone()
    if existing:
        conn.execute(
            "UPDATE event_votes SET vote_status = ?, updated_at = ? WHERE id = ?",
            (status, now_iso(), existing["id"]),
        )
    else:
        conn.execute(
            "INSERT INTO event_votes (event_id, user_id, vote_status, created_at, updated_at) VALUES (?, ?, ?, ?, ?)",
            (event_id, me["id"], status, now_iso(), now_iso()),
        )
    log_audit(conn, "vote_event", "event", event_id, me["id"], {"status": status})
    conn.commit()
    conn.close()
