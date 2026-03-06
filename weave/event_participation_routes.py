from weave.authz import (
    can_join_event,
    can_view_event_details,
    get_current_user_row,
    normalize_role,
)
from weave.core import (
    get_db_connection,
    invalidate_cache,
    jsonify,
    log_audit,
    record_user_activity,
    request,
)
from weave.responses import error_response, success_response, success_response_legacy
from weave.time_utils import now_iso


def list_event_participants(event_id):
    conn = get_db_connection()
    me = get_current_user_row(conn)
    if not me:
        conn.close()
        return error_response("Unauthorized", 401)
    if not can_view_event_details(me):
        conn.close()
        return error_response("단원 이상만 참여자 목록을 확인할 수 있습니다.", 403)
    event = conn.execute("SELECT id FROM events WHERE id = ?", (event_id,)).fetchone()
    if not event:
        conn.close()
        return error_response("이벤트를 찾을 수 없습니다.", 404)
    rows = conn.execute(
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
    return success_response(
        {
            "items": [
                {
                    "userId": row["user_id"],
                    "status": row["status"],
                    "joinedAt": row["created_at"],
                    "nickname": row["nickname"] or row["username"],
                    "role": normalize_role(row["role"]),
                }
                for row in rows
            ]
        }
    )


def join_event(event_id):
    conn = get_db_connection()
    me = get_current_user_row(conn)
    if not me:
        conn.close()
        return error_response("Unauthorized", 401)
    if not can_join_event(me):
        conn.close()
        return error_response("단원 이상만 참여 신청할 수 있습니다.", 403)
    event = conn.execute("SELECT * FROM events WHERE id = ?", (event_id,)).fetchone()
    if not event:
        conn.close()
        return error_response("이벤트를 찾을 수 없습니다.", 404)

    active_count = conn.execute(
        "SELECT COUNT(*) AS c FROM event_participants WHERE event_id = ? AND status = 'registered'",
        (event_id,),
    ).fetchone()["c"]
    limit_count = int(event["capacity"] or event["max_participants"] or 0)
    if limit_count > 0 and active_count >= limit_count:
        conn.close()
        return error_response("모집 정원이 마감되었습니다.", 409)

    existing = conn.execute(
        "SELECT * FROM event_participants WHERE event_id = ? AND user_id = ?",
        (event_id, me["id"]),
    ).fetchone()

    if existing:
        conn.execute(
            "UPDATE event_participants SET status = 'registered', updated_at = ? WHERE id = ?",
            (now_iso(), existing["id"]),
        )
    else:
        conn.execute(
            "INSERT INTO event_participants (event_id, user_id, status, created_at, updated_at) VALUES (?, ?, 'registered', ?, ?)",
            (event_id, me["id"], now_iso(), now_iso()),
        )

    log_audit(conn, "join_event", "event", event_id, me["id"])
    record_user_activity(conn, me["id"], "event_join", "event", event_id)
    conn.commit()
    conn.close()
    invalidate_cache("events:list:")
    return success_response({"event_id": event_id, "status": "registered"})


def cancel_event_participation(event_id):
    conn = get_db_connection()
    me = get_current_user_row(conn)
    if not me:
        conn.close()
        return error_response("Unauthorized", 401)
    if not can_join_event(me):
        conn.close()
        return error_response("단원 이상만 참여 취소할 수 있습니다.", 403)
    existing = conn.execute(
        "SELECT * FROM event_participants WHERE event_id = ? AND user_id = ?",
        (event_id, me["id"]),
    ).fetchone()
    if not existing:
        conn.close()
        return error_response("참가 신청 이력이 없습니다.", 404)

    conn.execute(
        "UPDATE event_participants SET status = 'cancelled', updated_at = ? WHERE id = ?",
        (now_iso(), existing["id"]),
    )
    log_audit(conn, "cancel_event", "event", event_id, me["id"])
    record_user_activity(conn, me["id"], "event_cancel", "event", event_id)
    conn.commit()
    conn.close()
    invalidate_cache("events:list:")
    return success_response({"event_id": event_id, "status": "cancelled"})


def apply_activity(activity_id):
    conn = get_db_connection()
    me = get_current_user_row(conn)
    if not me:
        conn.close()
        return jsonify({"ok": False, "message": "로그인이 필요합니다."}), 401
    activity = conn.execute(
        "SELECT * FROM activities WHERE id = ?", (activity_id,)
    ).fetchone()
    if not activity:
        conn.close()
        return jsonify({"ok": False, "message": "활동을 찾을 수 없습니다."}), 404

    existing = conn.execute(
        "SELECT * FROM activity_applications WHERE activity_id = ? AND user_id = ?",
        (activity_id, me["id"]),
    ).fetchone()

    if existing and existing["status"] not in ("cancelled", "noshow"):
        conn.close()
        return jsonify({"ok": False, "message": "이미 신청한 활동입니다."}), 409

    confirmed_count = conn.execute(
        "SELECT COUNT(*) AS count FROM activity_applications WHERE activity_id = ? AND status = 'confirmed'",
        (activity_id,),
    ).fetchone()["count"]

    limit_count = int(activity["recruitment_limit"] or 0)
    next_status = (
        "confirmed" if limit_count <= 0 or confirmed_count < limit_count else "waiting"
    )

    if existing:
        conn.execute(
            """
            UPDATE activity_applications
            SET status = ?, attendance_status = 'pending', attendance_method = '',
                updated_at = ?, hours = 0, points = 0, penalty_points = 0
            WHERE id = ?
            """,
            (next_status, now_iso(), existing["id"]),
        )
    else:
        conn.execute(
            """
            INSERT INTO activity_applications (
                activity_id, user_id, status, attendance_status, attendance_method,
                hours, points, penalty_points, applied_at, updated_at
            )
            VALUES (?, ?, ?, 'pending', '', 0, 0, 0, ?, ?)
            """,
            (activity_id, me["id"], next_status, now_iso(), now_iso()),
        )
    conn.commit()
    conn.close()
    return success_response_legacy({"ok": True, "status": next_status})


def cancel_activity(activity_id):
    conn = get_db_connection()
    me = get_current_user_row(conn)
    if not me:
        conn.close()
        return jsonify({"ok": False, "message": "로그인이 필요합니다."}), 401
    target = conn.execute(
        "SELECT * FROM activity_applications WHERE activity_id = ? AND user_id = ?",
        (activity_id, me["id"]),
    ).fetchone()
    if not target:
        conn.close()
        return jsonify({"ok": False, "message": "신청 내역이 없습니다."}), 404

    conn.execute(
        "UPDATE activity_applications SET status = 'cancelled', updated_at = ? WHERE id = ?",
        (now_iso(), target["id"]),
    )
    conn.commit()
    conn.close()
    return success_response_legacy({"ok": True, "message": "신청이 취소되었습니다."})
