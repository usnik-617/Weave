from weave.authz import (
    can_join_event,
    can_view_event_details,
    get_current_user_row,
    normalize_role,
)
from weave.core import (
    get_db_connection,
    invalidate_cache,
    log_audit,
    record_user_activity,
)
from weave.responses import error_response, success_response
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
