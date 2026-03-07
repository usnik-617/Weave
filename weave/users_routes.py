import sqlite3
from datetime import datetime

from weave import core as weave_core
from weave import error_messages
from weave import user_activity_service, user_profile_service, user_role_request_service
from weave import user_role_request_command_service
from weave import user_export_service
from weave.authz import get_current_user_row, normalize_role, role_at_least
from weave.core import (
    Response,
    get_db_connection,
    log_audit,
    record_user_activity,
    request,
    session,
    transaction,
)
from weave.responses import (
    error_response,
    success_response,
    user_row_to_dict,
)
from weave.time_utils import now_iso
from weave.validators import validate_nickname


def delete_my_account():
    conn = get_db_connection()
    me = get_current_user_row(conn)
    if not me:
        conn.close()
        return error_response(error_messages.UNAUTHORIZED, 401)

    deleted_at = now_iso()
    anonymized = f"deleted-{me['id']}-{int(datetime.now().timestamp())}"
    conn.execute(
        """
        UPDATE users
        SET status = 'deleted',
            deleted_at = ?,
            name = '삭제회원',
            email = ?,
            phone = '000-0000-0000',
            username = ?
        WHERE id = ?
        """,
        (deleted_at, f"{anonymized}@deleted.local", anonymized, me["id"]),
    )
    conn.commit()
    conn.close()
    session.pop("user_id", None)
    log_audit(me["id"], "delete_account", "user", me["id"])
    return success_response({"ok": True, "message": "계정이 삭제 처리되었습니다."})


def my_activity_history():
    conn = get_db_connection()
    me = get_current_user_row(conn)
    if not me:
        conn.close()
        return error_response(error_messages.USER_LOGIN_REQUIRED, 401)
    rows = conn.execute(
        """
        SELECT a.id AS activity_id, a.title, a.start_at, a.end_at, a.place,
               ap.status, ap.attendance_status, ap.hours, ap.points, ap.penalty_points
        FROM activity_applications ap
        JOIN activities a ON a.id = ap.activity_id
        WHERE ap.user_id = ?
        ORDER BY a.start_at DESC
        """,
        (me["id"],),
    ).fetchall()

    conn.close()
    return success_response(user_activity_service.build_my_activity_history_response(rows))


def my_certificate_csv():
    conn = get_db_connection()
    me = get_current_user_row(conn)
    if not me:
        conn.close()
        return error_response(error_messages.USER_LOGIN_REQUIRED, 401)
    rows = conn.execute(
        """
        SELECT a.title, a.start_at, a.end_at, a.place, ap.hours, ap.attendance_status
        FROM activity_applications ap
        JOIN activities a ON a.id = ap.activity_id
        WHERE ap.user_id = ?
        ORDER BY a.start_at ASC
        """,
        (me["id"],),
    ).fetchall()
    conn.close()

    csv_text = user_export_service.build_certificate_csv_text(me, rows)
    response = Response(csv_text, mimetype="text/csv; charset=utf-8")
    response.headers["Content-Disposition"] = (
        "attachment; filename=my_activity_certificate.csv"
    )
    return response


def user_profile():
    conn = get_db_connection()
    row = get_current_user_row(conn)
    if not row:
        conn.close()
        return success_response({"user": None})
    data = user_profile_service.get_user_profile_payload(conn, row, user_row_to_dict)
    conn.close()
    return success_response(data)


def update_my_nickname():
    payload = request.get_json(silent=True) or {}
    nickname = str(payload.get("nickname", "")).strip()
    valid, message = validate_nickname(nickname)
    if not valid:
        return error_response(message, 400)

    conn = get_db_connection()
    me = get_current_user_row(conn)
    if not me:
        conn.close()
        return error_response(error_messages.UNAUTHORIZED, 401)

    updated, err = weave_core._update_nickname_common(
        conn, me, nickname, bypass_window=False
    )
    if err:
        conn.close()
        return err
    log_audit(
        conn, "change_nickname", "user", me["id"], me["id"], {"nickname": nickname}
    )
    record_user_activity(
        conn, me["id"], "nickname_change", "user", me["id"], {"nickname": nickname}
    )
    try:
        conn.commit()
    except sqlite3.IntegrityError:
        conn.close()
        return error_response("이미 사용 중인 닉네임입니다.", 409)
    conn.close()
    return success_response(
        {"message": "닉네임이 변경되었습니다.", "user": user_row_to_dict(updated)}
    )


def list_my_activity():
    conn = get_db_connection()
    me = get_current_user_row(conn)
    if not me:
        conn.close()
        return error_response(error_messages.UNAUTHORIZED, 401)
    rows = conn.execute(
        """
        SELECT activity_type, target_type, target_id, metadata_json, created_at
        FROM user_activity
        WHERE user_id = ?
        ORDER BY id DESC
        LIMIT 50
        """,
        (me["id"],),
    ).fetchall()
    conn.close()
    return success_response(user_activity_service.build_list_my_activity_items(rows))


def admin_update_user_nickname(user_id):
    payload = request.get_json(silent=True) or {}
    nickname = str(payload.get("nickname", "")).strip()
    valid, message = validate_nickname(nickname)
    if not valid:
        return error_response(message, 400)

    conn = get_db_connection()
    me = get_current_user_row(conn)
    if not me:
        conn.close()
        return error_response(error_messages.UNAUTHORIZED, 401)
    if not role_at_least(me["role"], "VICE_LEADER"):
        conn.close()
        return error_response(error_messages.ROLE_REQUEST_VICE_LEADER_REQUIRED, 403)
    target = conn.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()
    if not target:
        conn.close()
        return error_response("사용자를 찾을 수 없습니다.", 404)

    updated, err = weave_core._update_nickname_common(
        conn, target, nickname, bypass_window=True
    )
    if err:
        conn.close()
        return err
    log_audit(
        conn, "admin_change_nickname", "user", user_id, me["id"], {"nickname": nickname}
    )
    try:
        conn.commit()
    except sqlite3.IntegrityError:
        conn.close()
        return error_response("이미 사용 중인 닉네임입니다.", 409)
    conn.close()
    return success_response(
        {"message": "닉네임이 변경되었습니다.", "user": user_row_to_dict(updated)}
    )


