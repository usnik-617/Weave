import os
import uuid
from datetime import datetime, timedelta

from weave.authz import get_current_user_row, role_at_least
from weave.core import (
    calculate_activity_hours,
    csv_response,
    get_db_connection,
    jsonify,
    log_audit,
    request,
)
from weave.responses import error_response, success_response
from weave.time_utils import now_iso, parse_iso_datetime


def _ensure_active_account(user):
    if user and user["status"] in ("suspended", "deleted"):
        return error_response("계정 상태로 인해 요청을 처리할 수 없습니다.", 403)
    return None


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
        return error_response("Unauthorized", 401)
    blocked = _ensure_active_account(me)
    if blocked:
        conn.close()
        return blocked
    activity = conn.execute(
        "SELECT id FROM activities WHERE id = ?", (activity_id,)
    ).fetchone()
    if not activity:
        conn.close()
        return error_response("활동을 찾을 수 없습니다.", 404)

    token = uuid.uuid4().hex
    expires = (datetime.now() + timedelta(hours=2)).isoformat()
    conn.execute(
        "INSERT INTO attendance_qr_tokens (activity_id, token, expires_at, created_by, created_at) VALUES (?, ?, ?, ?, ?)",
        (activity_id, token, expires, me["id"], now_iso()),
    )
    conn.commit()
    conn.close()
    return success_response({"token": token, "expiresAt": expires})


def qr_check_attendance(activity_id):
    payload = request.get_json(silent=True) or {}
    token = str(payload.get("token", "")).strip()
    if not token:
        return error_response("토큰이 필요합니다.", 400)

    conn = get_db_connection()
    me = get_current_user_row(conn)
    if not me:
        conn.close()
        return error_response("Unauthorized", 401)
    blocked = _ensure_active_account(me)
    if blocked:
        conn.close()
        return blocked
    qr = conn.execute(
        "SELECT * FROM attendance_qr_tokens WHERE activity_id = ? AND token = ?",
        (activity_id, token),
    ).fetchone()
    if not qr:
        conn.close()
        return error_response("유효하지 않은 토큰입니다.", 404)

    expires = parse_iso_datetime(qr["expires_at"])
    if not expires or expires < datetime.now():
        conn.close()
        return error_response("만료된 토큰입니다.", 410)

    app_row = conn.execute(
        "SELECT * FROM activity_applications WHERE activity_id = ? AND user_id = ?",
        (activity_id, me["id"]),
    ).fetchone()
    if not app_row:
        conn.close()
        return error_response("신청 내역이 없습니다.", 404)

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
    return success_response({"hours": hours, "points": points})


def bulk_attendance(activity_id):
    payload = request.get_json(silent=True) or {}
    entries = payload.get("entries", [])
    if not isinstance(entries, list) or not entries:
        return error_response("entries 배열이 필요합니다.", 400)

    conn = get_db_connection()
    me = get_current_user_row(conn)
    if not me:
        conn.close()
        return error_response("Unauthorized", 401)
    blocked = _ensure_active_account(me)
    if blocked:
        conn.close()
        return blocked
    if not role_at_least(me["role"], "VICE_LEADER"):
        conn.close()
        return error_response("부단장 이상만 출결 일괄처리를 할 수 있습니다.", 403)
    activity = conn.execute(
        "SELECT * FROM activities WHERE id = ?", (activity_id,)
    ).fetchone()
    if not activity:
        conn.close()
        return error_response("활동을 찾을 수 없습니다.", 404)

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
    return success_response({"updated": updated})


