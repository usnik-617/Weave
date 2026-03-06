from weave.authz import get_current_user_row, role_at_least
from weave.core import get_db_connection, log_audit, request
from weave.responses import error_response, success_response
from weave.time_utils import now_iso, parse_iso_datetime


def _event_duration_minutes(event_row):
    start_dt = parse_iso_datetime(
        event_row["start_datetime"] or event_row["event_date"]
    )
    end_dt = parse_iso_datetime(
        event_row["end_datetime"]
        or event_row["start_datetime"]
        or event_row["event_date"]
    )
    if not start_dt or not end_dt or end_dt <= start_dt:
        return 0
    return int((end_dt - start_dt).total_seconds() // 60)


def mark_event_attendance(event_id):
    payload = request.get_json(silent=True) or {}

    user_id = int(payload.get("user_id", 0) or 0)
    status = str(payload.get("status", "")).strip().lower()
    if user_id <= 0:
        return error_response("user_id는 필수입니다.", 400)
    if status not in ("registered", "attended", "absent"):
        return error_response(
            "status는 registered|attended|absent 중 하나여야 합니다.", 400
        )

    conn = get_db_connection()
    me = get_current_user_row(conn)
    if not me:
        conn.close()
        return error_response("Unauthorized", 401)
    if not role_at_least(me["role"], "VICE_LEADER"):
        conn.close()
        return error_response("부단장 이상만 출결을 처리할 수 있습니다.", 403)

    event = conn.execute("SELECT * FROM events WHERE id = ?", (event_id,)).fetchone()
    if not event:
        conn.close()
        return error_response("이벤트를 찾을 수 없습니다.", 404)

    participant = conn.execute(
        "SELECT id FROM event_participants WHERE event_id = ? AND user_id = ? AND status = 'registered'",
        (event_id, user_id),
    ).fetchone()
    if not participant:
        conn.close()
        return error_response("등록된 참여자를 찾을 수 없습니다.", 404)

    duration_minutes = _event_duration_minutes(event) if status == "attended" else 0
    attended_at = now_iso() if status == "attended" else None

    existing = conn.execute(
        "SELECT id FROM event_attendance WHERE event_id = ? AND user_id = ?",
        (event_id, user_id),
    ).fetchone()
    if existing:
        conn.execute(
            "UPDATE event_attendance SET status = ?, attended_at = ?, duration_minutes = ? WHERE id = ?",
            (status, attended_at, duration_minutes, existing["id"]),
        )
    else:
        conn.execute(
            "INSERT INTO event_attendance (event_id, user_id, status, attended_at, duration_minutes) VALUES (?, ?, ?, ?, ?)",
            (event_id, user_id, status, attended_at, duration_minutes),
        )

    if status == "attended":
        conn.execute(
            "INSERT INTO volunteer_activity (user_id, event_id, minutes, created_at) VALUES (?, ?, ?, ?)",
            (user_id, event_id, duration_minutes, now_iso()),
        )

    log_audit(
        conn,
        "mark_event_attendance",
        "event",
        event_id,
        me["id"],
        {"user_id": user_id, "status": status},
    )
    conn.commit()
    conn.close()
    return success_response(
        {
            "event_id": event_id,
            "user_id": user_id,
            "status": status,
            "duration_minutes": duration_minutes,
        }
    )
