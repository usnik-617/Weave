from __future__ import annotations

import threading
import time

from weave.core import get_db_connection, write_app_log
from weave.time_utils import now_iso

_RUN_LOCK = threading.Lock()
_LOOP_THREAD = None
_STOP_EVENT = threading.Event()


def _normalize_date_prefix(value):
    text = str(value or "").strip()
    if not text:
        return ""
    if "T" in text:
        text = text.split("T", 1)[0]
    return text[:10]


def _expected_activity_datetimes(post_row):
    start_day = _normalize_date_prefix(post_row["volunteer_start_date"])
    end_day = _normalize_date_prefix(post_row["volunteer_end_date"]) or start_day
    if not start_day:
        return "", ""
    return f"{start_day}T09:00:00", f"{end_day}T18:00:00"


def _delete_activity_with_relations(conn, activity_id):
    conn.execute("DELETE FROM activity_applications WHERE activity_id = ?", (activity_id,))
    conn.execute("DELETE FROM attendance_qr_tokens WHERE activity_id = ?", (activity_id,))
    conn.execute("DELETE FROM activities WHERE id = ?", (activity_id,))


def _delete_event_with_relations(conn, event_id):
    conn.execute("DELETE FROM participants WHERE event_id = ?", (event_id,))
    conn.execute("DELETE FROM event_participants WHERE event_id = ?", (event_id,))
    conn.execute("DELETE FROM event_votes WHERE event_id = ?", (event_id,))
    conn.execute("DELETE FROM event_attendance WHERE event_id = ?", (event_id,))
    conn.execute("DELETE FROM volunteer_activity WHERE event_id = ?", (event_id,))
    conn.execute("DELETE FROM events WHERE id = ?", (event_id,))


def sync_notice_linked_calendar(conn, post_row):
    post_id = int(post_row["id"] or 0)
    summary = {
        "postId": post_id,
        "activityDeleted": 0,
        "activityUpdated": 0,
        "activityCreated": 0,
        "activityDeduped": 0,
        "eventDeleted": 0,
    }
    if post_id <= 0:
        return summary

    linked_events = conn.execute(
        "SELECT id FROM events WHERE notice_post_id = ? ORDER BY id ASC",
        (post_id,),
    ).fetchall()
    linked_activities = conn.execute(
        "SELECT * FROM activities WHERE notice_post_id = ? ORDER BY id ASC",
        (post_id,),
    ).fetchall()

    start_at, end_at = _expected_activity_datetimes(post_row)
    if not start_at:
        for row in linked_events:
            _delete_event_with_relations(conn, int(row["id"]))
            summary["eventDeleted"] += 1
        for row in linked_activities:
            _delete_activity_with_relations(conn, int(row["id"]))
            summary["activityDeleted"] += 1
        return summary

    # Keep at most one linked activity per notice and normalize stale title/date.
    primary = linked_activities[0] if linked_activities else None
    duplicates = linked_activities[1:] if len(linked_activities) > 1 else []
    for row in duplicates:
        _delete_activity_with_relations(conn, int(row["id"]))
        summary["activityDeduped"] += 1

    title = str(post_row["title"] or "").strip()
    content = str(post_row["content"] or "")
    author_id = int(post_row["author_id"] or 0) if post_row["author_id"] is not None else None
    manager_name = "관리자"
    if author_id:
        author = conn.execute(
            "SELECT nickname, username FROM users WHERE id = ?",
            (author_id,),
        ).fetchone()
        if author:
            manager_name = str(author["nickname"] or author["username"] or "관리자")

    if primary:
        conn.execute(
            """
            UPDATE activities
            SET title = ?, description = ?, start_at = ?, end_at = ?
            WHERE id = ?
            """,
            (
                title,
                content[:300],
                start_at,
                end_at,
                int(primary["id"]),
            ),
        )
        summary["activityUpdated"] += 1
    else:
        conn.execute(
            """
            INSERT INTO activities (
                title, description, start_at, end_at, place, supplies, gather_time,
                manager_name, recruitment_limit, notice_post_id, created_by, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                title,
                content[:300],
                start_at,
                end_at,
                "공지사항",
                "",
                "",
                manager_name,
                0,
                post_id,
                author_id,
                now_iso(),
            ),
        )
        summary["activityCreated"] += 1

    return summary


def run_notice_calendar_integrity(conn=None):
    owns_conn = conn is None
    if owns_conn:
        conn = get_db_connection()

    summary = {
        "checkedNotices": 0,
        "orphanActivitiesDeleted": 0,
        "orphanEventsDeleted": 0,
        "activityDeleted": 0,
        "activityUpdated": 0,
        "activityCreated": 0,
        "activityDeduped": 0,
        "eventDeleted": 0,
    }
    with _RUN_LOCK:
        # 1) Delete true orphan links first (notice_post_id points to missing/non-notice post)
        orphan_activity_rows = conn.execute(
            """
            SELECT a.id
            FROM activities a
            LEFT JOIN posts p ON p.id = a.notice_post_id
            WHERE a.notice_post_id IS NOT NULL
              AND (p.id IS NULL OR p.category != 'notice')
            """
        ).fetchall()
        for row in orphan_activity_rows:
            _delete_activity_with_relations(conn, int(row["id"]))
            summary["orphanActivitiesDeleted"] += 1

        orphan_event_rows = conn.execute(
            """
            SELECT e.id
            FROM events e
            LEFT JOIN posts p ON p.id = e.notice_post_id
            WHERE e.notice_post_id IS NOT NULL
              AND (p.id IS NULL OR p.category != 'notice')
            """
        ).fetchall()
        for row in orphan_event_rows:
            _delete_event_with_relations(conn, int(row["id"]))
            summary["orphanEventsDeleted"] += 1

        # 2) Reconcile linked rows for currently alive notice posts.
        notice_rows = conn.execute(
            """
            SELECT id, title, content, author_id, volunteer_start_date, volunteer_end_date
            FROM posts
            WHERE category = 'notice'
            """
        ).fetchall()
        for post_row in notice_rows:
            summary["checkedNotices"] += 1
            per_post = sync_notice_linked_calendar(conn, post_row)
            for key in ("activityDeleted", "activityUpdated", "activityCreated", "activityDeduped", "eventDeleted"):
                summary[key] += int(per_post.get(key, 0) or 0)

        conn.commit()

    if owns_conn:
        conn.close()
    return summary


def _integrity_loop(interval_sec):
    safe_interval = max(60, int(interval_sec or 600))
    while not _STOP_EVENT.wait(safe_interval):
        try:
            summary = run_notice_calendar_integrity()
            write_app_log("info", "notice_calendar_integrity_batch", extra=summary)
        except Exception as exc:  # pragma: no cover - defensive background logging path
            write_app_log(
                "warning",
                "notice_calendar_integrity_batch_failed",
                extra={"reason": str(exc)},
            )


def start_notice_calendar_integrity_worker(interval_sec=600):
    global _LOOP_THREAD
    if _LOOP_THREAD and _LOOP_THREAD.is_alive():
        return
    _STOP_EVENT.clear()
    _LOOP_THREAD = threading.Thread(
        target=_integrity_loop,
        args=(max(60, int(interval_sec or 600)),),
        daemon=True,
        name="weave-notice-calendar-integrity",
    )
    _LOOP_THREAD.start()
