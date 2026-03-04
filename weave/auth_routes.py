from weave.core import *


def auth_me():
    row = get_current_user_row()
    if not row:
        return success_response({"user": None})
    data = {"user": user_row_to_dict(row)}
    return jsonify({"success": True, "data": data, "user": data["user"]})


def auth_signup():
    payload = request.get_json(silent=True) or {}
    blocked, blocked_until = is_rate_limited("signup", payload.get("username", ""))
    if blocked:
        blocked_until_text = blocked_until.isoformat() if blocked_until else now_iso()
        return error_response("요청이 너무 많습니다. 잠시 후 다시 시도해주세요.", 429, {"blocked_until": blocked_until_text})

    valid, message = validate_signup_payload(payload)
    if not valid:
        mark_rate_limit_failure("signup", payload.get("username", ""))
        return error_response(message, 400)

    conn = get_db_connection()
    cur = conn.cursor()
    exists_email = cur.execute("SELECT id FROM users WHERE email = ?", (payload["email"],)).fetchone()
    if exists_email:
        conn.close()
        return error_response("이미 등록된 이메일입니다.", 409)

    exists_username = cur.execute("SELECT id FROM users WHERE username = ?", (payload["username"],)).fetchone()
    if exists_username:
        conn.close()
        mark_rate_limit_failure("signup", payload.get("username", ""))
        return error_response("이미 사용 중인 아이디입니다.", 409)

    exists_nickname = cur.execute("SELECT id FROM users WHERE nickname = ?", (payload["nickname"],)).fetchone()
    if exists_nickname:
        conn.close()
        mark_rate_limit_failure("signup", payload.get("username", ""))
        return error_response("이미 사용 중인 닉네임입니다.", 409)

    cur.execute(
        """
        INSERT INTO users (
            name, username, email, phone, birth_date, password_hash, join_date,
            role, status, generation, interests, certificates, availability, nickname, nickname_updated_at
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            payload["name"].strip(),
            payload["username"].strip(),
            payload["email"].strip(),
            payload["phone"].strip(),
            payload["birthDate"].strip(),
            generate_password_hash(payload["password"]),
            now_iso(),
            "GENERAL",
            "active",
            str(payload.get("generation", "")).strip(),
            to_list_text(payload.get("interests", "")),
            to_list_text(payload.get("certificates", "")),
            str(payload.get("availability", "")).strip(),
            str(payload.get("nickname", "")).strip(),
            now_iso(),
        ),
    )
    user_id = cur.lastrowid
    log_audit(conn, "signup", "user", user_id, user_id)
    conn.commit()
    row = cur.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()
    conn.close()

    write_app_log("info", "signup", user_id=user_id)
    clear_rate_limit("signup", payload.get("username", ""))

    session["user_id"] = user_id
    user_data = user_row_to_dict(row)
    payload = {
        "message": "회원가입이 완료되었습니다.",
        "user": user_data,
    }
    return jsonify({"success": True, "data": payload, "ok": True, **payload})


def auth_login():
    payload = request.get_json(silent=True) or {}
    username = str(payload.get("username", "")).strip()
    password = str(payload.get("password", ""))
    client_ip = get_client_ip()

    blocked, blocked_until = is_rate_limited("login", username)
    if blocked:
        blocked_until_text = blocked_until.isoformat() if blocked_until else now_iso()
        write_app_log("warning", "login_rate_limited", extra={"blocked_until": blocked_until_text})
        return error_response(
            f"로그인 시도가 너무 많습니다. {blocked_until_text} 이후 다시 시도하세요.",
            429,
            {"blocked_until": blocked_until_text},
        )

    if not username or not password:
        return error_response("아이디와 비밀번호를 입력해주세요.", 400)

    conn = get_db_connection()
    row = conn.execute("SELECT * FROM users WHERE username = ?", (username,)).fetchone()

    if not row:
        conn.close()
        mark_rate_limit_failure("login", username)
        write_app_log("warning", "login_failed_unknown_user", extra={"username": username})
        return error_response("아이디 또는 비밀번호가 틀렸습니다.", 401)

    try_unlock_expired_user(conn, row)
    row = conn.execute("SELECT * FROM users WHERE id = ?", (row["id"],)).fetchone()

    if row["status"] in ("withdrawn", "deleted"):
        conn.close()
        write_app_log("warning", "login_withdrawn", user_id=row["id"])
        return error_response("탈퇴 처리된 계정입니다.", 403)

    if row["status"] == "suspended":
        conn.close()
        write_app_log("warning", "login_suspended", user_id=row["id"])
        return error_response("정지된 계정입니다. 관리자에게 문의하세요.", 403)

    if not check_password_hash(row["password_hash"], password):
        locked, _ = increase_login_failure(conn, row)
        conn.close()
        mark_rate_limit_failure("login", username)
        write_app_log("warning", "login_failed", user_id=row["id"])
        if locked:
            return error_response("로그인 5회 실패로 계정이 잠금되었습니다.", 423)
        return error_response("아이디 또는 비밀번호가 틀렸습니다.", 401)

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
        }
        return jsonify({"success": True, "data": payload, "ok": True, **payload})

    payload = {"user": user_row_to_dict(row)}
    return jsonify({"success": True, "data": payload, "ok": True, **payload})


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
        return error_response("연락처 또는 이메일을 입력하세요.", 400)

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

    return error_response("일치하는 계정을 찾지 못했습니다.", 404)


def auth_reset_password():
    payload = request.get_json(silent=True) or {}
    username = str(payload.get("username", "")).strip()
    contact = str(payload.get("contact", "")).strip()
    new_password = str(payload.get("newPassword", ""))

    blocked, blocked_until = is_rate_limited("reset-password", username)
    if blocked:
        blocked_until_text = blocked_until.isoformat() if blocked_until else now_iso()
        return error_response("요청이 너무 많습니다. 잠시 후 다시 시도해주세요.", 429, {"blocked_until": blocked_until_text})

    if not username or not contact or not new_password:
        mark_rate_limit_failure("reset-password", username)
        return error_response("필수 값을 입력해주세요.", 400)

    valid_password, password_message = validate_password_policy(new_password)
    if not valid_password:
        mark_rate_limit_failure("reset-password", username)
        return error_response(password_message, 400)

    normalized_contact = contact.replace("-", "").lower()

    conn = get_db_connection()
    row = conn.execute(
        "SELECT * FROM users WHERE username = ?",
        (username,),
    ).fetchone()

    if not row:
        conn.close()
        mark_rate_limit_failure("reset-password", username)
        return error_response("일치하는 계정을 찾지 못했습니다.", 404)

    email_key = (row["email"] or "").replace("-", "").lower()
    phone_key = (row["phone"] or "").replace("-", "").lower()
    if normalized_contact not in (email_key, phone_key):
        conn.close()
        mark_rate_limit_failure("reset-password", username)
        return error_response("일치하는 계정을 찾지 못했습니다.", 404)

    conn.execute(
        "UPDATE users SET password_hash = ?, failed_login_count = 0, locked_until = NULL, status = CASE WHEN status='suspended' THEN COALESCE(CASE WHEN approved_at IS NOT NULL THEN 'active' END, 'pending') ELSE status END WHERE id = ?",
        (generate_password_hash(new_password), row["id"]),
    )
    log_audit(conn, "password_reset", "user", row["id"], row["id"])
    send_email(row["email"], "[Weave] 비밀번호 재설정 안내", "비밀번호가 재설정되었습니다. 본인이 요청하지 않았다면 즉시 운영진에 문의하세요.")
    conn.commit()
    conn.close()
    clear_rate_limit("reset-password", username)
    write_app_log("info", "password_reset", user_id=row["id"])
    payload = {"ok": True, "message": "비밀번호가 재설정되었습니다."}
    return jsonify({"success": True, "data": payload, **payload})


def auth_unlock_account():
    payload = request.get_json(silent=True) or {}
    username = str(payload.get("username", "")).strip()
    contact = normalize_contact(payload.get("contact", ""))

    if not username or not contact:
        return jsonify({"ok": False, "message": "아이디와 휴대폰/이메일이 필요합니다."}), 400

    conn = get_db_connection()
    row = conn.execute("SELECT * FROM users WHERE username = ?", (username,)).fetchone()
    if not row:
        conn.close()
        return jsonify({"ok": False, "message": "일치하는 계정을 찾지 못했습니다."}), 404

    if contact not in (normalize_contact(row["email"]), normalize_contact(row["phone"])):
        conn.close()
        return jsonify({"ok": False, "message": "인증 정보가 일치하지 않습니다."}), 403

    next_status = "active" if row["approved_at"] else "pending"
    conn.execute(
        "UPDATE users SET status = ?, failed_login_count = 0, locked_until = NULL WHERE id = ?",
        (next_status, row["id"]),
    )
    conn.commit()
    conn.close()
    return jsonify({"ok": True, "message": "계정 잠금이 해제되었습니다."})


def auth_withdraw():
    payload = request.get_json(silent=True) or {}
    contact = normalize_contact(payload.get("contact", ""))
    password = str(payload.get("password", ""))
    reason = str(payload.get("reason", "")).strip()

    conn = get_db_connection()
    me = get_current_user_row(conn)
    if not me:
        conn.close()
        return error_response("Unauthorized", 401)

    if contact not in (normalize_contact(me["email"]), normalize_contact(me["phone"])):
        conn.close()
        return error_response("연락처/이메일 인증이 필요합니다.", 403)

    if not check_password_hash(me["password_hash"], password):
        conn.close()
        return error_response("비밀번호가 올바르지 않습니다.", 403)

    retention_days = int(os.environ.get("WEAVE_RETENTION_DAYS", "30"))
    retention_until = (datetime.now() + timedelta(days=retention_days)).isoformat()
    deleted_at = now_iso()
    anonymized = f"withdrawn-{me['id']}-{int(datetime.now().timestamp())}"

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
    conn.commit()
    conn.close()
    session.pop("user_id", None)
    write_app_log("info", "user_withdraw", user_id=me["id"])
    return success_response({"ok": True, "message": f"탈퇴 완료. 데이터는 {retention_days}일 보관 후 파기됩니다."})


