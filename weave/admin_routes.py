from datetime import datetime

from weave.authz import get_current_user_row, normalize_role, role_at_least
from weave.core import (
    get_db_connection,
    jsonify,
    log_audit,
    request,
    send_email,
    write_app_log,
)
from weave.responses import (
    error_response,
    success_response,
    success_response_legacy,
    user_row_to_dict,
)
from weave.time_utils import now_iso


def admin_pending_users():
    me = get_current_user_row()
    if not me:
        return error_response("Unauthorized", 401)
    if not role_at_least(me["role"], "VICE_LEADER"):
        return error_response("부단장 이상만 접근할 수 있습니다.", 403)

    page = int(request.args.get("page", "1") or 1)
    page_size = int(request.args.get("pageSize", "10") or 10)
    sort_by = str(request.args.get("sortBy", "id") or "id").strip().lower()
    sort_dir = str(request.args.get("sortDir", "desc") or "desc").strip().lower()
    keyword = str(request.args.get("q", "") or "").strip()
    page = max(page, 1)
    page_size = min(max(page_size, 1), 100)
    offset = (page - 1) * page_size
    sort_map = {
        "id": "id",
        "name": "name",
        "username": "username",
        "generation": "generation",
        "interests": "interests",
        "status": "status",
    }
    sort_column = sort_map.get(sort_by, "id")
    sort_direction = "ASC" if sort_dir == "asc" else "DESC"

    where_sql = "WHERE status = 'pending'"
    query_params = []
    if keyword:
        where_sql += " AND (name LIKE ? OR username LIKE ? OR IFNULL(generation, '') LIKE ? OR IFNULL(interests, '') LIKE ? OR IFNULL(status, '') LIKE ?)"
        wildcard = f"%{keyword}%"
        query_params.extend([wildcard, wildcard, wildcard, wildcard, wildcard])

    conn = get_db_connection()
    total = conn.execute(
        f"SELECT COUNT(*) AS c FROM users {where_sql}",
        tuple(query_params),
    ).fetchone()["c"]
    rows = conn.execute(
        f"SELECT * FROM users {where_sql} ORDER BY {sort_column} {sort_direction}, id DESC LIMIT ? OFFSET ?",
        tuple([*query_params, page_size, offset]),
    ).fetchall()
    conn.close()
    total_pages = max((int(total or 0) + page_size - 1) // page_size, 1)
    return jsonify(
        {
            "ok": True,
            "items": [user_row_to_dict(row) for row in rows],
            "pagination": {
                "total": int(total or 0),
                "page": page,
                "pageSize": page_size,
                "totalPages": total_pages,
                "hasPrev": page > 1,
                "hasNext": page < total_pages,
                "sortBy": sort_column,
                "sortDir": sort_direction.lower(),
                "q": keyword,
            },
        }
    )


def admin_approve_user(user_id):
    payload = request.get_json(silent=True) or {}
    role = normalize_role(payload.get("role", "MEMBER"))
    if role not in ("GENERAL", "MEMBER", "EXECUTIVE", "VICE_LEADER", "LEADER", "ADMIN"):
        return error_response("유효하지 않은 역할입니다.", 400)

    conn = get_db_connection()
    target = conn.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()
    if not target:
        conn.close()
        return error_response("대상을 찾을 수 없습니다.", 404)

    me = get_current_user_row(conn)
    if not me:
        conn.close()
        return error_response("Unauthorized", 401)
    if not role_at_least(me["role"], "VICE_LEADER"):
        conn.close()
        return error_response("부단장 이상만 접근할 수 있습니다.", 403)
    if role == "ADMIN" and not role_at_least(me["role"], "ADMIN"):
        conn.close()
        return error_response("관리자 승격 권한이 없습니다.", 403)

    conn.execute(
        "UPDATE users SET status = 'active', role = ?, is_admin = CASE WHEN ? = 'ADMIN' THEN 1 ELSE is_admin END, approved_at = ?, approved_by = ? WHERE id = ?",
        (role, role, now_iso(), me["id"], user_id),
    )
    audit_action = (
        "approve_member"
        if role == "MEMBER"
        else ("approve_executive" if role == "EXECUTIVE" else "role_change")
    )
    log_audit(me["id"], audit_action, "user", user_id, {"role": role})
    if role == "ADMIN":
        log_audit(me["id"], "assign_admin_role", "user", user_id, {"role": role})
    conn.commit()
    row = conn.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()
    if role == "MEMBER":
        send_email(
            row["email"], "[Weave] 단원 승인 안내", "단원 승인이 완료되었습니다."
        )
    elif role == "EXECUTIVE":
        send_email(
            row["email"], "[Weave] 임원 승인 안내", "임원 승인이 완료되었습니다."
        )
    else:
        send_email(
            row["email"],
            "[Weave] 가입 승인 안내",
            f"가입이 승인되었습니다. 현재 권한: {role}",
        )
    conn.close()
    write_app_log(
        "info",
        "admin_approve_user",
        user_id=me["id"],
        extra={"target_user_id": user_id, "role": role},
    )
    payload = {
        "ok": True,
        "message": "가입이 승인되었습니다.",
        "user": user_row_to_dict(row),
    }
    return success_response_legacy(payload)


def admin_reject_user(user_id):
    conn = get_db_connection()
    me = get_current_user_row(conn)
    if not me:
        conn.close()
        return error_response("Unauthorized", 401)
    if not role_at_least(me["role"], "VICE_LEADER"):
        conn.close()
        return error_response("부단장 이상만 접근할 수 있습니다.", 403)
    target = conn.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()
    if not target:
        conn.close()
        return error_response("대상을 찾을 수 없습니다.", 404)

    conn.execute(
        "UPDATE users SET status = 'deleted', deleted_at = ? WHERE id = ?",
        (now_iso(), user_id),
    )
    log_audit(me["id"] if me else None, "delete_user", "user", user_id)
    conn.commit()
    conn.close()
    write_app_log(
        "warning",
        "admin_reject_user",
        user_id=me["id"] if me else None,
        extra={"target_user_id": user_id},
    )
    return success_response({"ok": True, "message": "가입 신청이 반려되었습니다."})


def admin_suspend_user(user_id):
    conn = get_db_connection()
    me = get_current_user_row(conn)
    if not me:
        conn.close()
        return error_response("Unauthorized", 401)
    if not role_at_least(me["role"], "VICE_LEADER"):
        conn.close()
        return error_response("부단장 이상만 접근할 수 있습니다.", 403)
    target = conn.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()
    if not target:
        conn.close()
        return error_response("대상을 찾을 수 없습니다.", 404)
    conn.execute("UPDATE users SET status = 'suspended' WHERE id = ?", (user_id,))
    conn.commit()
    conn.close()
    log_audit(me["id"], "suspend_user", "user", user_id)
    return success_response({"ok": True, "message": "사용자가 정지되었습니다."})


def admin_activate_user(user_id):
    conn = get_db_connection()
    me = get_current_user_row(conn)
    if not me:
        conn.close()
        return error_response("Unauthorized", 401)
    if not role_at_least(me["role"], "VICE_LEADER"):
        conn.close()
        return error_response("부단장 이상만 접근할 수 있습니다.", 403)
    target = conn.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()
    if not target:
        conn.close()
        return error_response("대상을 찾을 수 없습니다.", 404)
    conn.execute("UPDATE users SET status = 'active' WHERE id = ?", (user_id,))
    conn.commit()
    conn.close()
    log_audit(me["id"], "activate_user", "user", user_id)
    return success_response({"ok": True, "message": "사용자가 활성화되었습니다."})


def admin_stats():
    me = get_current_user_row()
    if not me:
        return error_response("Unauthorized", 401)
    if not role_at_least(me["role"], "VICE_LEADER"):
        return error_response("부단장 이상만 접근할 수 있습니다.", 403)

    conn = get_db_connection()
    total_users = conn.execute("SELECT COUNT(*) AS c FROM users").fetchone()["c"]
    total_events = conn.execute("SELECT COUNT(*) AS c FROM events").fetchone()["c"]
    total_participants = conn.execute(
        "SELECT COUNT(*) AS c FROM event_participants WHERE status='registered'"
    ).fetchone()["c"]
    upcoming_events = conn.execute(
        "SELECT COUNT(*) AS c FROM events WHERE event_date >= ?",
        (datetime.now().isoformat(),),
    ).fetchone()["c"]
    recent_signups_rows = conn.execute(
        "SELECT id, username, email, join_date FROM users ORDER BY join_date DESC LIMIT 10"
    ).fetchall()
    conn.close()
    return success_response(
        {
            "total_users": int(total_users or 0),
            "total_events": int(total_events or 0),
            "total_participants": int(total_participants or 0),
            "upcoming_events": int(upcoming_events or 0),
            "recent_signups": [dict(row) for row in recent_signups_rows],
        }
    )


def get_audit_logs():
    me = get_current_user_row()
    if not me:
        return error_response("Unauthorized", 401)
    if not role_at_least(me["role"], "VICE_LEADER"):
        return error_response("부단장 이상만 접근할 수 있습니다.", 403)

    page = max(1, int(request.args.get("page", "1") or 1))
    page_size = min(100, max(1, int(request.args.get("pageSize", "20") or 20)))
    offset = (page - 1) * page_size
    action = str(request.args.get("action", "")).strip()
    target_type = str(request.args.get("target_type", "")).strip()
    actor_user_id = str(
        request.args.get("actor_user_id", request.args.get("user_id", ""))
    ).strip()
    created_from = str(request.args.get("created_from", "")).strip()
    created_to = str(request.args.get("created_to", "")).strip()

    where = ["1=1"]
    params = []
    if action:
        where.append("action = ?")
        params.append(action)
    if target_type:
        where.append("target_type = ?")
        params.append(target_type)
    if actor_user_id:
        where.append("actor_user_id = ?")
        params.append(actor_user_id)
    if created_from:
        where.append("created_at >= ?")
        params.append(created_from)
    if created_to:
        where.append("created_at <= ?")
        params.append(created_to)

    where_sql = " AND ".join(where)
    conn = get_db_connection()
    total = conn.execute(
        f"SELECT COUNT(*) AS c FROM audit_logs WHERE {where_sql}", params
    ).fetchone()["c"]
    rows = conn.execute(
        f"""
        SELECT a.*,
               u.username AS actor_username
        FROM audit_logs a
        LEFT JOIN users u ON u.id = a.actor_user_id
        WHERE {where_sql}
        ORDER BY a.id DESC
        LIMIT ? OFFSET ?
        """,
        [*params, page_size, offset],
    ).fetchall()
    conn.close()

    return success_response(
        {
            "items": [dict(row) for row in rows],
            "pagination": {
                "total": int(total or 0),
                "page": page,
                "pageSize": page_size,
                "totalPages": max(1, (int(total or 0) + page_size - 1) // page_size),
            },
        }
    )
