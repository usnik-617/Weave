import os
import sqlite3
import uuid
from datetime import datetime, timedelta

from werkzeug.security import check_password_hash, generate_password_hash

from weave import auth_command_service, auth_policy, auth_query_service
from weave import error_messages
from weave.authz import get_current_user_row
from weave.core import (
    DB_PATH,
    clear_rate_limit,
    get_db_connection,
    increase_login_failure,
    is_rate_limited,
    log_audit,
    mark_rate_limit_failure,
    request,
    reset_login_failures,
    send_email,
    session,
    touch_user_activity,
    transaction,
    try_unlock_expired_user,
    write_app_log,
)
from weave.responses import (
    error_response,
    success_response,
    user_row_to_dict,
)
from weave.time_utils import now_iso
from weave.validators import (
    normalize_contact,
    validate_nickname,
    validate_password_policy,
    validate_signup_payload,
)


def auth_me():
    row = get_current_user_row()
    if not row:
        return success_response({"user": None, "csrfToken": session.get("csrf_token")})
    data = {"user": user_row_to_dict(row), "csrfToken": session.get("csrf_token")}
    return success_response(data)


def auth_csrf_token():
    token = session.get("csrf_token")
    if not token:
        token = uuid.uuid4().hex
        session["csrf_token"] = token
    return success_response({"csrfToken": token})


def auth_signup():
    payload = request.get_json(silent=True) or {}
    signup_hint = auth_policy.signup_rate_limit_hint(payload)
    blocked, blocked_until = is_rate_limited("signup", signup_hint)
    if blocked:
        blocked_until_text = auth_policy.blocked_until_text(blocked_until, now_iso)
        return error_response(
            error_messages.AUTH_TOO_MANY_REQUESTS,
            429,
            {"blocked_until": blocked_until_text},
        )

    valid, message = validate_signup_payload(payload)
    if not valid:
        mark_rate_limit_failure("signup", signup_hint)
        return error_response(message, 400)

    nickname = str(payload.get("nickname", "")).strip()
    nickname_ok, nickname_message = validate_nickname(nickname)
    if not nickname_ok:
        mark_rate_limit_failure("signup", signup_hint)
        return error_response(nickname_message, 400)

    conn = get_db_connection()
    conflict = auth_query_service.find_signup_conflict(conn, payload, nickname)
    if conflict == "email":
        conn.close()
        return error_response(error_messages.AUTH_EMAIL_EXISTS, 409)
    if conflict == "username":
        conn.close()
        mark_rate_limit_failure("signup", signup_hint)
        return error_response(error_messages.AUTH_USERNAME_EXISTS, 409)
    if conflict == "nickname":
        conn.close()
        mark_rate_limit_failure("signup", signup_hint)
        return error_response(error_messages.AUTH_NICKNAME_EXISTS, 409)

    user_id, create_error = auth_command_service.create_signup_user(conn, payload, nickname)
    if create_error:
        conn.close()
        mark_rate_limit_failure("signup", signup_hint)
        return error_response(error_messages.AUTH_NICKNAME_EXISTS, 409)

    cur = conn.cursor()
    log_audit(conn, "signup", "user", user_id, user_id)
    try:
        conn.commit()
    except sqlite3.IntegrityError:
        conn.close()
        mark_rate_limit_failure("signup", signup_hint)
        return error_response(error_messages.AUTH_NICKNAME_EXISTS, 409)
    row = cur.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()
    conn.close()

    write_app_log("info", "signup", user_id=user_id)
    clear_rate_limit("signup", signup_hint)

    session["user_id"] = user_id
    user_data = user_row_to_dict(row)
    payload = {
        "message": "회원가입이 완료되었습니다.",
        "user": user_data,
    }
    payload["ok"] = True
    return success_response(payload)


