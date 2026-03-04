from weave.core import *


def delete_my_account():
    conn = get_db_connection()
    me = get_current_user_row(conn)
    if not me:
        conn.close()
        return error_response("Unauthorized", 401)

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
        return jsonify({"ok": False, "message": "로그인이 필요합니다."}), 401
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

    total_hours = sum(float(row["hours"] or 0) for row in rows)
    total_points = sum(int(row["points"] or 0) for row in rows) - sum(int(row["penalty_points"] or 0) for row in rows)
    items = [
        {
            "activityId": row["activity_id"],
            "title": row["title"],
            "startAt": row["start_at"],
            "endAt": row["end_at"],
            "place": row["place"],
            "status": row["status"],
            "attendanceStatus": row["attendance_status"],
            "hours": row["hours"],
            "points": row["points"],
            "penaltyPoints": row["penalty_points"],
        }
        for row in rows
    ]
    conn.close()
    return jsonify(
        {
            "ok": True,
            "summary": {
                "totalHours": round(total_hours, 2),
                "totalPoints": total_points,
                "certificateDownloadUrl": "/api/me/certificate.csv",
            },
            "items": items,
        }
    )


def my_certificate_csv():
    conn = get_db_connection()
    me = get_current_user_row(conn)
    if not me:
        conn.close()
        return jsonify({"ok": False, "message": "로그인이 필요합니다."}), 401
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

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["이름", "아이디", "활동명", "시작", "종료", "장소", "출석상태", "봉사시간"])
    for row in rows:
        writer.writerow(
            [
                me["name"],
                me["username"],
                row["title"],
                row["start_at"],
                row["end_at"],
                row["place"],
                row["attendance_status"],
                row["hours"],
            ]
        )

    response = Response(output.getvalue(), mimetype="text/csv; charset=utf-8")
    response.headers["Content-Disposition"] = "attachment; filename=my_activity_certificate.csv"
    return response


def user_profile():
    row = get_current_user_row()
    return success_response({"user": user_row_to_dict(row)})


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
        return error_response("Unauthorized", 401)

    updated, err = _update_nickname_common(conn, me, nickname, bypass_window=False)
    if err:
        conn.close()
        return err
    log_audit(conn, "change_nickname", "user", me["id"], me["id"], {"nickname": nickname})
    record_user_activity(conn, me["id"], "nickname_change", "user", me["id"], {"nickname": nickname})
    conn.commit()
    conn.close()
    return success_response({"message": "닉네임이 변경되었습니다.", "user": user_row_to_dict(updated)})


def list_my_activity():
    conn = get_db_connection()
    me = get_current_user_row(conn)
    if not me:
        conn.close()
        return error_response("Unauthorized", 401)
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
    return success_response(
        {
            "items": [
                {
                    "type": row["activity_type"],
                    "targetType": row["target_type"],
                    "targetId": row["target_id"],
                    "metadata": json.loads(row["metadata_json"] or "{}"),
                    "createdAt": row["created_at"],
                }
                for row in rows
            ]
        }
    )


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
        return error_response("Unauthorized", 401)
    target = conn.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()
    if not target:
        conn.close()
        return error_response("사용자를 찾을 수 없습니다.", 404)

    updated, err = _update_nickname_common(conn, target, nickname, bypass_window=True)
    if err:
        conn.close()
        return err
    log_audit(conn, "admin_change_nickname", "user", user_id, me["id"], {"nickname": nickname})
    conn.commit()
    conn.close()
    return success_response({"message": "닉네임이 변경되었습니다.", "user": user_row_to_dict(updated)})


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
        return error_response("Unauthorized", 401)
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
        return error_response("Unauthorized", 401)
    conn.close()
    if normalize_role(me["role"]) != "MEMBER":
        return error_response("단원만 임원 승격을 요청할 수 있습니다.", 400)
    return request_role_change_internal("EXECUTIVE")


def request_role_change_internal(target):
    conn = get_db_connection()
    me = get_current_user_row(conn)
    if not me:
        conn.close()
        return error_response("Unauthorized", 401)

    current = normalize_role(me["role"])
    target = normalize_role(target)
    allowed = {("GENERAL", "MEMBER"), ("MEMBER", "EXECUTIVE")}
    if (current, target) not in allowed:
        conn.close()
        return error_response("요청 가능한 역할 전환이 아닙니다.", 400)

    pending = conn.execute(
        "SELECT id FROM role_requests WHERE user_id = ? AND status = 'PENDING'",
        (me["id"],),
    ).fetchone()
    if pending:
        conn.close()
        return error_response("이미 처리 대기 중인 요청이 있습니다.", 409)

    cur = conn.cursor()
    cur.execute(
        """
        INSERT INTO role_requests (user_id, from_role, to_role, status, created_at)
        VALUES (?, ?, ?, 'PENDING', ?)
        """,
        (me["id"], current, target, now_iso()),
    )
    request_id = cur.lastrowid
    log_audit(conn, "request_role_change", "role_request", request_id, me["id"], {"from": current, "to": target})
    conn.commit()
    conn.close()
    return success_response({"request_id": request_id}, 201)


def list_role_requests():
    status = str(request.args.get("status", "PENDING")).strip().upper()
    page = max(1, int(request.args.get("page", "1") or 1))
    page_size = min(100, max(1, int(request.args.get("pageSize", "20") or 20)))
    offset = (page - 1) * page_size

    conn = get_db_connection()
    total = conn.execute("SELECT COUNT(*) AS c FROM role_requests WHERE status = ?", (status,)).fetchone()["c"]
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


def _decide_role_request(request_id, approve=True):
    conn = get_db_connection()
    me = get_current_user_row(conn)
    if not me:
        conn.close()
        return error_response("Unauthorized", 401)
    req = conn.execute("SELECT * FROM role_requests WHERE id = ?", (request_id,)).fetchone()
    if not req:
        conn.close()
        return error_response("요청을 찾을 수 없습니다.", 404)
    if req["status"] != "PENDING":
        conn.close()
        return error_response("이미 처리된 요청입니다.", 409)

    next_status = "APPROVED" if approve else "REJECTED"
    conn.execute(
        "UPDATE role_requests SET status = ?, decided_at = ?, decided_by = ? WHERE id = ?",
        (next_status, now_iso(), me["id"], request_id),
    )
    if approve:
        conn.execute("UPDATE users SET role = ?, is_admin = CASE WHEN ? = 'ADMIN' THEN 1 ELSE is_admin END WHERE id = ?", (req["to_role"], req["to_role"], req["user_id"]))
    log_audit(conn, f"role_request_{next_status.lower()}", "role_request", request_id, me["id"], {"user_id": req["user_id"]})
    conn.commit()
    conn.close()
    return success_response({"request_id": request_id, "status": next_status})


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


