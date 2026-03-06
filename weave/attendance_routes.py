import os
import uuid
from datetime import datetime, timedelta

from weave.authz import get_current_user_row, role_at_least
from weave.core import calculate_activity_hours, get_db_connection, jsonify, log_audit, request
from weave.responses import error_response, success_response
from weave.responses import success_response_legacy
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


def create_attendance_qr_token(activity_id):
    conn = get_db_connection()
    me = get_current_user_row(conn)
    if not me:
        conn.close()
        return jsonify({"ok": False, "message": "로그인이 필요합니다."}), 401
    activity = conn.execute(
        "SELECT id FROM activities WHERE id = ?", (activity_id,)
    ).fetchone()
    if not activity:
        conn.close()
        return jsonify({"ok": False, "message": "활동을 찾을 수 없습니다."}), 404

    token = uuid.uuid4().hex
    expires = (datetime.now() + timedelta(hours=2)).isoformat()
    conn.execute(
        "INSERT INTO attendance_qr_tokens (activity_id, token, expires_at, created_by, created_at) VALUES (?, ?, ?, ?, ?)",
        (activity_id, token, expires, me["id"], now_iso()),
    )
    conn.commit()
    conn.close()
    return success_response_legacy({"ok": True, "token": token, "expiresAt": expires})


def qr_check_attendance(activity_id):
    payload = request.get_json(silent=True) or {}
    token = str(payload.get("token", "")).strip()
    if not token:
        return jsonify({"ok": False, "message": "토큰이 필요합니다."}), 400

    conn = get_db_connection()
    me = get_current_user_row(conn)
    if not me:
        conn.close()
        return jsonify({"ok": False, "message": "로그인이 필요합니다."}), 401
    qr = conn.execute(
        "SELECT * FROM attendance_qr_tokens WHERE activity_id = ? AND token = ?",
        (activity_id, token),
    ).fetchone()
    if not qr:
        conn.close()
        return jsonify({"ok": False, "message": "유효하지 않은 토큰입니다."}), 404

    expires = parse_iso_datetime(qr["expires_at"])
    if not expires or expires < datetime.now():
        conn.close()
        return jsonify({"ok": False, "message": "만료된 토큰입니다."}), 410

    app_row = conn.execute(
        "SELECT * FROM activity_applications WHERE activity_id = ? AND user_id = ?",
        (activity_id, me["id"]),
    ).fetchone()
    if not app_row:
        conn.close()
        return jsonify({"ok": False, "message": "신청 내역이 없습니다."}), 404

    activity = conn.execute(
        "SELECT * FROM activities WHERE id = ?", (activity_id,)
    ).fetchone()
    hours = calculate_activity_hours(activity)
    points = int(hours * 10)
    conn.execute(
        """
        UPDATE activity_applications
        SET status = 'confirmed', attendance_status = 'present', attendance_method = 'qr',
            hours = ?, points = ?, penalty_points = 0, updated_at = ?
        WHERE id = ?
        """,
        (hours, points, now_iso(), app_row["id"]),
    )
    conn.commit()
    conn.close()
    return success_response_legacy({"ok": True, "hours": hours, "points": points})


def bulk_attendance(activity_id):
    payload = request.get_json(silent=True) or {}
    entries = payload.get("entries", [])
    if not isinstance(entries, list) or not entries:
        return jsonify({"ok": False, "message": "entries 배열이 필요합니다."}), 400

    conn = get_db_connection()
    me = get_current_user_row(conn)
    if not me:
        conn.close()
        return error_response("Unauthorized", 401)
    if not role_at_least(me["role"], "VICE_LEADER"):
        conn.close()
        return error_response("부단장 이상만 출결 일괄처리를 할 수 있습니다.", 403)
    activity = conn.execute(
        "SELECT * FROM activities WHERE id = ?", (activity_id,)
    ).fetchone()
    if not activity:
        conn.close()
        return jsonify({"ok": False, "message": "활동을 찾을 수 없습니다."}), 404

    hours = calculate_activity_hours(activity)
    points = int(hours * 10)
    no_show_penalty = int(os.environ.get("WEAVE_NOSHOW_PENALTY", "2"))

    updated = 0
    for item in entries:
        user_id = int(item.get("userId", 0) or 0)
        status = str(item.get("status", "pending")).strip().lower()
        if user_id <= 0 or status not in ("present", "absent", "noshow"):
            continue

        app_row = conn.execute(
            "SELECT * FROM activity_applications WHERE activity_id = ? AND user_id = ?",
            (activity_id, user_id),
        ).fetchone()
        if not app_row:
            continue

        final_status = "confirmed" if status == "present" else app_row["status"]
        final_hours = hours if status == "present" else 0
        final_points = points if status == "present" else 0
        penalty = no_show_penalty if status == "noshow" else 0

        conn.execute(
            """
            UPDATE activity_applications
            SET status = ?, attendance_status = ?, attendance_method = 'bulk',
                hours = ?, points = ?, penalty_points = ?, updated_at = ?
            WHERE id = ?
            """,
            (
                final_status,
                status,
                final_hours,
                final_points,
                penalty,
                now_iso(),
                app_row["id"],
            ),
        )
        updated += 1

    conn.commit()
    conn.close()
    return success_response_legacy({"ok": True, "updated": updated})