def auth_login():
    payload = request.get_json(silent=True) or {}
    username = str(payload.get("username", "")).strip()
    password = str(payload.get("password", ""))

    if not auth_policy.should_bypass_login_rate_limit(request, DB_PATH):
        blocked, blocked_until = is_rate_limited("login", username)
        if blocked:
            blocked_until_text = auth_policy.blocked_until_text(blocked_until, now_iso)
            write_app_log(
                "warning",
                "login_rate_limited",
                extra={"blocked_until": blocked_until_text},
            )
            return error_response(
                error_messages.AUTH_LOGIN_RATE_LIMITED,
                429,
                {"blocked_until": blocked_until_text},
            )

    if not auth_policy.validate_login_payload(username, password):
        return error_response(error_messages.AUTH_CREDENTIALS_REQUIRED, 400)

    conn = get_db_connection()
    row = auth_query_service.get_user_by_username(conn, username)

    if not row:
        conn.close()
        mark_rate_limit_failure("login", username)
        write_app_log(
            "warning", "login_failed_unknown_user", extra={"username": username}
        )
        return error_response(error_messages.AUTH_INVALID_CREDENTIALS, 401)

    try_unlock_expired_user(conn, row)
    row = conn.execute("SELECT * FROM users WHERE id = ?", (row["id"],)).fetchone()

    if row["status"] in ("withdrawn", "deleted"):
        conn.close()
        write_app_log("warning", "login_withdrawn", user_id=row["id"])
        return error_response(error_messages.AUTH_WITHDRAWN, 403)

    if row["status"] == "suspended":
        conn.close()
        write_app_log("warning", "login_suspended", user_id=row["id"])
        return error_response(error_messages.AUTH_SUSPENDED, 403)

    if not check_password_hash(row["password_hash"], password):
        locked, _ = increase_login_failure(conn, row)
        conn.close()
        mark_rate_limit_failure("login", username)
        write_app_log("warning", "login_failed", user_id=row["id"])
        if locked:
            return error_response(error_messages.AUTH_LOCKED_AFTER_FAILURES, 423)
        return error_response(error_messages.AUTH_INVALID_CREDENTIALS, 401)

    reset_login_failures(conn, row["id"])
    row = conn.execute("SELECT * FROM users WHERE id = ?", (row["id"],)).fetchone()
    log_audit(conn, "login", "user", row["id"], row["id"])
    conn.close()
    clear_rate_limit("login", username)
    write_app_log("info", "login_success", user_id=row["id"])

    session["user_id"] = row["id"]
    touch_user_activity(row["id"])
    if row["status"] == "pending":
        payload = {
            "pending": True,
            "message": "가입 승인 대기 중입니다. 승인 후 정식 단원 기능을 사용할 수 있습니다.",
            "user": user_row_to_dict(row),
            "ok": True,
        }
        return success_response(payload)

    payload = {"user": user_row_to_dict(row), "ok": True}
    return success_response(payload)


def auth_logout():
    user_id = session.get("user_id")
    conn = get_db_connection()
    if user_id:
        log_audit(conn, "logout", "user", user_id, user_id)
        write_app_log("info", "logout", user_id=user_id)
    conn.commit()
    conn.close()
    session.pop("user_id", None)
    return success_response({"ok": True})


def auth_find_username():
    payload = request.get_json(silent=True) or {}
    contact = str(payload.get("contact", "")).strip()
    if not contact:
        return error_response(error_messages.AUTH_CONTACT_REQUIRED, 400)

    normalized = contact.replace("-", "").lower()
    conn = get_db_connection()
    row = conn.execute("SELECT username, email, phone, status FROM users").fetchall()
    conn.close()

    for item in row:
        if item["status"] == "withdrawn":
            continue
        email_key = (item["email"] or "").replace("-", "").lower()
        phone_key = (item["phone"] or "").replace("-", "").lower()
        if normalized in (email_key, phone_key):
            return success_response({"username": item["username"], "ok": True})

    return error_response(error_messages.AUTH_ACCOUNT_NOT_FOUND, 404)