def update_user_nickname_legacy():
    return update_my_nickname()


def request_role_change():
    payload = request.get_json(silent=True) or {}
    target = normalize_role(payload.get("to_role", ""))
    return request_role_change_internal(target)


def request_member_role():
    request.get_json(silent=True)
    conn = get_db_connection()
    me = get_current_user_row(conn)
    if not me:
        conn.close()
        return error_response(error_messages.UNAUTHORIZED, 401)
    conn.close()
    if normalize_role(me["role"]) != "GENERAL":
        return error_response("일반 회원만 단원 승격을 요청할 수 있습니다.", 400)
    return request_role_change_internal("MEMBER")


def request_executive_role():
    request.get_json(silent=True)
    conn = get_db_connection()
    me = get_current_user_row(conn)
    if not me:
        conn.close()
        return error_response(error_messages.UNAUTHORIZED, 401)
    conn.close()
    if normalize_role(me["role"]) != "MEMBER":
        return error_response("단원만 임원 승격을 요청할 수 있습니다.", 400)
    return request_role_change_internal("EXECUTIVE")


def request_role_change_internal(target):
    conn = get_db_connection()
    me = get_current_user_row(conn)
    if not me:
        conn.close()
        return error_response(error_messages.UNAUTHORIZED, 401)

    current = normalize_role(me["role"])
    target = normalize_role(target)
    if not user_role_request_service.validate_transition(current, target):
        conn.close()
        return error_response(error_messages.ROLE_REQUEST_INVALID_TRANSITION, 400)

    pending = conn.execute(
        "SELECT id FROM role_requests WHERE user_id = ? AND status = 'PENDING'",
        (me["id"],),
    ).fetchone()
    if pending:
        conn.close()
        return error_response(error_messages.ROLE_REQUEST_PENDING_EXISTS, 409)
    try:
        with transaction(conn):
            cur = conn.cursor()
            cur.execute(
                """
                INSERT INTO role_requests (user_id, from_role, to_role, status, created_at)
                VALUES (?, ?, ?, 'PENDING', ?)
                """,
                (me["id"], current, target, now_iso()),
            )
            request_id = cur.lastrowid
            log_audit(
                conn,
                "request_role_change",
                "role_request",
                request_id,
                me["id"],
                {"from": current, "to": target},
            )
        return success_response({"request_id": request_id}, 201)
    except Exception:
        return error_response("역할 요청 처리 중 오류가 발생했습니다.", 500)
    finally:
        conn.close()


def list_role_requests():
    status = str(request.args.get("status", "PENDING")).strip().upper()
    page = max(1, int(request.args.get("page", "1") or 1))
    page_size = min(100, max(1, int(request.args.get("pageSize", "20") or 20)))
    offset = (page - 1) * page_size

    conn = get_db_connection()
    me = get_current_user_row(conn)
    if not me:
        conn.close()
        return error_response(error_messages.UNAUTHORIZED, 401)
    if not role_at_least(me["role"], "VICE_LEADER"):
        conn.close()
        return error_response(error_messages.ROLE_REQUEST_VICE_LEADER_REQUIRED, 403)
    total = conn.execute(
        "SELECT COUNT(*) AS c FROM role_requests WHERE status = ?", (status,)
    ).fetchone()["c"]
    rows = conn.execute(
        """
        SELECT rr.*, u.username, u.nickname
        FROM role_requests rr
        JOIN users u ON u.id = rr.user_id
        WHERE rr.status = ?
        ORDER BY rr.id DESC
        LIMIT ? OFFSET ?
        """,
        (status, page_size, offset),
    ).fetchall()
    conn.close()
    return success_response(
        user_role_request_service.role_requests_page_data(total, rows, page, page_size)
    )


def _decide_role_request(request_id, approve=True):
    conn = get_db_connection()
    me = get_current_user_row(conn)
    if not me:
        conn.close()
        return error_response(error_messages.UNAUTHORIZED, 401)
    if not role_at_least(me["role"], "VICE_LEADER"):
        conn.close()
        return error_response(error_messages.ROLE_REQUEST_VICE_LEADER_REQUIRED, 403)
    try:
        with transaction(conn):
            next_status, err = user_role_request_command_service.decide_role_request(
                conn,
                request_id,
                me,
                approve,
                now_iso,
                log_audit,
            )
            if err == "not_found":
                return error_response(error_messages.ROLE_REQUEST_NOT_FOUND, 404)
            if err == "already_decided":
                return error_response(error_messages.ROLE_REQUEST_ALREADY_DECIDED, 409)
        return success_response({"request_id": request_id, "status": next_status})
    except Exception:
        return error_response("요청 처리 저장 중 오류가 발생했습니다.", 500)
    finally:
        conn.close()


def approve_role_request(request_id):
    return _decide_role_request(request_id, True)


def deny_role_request(request_id):
    return _decide_role_request(request_id, False)


def list_role_requests_legacy():
    return list_role_requests()


def approve_role_request_legacy(request_id):
    return _decide_role_request(request_id, True)


def reject_role_request_legacy(request_id):
    return _decide_role_request(request_id, False)

