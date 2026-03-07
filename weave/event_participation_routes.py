from weave.authz import (
    can_join_event,
    can_view_event_details,
    get_current_user_row,
    normalize_role,
)
from weave import cache_keys, error_messages
from weave import event_participation_command_service, event_participation_policy
from weave.core import (
    get_db_connection,
    invalidate_cache,
    log_audit,
    record_user_activity,
    transaction,
)
from weave.responses import error_response, success_response
from weave.time_utils import now_iso


def _ensure_active_account(user):
    if event_participation_policy.is_account_blocked(user):
        return error_response(error_messages.EVENT_ACCOUNT_STATUS_FORBIDDEN, 403)
    return None


def list_event_participants(event_id):
    conn = get_db_connection()
    me = get_current_user_row(conn)
    if not me:
        conn.close()
        return error_response(error_messages.UNAUTHORIZED, 401)
    if not can_view_event_details(me):
        conn.close()
        return error_response(error_messages.EVENT_PARTICIPANTS_VIEW_FORBIDDEN, 403)
    event = conn.execute("SELECT id FROM events WHERE id = ?", (event_id,)).fetchone()
    if not event:
        conn.close()
        return error_response(error_messages.EVENT_NOT_FOUND, 404)
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
        return error_response(error_messages.UNAUTHORIZED, 401)
    if not can_join_event(me):
        conn.close()
        return error_response(error_messages.EVENT_JOIN_FORBIDDEN, 403)
    blocked = _ensure_active_account(me)
    if blocked:
        conn.close()
        return blocked
    event = conn.execute("SELECT * FROM events WHERE id = ?", (event_id,)).fetchone()
    if not event:
        conn.close()
        return error_response(error_messages.EVENT_NOT_FOUND, 404)

    active_count = conn.execute(
        "SELECT COUNT(*) AS c FROM event_participants WHERE event_id = ? AND status = 'registered'",
        (event_id,),
    ).fetchone()["c"]
    limit_count = int(event["capacity"] or event["max_participants"] or 0)
    if event_participation_policy.event_capacity_reached(limit_count, active_count):
        conn.close()
        return error_response(error_messages.EVENT_CAPACITY_FULL, 409)

    try:
        with transaction(conn):
            event_participation_command_service.upsert_event_participation(
                conn,
                event_id,
                me["id"],
                now_iso,
            )
            log_audit(conn, "join_event", "event", event_id, me["id"])
            record_user_activity(conn, me["id"], "event_join", "event", event_id)
    finally:
        conn.close()
    invalidate_cache(cache_keys.EVENTS_LIST_PREFIX)
    return success_response({"event_id": event_id, "status": "registered"})


def cancel_event_participation(event_id):
    conn = get_db_connection()
    me = get_current_user_row(conn)
    if not me:
        conn.close()
        return error_response(error_messages.UNAUTHORIZED, 401)
    if not can_join_event(me):
        conn.close()
        return error_response(error_messages.EVENT_CANCEL_FORBIDDEN, 403)
    blocked = _ensure_active_account(me)
    if blocked:
        conn.close()
        return blocked
    existing = conn.execute(
        "SELECT * FROM event_participants WHERE event_id = ? AND user_id = ?",
        (event_id, me["id"]),
    ).fetchone()
    if not existing:
        conn.close()
        return error_response(error_messages.EVENT_NO_PARTICIPATION_HISTORY, 404)

    try:
        with transaction(conn):
            event_participation_command_service.cancel_event_participation(
                conn,
                existing["id"],
                now_iso,
            )
            log_audit(conn, "cancel_event", "event", event_id, me["id"])
            record_user_activity(conn, me["id"], "event_cancel", "event", event_id)
    finally:
        conn.close()
    invalidate_cache(cache_keys.EVENTS_LIST_PREFIX)
    return success_response({"event_id": event_id, "status": "cancelled"})


def apply_activity(activity_id):
    conn = get_db_connection()
    me = get_current_user_row(conn)
    if not me:
        conn.close()
        return error_response(error_messages.UNAUTHORIZED, 401)
    blocked = _ensure_active_account(me)
    if blocked:
        conn.close()
        return blocked
    activity = conn.execute(
        "SELECT * FROM activities WHERE id = ?", (activity_id,)
    ).fetchone()
    if not activity:
        conn.close()
        return error_response(error_messages.EVENT_ACTIVITY_NOT_FOUND, 404)

    existing = conn.execute(
        "SELECT * FROM activity_applications WHERE activity_id = ? AND user_id = ?",
        (activity_id, me["id"]),
    ).fetchone()

    if not event_participation_policy.can_reapply_activity(existing):
        conn.close()
        return error_response(error_messages.EVENT_ALREADY_APPLIED, 409)

    confirmed_count = conn.execute(
        "SELECT COUNT(*) AS count FROM activity_applications WHERE activity_id = ? AND status = 'confirmed'",
        (activity_id,),
    ).fetchone()["count"]

    limit_count = int(activity["recruitment_limit"] or 0)
    next_status = event_participation_policy.next_activity_status(
        limit_count,
        confirmed_count,
    )

    try:
        with transaction(conn):
            event_participation_command_service.upsert_activity_application(
                conn,
                activity_id,
                me["id"],
                next_status,
                existing,
                now_iso,
            )
    finally:
        conn.close()
    return success_response({"status": next_status})


def cancel_activity(activity_id):
    conn = get_db_connection()
    me = get_current_user_row(conn)
    if not me:
        conn.close()
        return error_response(error_messages.UNAUTHORIZED, 401)
    blocked = _ensure_active_account(me)
    if blocked:
        conn.close()
        return blocked
    target = conn.execute(
        "SELECT * FROM activity_applications WHERE activity_id = ? AND user_id = ?",
        (activity_id, me["id"]),
    ).fetchone()
    if not target:
        conn.close()
        return error_response(error_messages.EVENT_NO_ACTIVITY_APPLICATION, 404)

    try:
        with transaction(conn):
            event_participation_command_service.cancel_activity_application(
                conn,
                target["id"],
                now_iso,
            )
    finally:
        conn.close()
    return success_response(
        {"status": "cancelled", "message": error_messages.EVENT_ACTIVITY_CANCELLED}
    )