def auth_reset_password():
    payload = request.get_json(silent=True) or {}
    username = str(payload.get("username", "")).strip()
    contact = str(payload.get("contact", "")).strip()
    new_password = str(payload.get("newPassword", ""))

    blocked, blocked_until = is_rate_limited("reset-password", username)
    if blocked:
        blocked_until_text = blocked_until.isoformat() if blocked_until else now_iso()
        return error_response(
            error_messages.AUTH_TOO_MANY_REQUESTS,
            429,
            {"blocked_until": blocked_until_text},
        )

    if not username or not contact or not new_password:
        mark_rate_limit_failure("reset-password", username)
        return error_response(error_messages.AUTH_REQUIRED_FIELDS, 400)

    valid_password, password_message = validate_password_policy(new_password)
    if not valid_password:
        mark_rate_limit_failure("reset-password", username)
        return error_response(password_message, 400)

    normalized_contact = contact.replace("-", "").lower()

    conn = get_db_connection()
    row = auth_query_service.get_user_contacts_by_username(conn, username)

    if not row:
        conn.close()
        mark_rate_limit_failure("reset-password", username)
        return error_response(error_messages.AUTH_ACCOUNT_NOT_FOUND, 404)

    email_key = (row["email"] or "").replace("-", "").lower()
    phone_key = (row["phone"] or "").replace("-", "").lower()
    if normalized_contact not in (email_key, phone_key):
        conn.close()
        mark_rate_limit_failure("reset-password", username)
        return error_response(error_messages.AUTH_ACCOUNT_NOT_FOUND, 404)

    with transaction(conn):
        conn.execute(
            "UPDATE users SET password_hash = ?, failed_login_count = 0, locked_until = NULL, status = CASE WHEN status='suspended' THEN COALESCE(CASE WHEN approved_at IS NOT NULL THEN 'active' END, 'pending') ELSE status END WHERE id = ?",
            (generate_password_hash(new_password), row["id"]),
        )
        log_audit(conn, "password_reset", "user", row["id"], row["id"])
    send_email(
        row["email"],
        "[Weave] 비밀번호 재설정 안내",
        "비밀번호가 재설정되었습니다. 본인이 요청하지 않았다면 즉시 운영진에 문의하세요.",
    )
    conn.close()
    clear_rate_limit("reset-password", username)
    write_app_log("info", "password_reset", user_id=row["id"])
    payload = {"ok": True, "message": "비밀번호가 재설정되었습니다."}
    return success_response(payload)


def auth_unlock_account():
    payload = request.get_json(silent=True) or {}
    username = str(payload.get("username", "")).strip()
    contact = normalize_contact(payload.get("contact", ""))

    if not username or not contact:
        return error_response(error_messages.AUTH_UNLOCK_CONTACT_REQUIRED, 400)

    conn = get_db_connection()
    row = auth_query_service.get_user_contacts_by_username(conn, username)
    if not row:
        conn.close()
        return error_response(error_messages.AUTH_ACCOUNT_NOT_FOUND, 404)

    if contact not in (
        normalize_contact(row["email"]),
        normalize_contact(row["phone"]),
    ):
        conn.close()
        return error_response(error_messages.AUTH_UNLOCK_MISMATCH, 403)

    next_status = "active" if row["approved_at"] else "pending"
    with transaction(conn):
        conn.execute(
            "UPDATE users SET status = ?, failed_login_count = 0, locked_until = NULL WHERE id = ?",
            (next_status, row["id"]),
        )
    conn.close()
    return success_response({"ok": True, "message": "계정 잠금이 해제되었습니다."})


def auth_withdraw():
    payload = request.get_json(silent=True) or {}
    contact = normalize_contact(payload.get("contact", ""))
    password = str(payload.get("password", ""))
    reason = str(payload.get("reason", "")).strip()

    conn = get_db_connection()
    me = get_current_user_row(conn)
    if not me:
        conn.close()
        return error_response(error_messages.UNAUTHORIZED, 401)

    if contact not in (normalize_contact(me["email"]), normalize_contact(me["phone"])):
        conn.close()
        return error_response(error_messages.AUTH_CONTACT_VERIFY_REQUIRED, 403)

    if not check_password_hash(me["password_hash"], password):
        conn.close()
        return error_response(error_messages.AUTH_PASSWORD_MISMATCH, 403)

    retention_days = int(os.environ.get("WEAVE_RETENTION_DAYS", "30"))
    retention_until = (datetime.now() + timedelta(days=retention_days)).isoformat()
    deleted_at = now_iso()
    anonymized = f"withdrawn-{me['id']}-{int(datetime.now().timestamp())}"

    with transaction(conn):
        conn.execute(
            """
            UPDATE users
            SET status = 'deleted',
                deleted_at = ?,
                retention_until = ?,
                name = '탈퇴회원',
                email = ?,
                phone = '000-0000-0000',
                username = ?,
                interests = ?,
                certificates = ?,
                availability = ?,
                generation = ?
            WHERE id = ?
            """,
            (
                deleted_at,
                retention_until,
                f"{anonymized}@withdrawn.local",
                anonymized,
                f"탈퇴사유:{reason}" if reason else "탈퇴",
                "",
                "",
                "",
                me["id"],
            ),
        )
        log_audit(conn, "delete_user", "user", me["id"], me["id"])
    conn.close()
    session.pop("user_id", None)
    write_app_log("info", "user_withdraw", user_id=me["id"])
    return success_response(
        {
            "ok": True,
            "message": f"탈퇴 완료. 데이터는 {retention_days}일 보관 후 파기됩니다.",
        }
    )