def admin_dashboard():
    conn = get_db_connection()
    me = get_current_user_row(conn)
    if not me:
        conn.close()
        return error_response("Unauthorized", 401)
    if not role_at_least(me["role"], "VICE_LEADER"):
        conn.close()
        return error_response("부단장 이상만 접근할 수 있습니다.", 403)

    today = datetime.now().date().isoformat()
    month_prefix = datetime.now().strftime("%Y-%m")
    today_schedule = conn.execute(
        "SELECT COUNT(*) AS c FROM activities WHERE date(start_at) = ?", (today,)
    ).fetchone()["c"]
    pending_users = conn.execute(
        "SELECT COUNT(*) AS c FROM users WHERE status = 'pending'"
    ).fetchone()["c"]
    waiting_apps = conn.execute(
        "SELECT COUNT(*) AS c FROM activity_applications WHERE status = 'waiting'"
    ).fetchone()["c"]
    noshows = conn.execute(
        "SELECT COUNT(*) AS c FROM activity_applications WHERE attendance_status = 'noshow'"
    ).fetchone()["c"]
    scheduled_notices = conn.execute(
        "SELECT COUNT(*) AS c FROM scheduled_notices WHERE status = 'pending'"
    ).fetchone()["c"]
    qna_unanswered = conn.execute(
        "SELECT COUNT(*) AS c FROM qna_posts WHERE TRIM(COALESCE(answer,'')) = ''"
    ).fetchone()["c"]
    expense_alerts = conn.execute(
        "SELECT COUNT(*) AS c FROM expenses WHERE settled = 0 AND substr(due_date,1,7) = ?",
        (month_prefix,),
    ).fetchone()["c"]
    conn.close()

    return jsonify(
        {
            "ok": True,
            "dashboard": {
                "todaySchedule": int(today_schedule or 0),
                "pendingApprovals": int(pending_users or 0),
                "waitingApplications": int(waiting_apps or 0),
                "noshowCount": int(noshows or 0),
                "scheduledNotices": int(scheduled_notices or 0),
                "qnaUnanswered": int(qna_unanswered or 0),
                "expenseAlerts": int(expense_alerts or 0),
            },
        }
    )


def export_participants_csv():
    conn = get_db_connection()
    me = get_current_user_row(conn)
    if not me:
        conn.close()
        return error_response("Unauthorized", 401)
    if not role_at_least(me["role"], "VICE_LEADER"):
        conn.close()
        return error_response("부단장 이상만 접근할 수 있습니다.", 403)
    rows = conn.execute(
        "SELECT id, name, username, email, phone, role, status, generation FROM users ORDER BY id ASC"
    ).fetchall()
    conn.close()
    return csv_response(
        "participants.csv",
        ["id", "name", "username", "email", "phone", "role", "status", "generation"],
        [
            [
                row["id"],
                row["name"],
                row["username"],
                row["email"],
                row["phone"],
                row["role"],
                row["status"],
                row["generation"],
            ]
            for row in rows
        ],
    )


def export_attendance_csv():
    conn = get_db_connection()
    me = get_current_user_row(conn)
    if not me:
        conn.close()
        return error_response("Unauthorized", 401)
    if not role_at_least(me["role"], "VICE_LEADER"):
        conn.close()
        return error_response("부단장 이상만 접근할 수 있습니다.", 403)
    rows = conn.execute(
        """
        SELECT a.title, a.start_at, u.name, u.username, ap.status, ap.attendance_status, ap.hours
        FROM activity_applications ap
        JOIN activities a ON a.id = ap.activity_id
        JOIN users u ON u.id = ap.user_id
        ORDER BY a.start_at DESC, u.username ASC
        """
    ).fetchall()
    conn.close()
    return csv_response(
        "attendance.csv",
        [
            "activity",
            "start_at",
            "name",
            "username",
            "apply_status",
            "attendance_status",
            "hours",
        ],
        [
            [
                row["title"],
                row["start_at"],
                row["name"],
                row["username"],
                row["status"],
                row["attendance_status"],
                row["hours"],
            ]
            for row in rows
        ],
    )


def export_hours_csv():
    conn = get_db_connection()
    me = get_current_user_row(conn)
    if not me:
        conn.close()
        return error_response("Unauthorized", 401)
    if not role_at_least(me["role"], "VICE_LEADER"):
        conn.close()
        return error_response("부단장 이상만 접근할 수 있습니다.", 403)
    rows = conn.execute(
        """
        SELECT u.name, u.username,
               COALESCE(SUM(ap.hours),0) AS total_hours,
               COALESCE(SUM(ap.points),0) AS total_points,
               COALESCE(SUM(ap.penalty_points),0) AS penalty_points
        FROM users u
        LEFT JOIN activity_applications ap ON ap.user_id = u.id
        GROUP BY u.id, u.name, u.username
        ORDER BY total_hours DESC
        """
    ).fetchall()
    conn.close()
    return csv_response(
        "hours_summary.csv",
        ["name", "username", "total_hours", "total_points", "penalty_points"],
        [
            [
                row["name"],
                row["username"],
                row["total_hours"],
                row["total_points"],
                row["penalty_points"],
            ]
            for row in rows
        ],
    )
