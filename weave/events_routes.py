from weave.core import *


def list_activities():
    date_value = str(request.args.get("date", "")).strip()
    view = str(request.args.get("view", "month")).strip().lower()
    if view not in ("month", "week"):
        view = "month"

    if not date_value:
        base_date = datetime.now().date()
    else:
        try:
            base_date = datetime.fromisoformat(date_value).date()
        except Exception:
            base_date = datetime.now().date()

    if view == "week":
        start_date = base_date - timedelta(days=base_date.weekday())
        end_date = start_date + timedelta(days=6)
    else:
        start_date = base_date.replace(day=1)
        next_month = (start_date.replace(day=28) + timedelta(days=4)).replace(day=1)
        end_date = next_month - timedelta(days=1)

    conn = get_db_connection()
    rows = conn.execute(
        """
        SELECT * FROM activities
        WHERE is_cancelled = 0
        ORDER BY start_at ASC
        """,
    ).fetchall()
    conn.close()
    filtered_rows = []
    for row in rows:
        activity_date = activity_start_date_local(row["start_at"])
        if activity_date and start_date <= activity_date <= end_date:
            filtered_rows.append(row)
    return jsonify(
        {
            "ok": True,
            "view": view,
            "range": {"start": start_date.isoformat(), "end": end_date.isoformat()},
            "items": [serialize_activity_row(row) for row in filtered_rows],
        }
    )


def create_activity():
    payload = request.get_json(silent=True) or {}
    required = ["title", "startAt", "endAt"]
    for field in required:
        if not str(payload.get(field, "")).strip():
            return jsonify({"ok": False, "message": f"{field} 값이 필요합니다."}), 400

    title = str(payload.get("title", "")).strip()
    if len(title) > 120:
        return jsonify({"ok": False, "message": "활동 제목은 120자 이하여야 합니다."}), 400

    start_at = str(payload.get("startAt", "")).strip()
    end_at = str(payload.get("endAt", "")).strip()
    start_dt = parse_iso_datetime(start_at)
    end_dt = parse_iso_datetime(end_at)
    if not start_dt or not end_dt:
        return jsonify({"ok": False, "message": "시작/종료 시간 형식이 올바르지 않습니다."}), 400
    if end_dt <= start_dt:
        return jsonify({"ok": False, "message": "종료 시간은 시작 시간보다 늦어야 합니다."}), 400

    recruitment_limit = int(payload.get("recruitmentLimit", 0) or 0)
    if recruitment_limit < 0 or recruitment_limit > 1000:
        return jsonify({"ok": False, "message": "모집 인원은 0~1000 범위여야 합니다."}), 400

    recurrence_group_id = str(payload.get("recurrenceGroupId", "")).strip()
    if recurrence_group_id and (len(recurrence_group_id) > 64 or not re.fullmatch(r"[A-Za-z0-9_-]+", recurrence_group_id)):
        return jsonify({"ok": False, "message": "반복 그룹 ID 형식이 올바르지 않습니다."}), 400

    conn = get_db_connection()
    me = get_current_user_row(conn)
    if not me:
        conn.close()
        return jsonify({"ok": False, "message": "로그인이 필요합니다."}), 401
    cur = conn.cursor()
    cur.execute(
        """
        INSERT INTO activities (
            title, description, start_at, end_at, place, supplies, gather_time,
            manager_name, recruitment_limit, recurrence_group_id, created_by, created_at
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            title,
            str(payload.get("description", "")).strip(),
            start_at,
            end_at,
            str(payload.get("place", "")).strip(),
            str(payload.get("supplies", "")).strip(),
            str(payload.get("gatherTime", "")).strip(),
            str(payload.get("manager", me["name"])).strip(),
            recruitment_limit,
            recurrence_group_id,
            me["id"],
            now_iso(),
        ),
    )
    activity_id = cur.lastrowid
    conn.commit()
    row = conn.execute("SELECT * FROM activities WHERE id = ?", (activity_id,)).fetchone()
    conn.close()
    return jsonify({"ok": True, "activity": serialize_activity_row(row)})


def apply_activity(activity_id):
    conn = get_db_connection()
    me = get_current_user_row(conn)
    if not me:
        conn.close()
        return jsonify({"ok": False, "message": "로그인이 필요합니다."}), 401
    activity = conn.execute("SELECT * FROM activities WHERE id = ?", (activity_id,)).fetchone()
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
    next_status = "confirmed" if limit_count <= 0 or confirmed_count < limit_count else "waiting"

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
    return jsonify({"ok": True, "status": next_status})


def cancel_recurrence_group(group_id):
    group_id = str(group_id or "").strip()
    if not group_id or len(group_id) > 64 or not re.fullmatch(r"[A-Za-z0-9_-]+", group_id):
        return jsonify({"ok": False, "message": "유효하지 않은 반복 그룹 ID입니다."}), 400

    conn = get_db_connection()
    activities = conn.execute(
        "SELECT id FROM activities WHERE recurrence_group_id = ? AND is_cancelled = 0",
        (group_id,),
    ).fetchall()
    if not activities:
        conn.close()
        return jsonify({"ok": False, "message": "취소할 반복 그룹이 없습니다."}), 404

    activity_ids = [row["id"] for row in activities]
    placeholders = ",".join(["?"] * len(activity_ids))

    conn.execute(
        f"UPDATE activities SET is_cancelled = 1, cancelled_at = ? WHERE id IN ({placeholders})",
        [now_iso(), *activity_ids],
    )
    conn.execute(
        f"""
        UPDATE activity_applications
        SET status = 'cancelled', updated_at = ?
        WHERE activity_id IN ({placeholders})
          AND status IN ('waiting', 'confirmed')
        """,
        [now_iso(), *activity_ids],
    )
    conn.commit()
    conn.close()
    return jsonify({"ok": True, "message": "반복 그룹 일정이 일괄 취소되었습니다.", "count": len(activity_ids)})


def recurrence_group_impact(group_id):
    group_id = str(group_id or "").strip()
    if not group_id or len(group_id) > 64 or not re.fullmatch(r"[A-Za-z0-9_-]+", group_id):
        return jsonify({"ok": False, "message": "유효하지 않은 반복 그룹 ID입니다."}), 400

    conn = get_db_connection()
    activity_count = conn.execute(
        "SELECT COUNT(*) AS c FROM activities WHERE recurrence_group_id = ? AND is_cancelled = 0",
        (group_id,),
    ).fetchone()["c"]
    application_count = conn.execute(
        """
        SELECT COUNT(*) AS c
        FROM activity_applications ap
        JOIN activities a ON a.id = ap.activity_id
        WHERE a.recurrence_group_id = ?
          AND a.is_cancelled = 0
          AND ap.status IN ('waiting', 'confirmed')
        """,
        (group_id,),
    ).fetchone()["c"]

    preview_rows = conn.execute(
        """
        SELECT
            a.id,
            a.title,
            a.start_at,
            a.end_at,
            a.place,
            (
                SELECT COUNT(*)
                FROM activity_applications ap
                WHERE ap.activity_id = a.id
                  AND ap.status IN ('waiting', 'confirmed')
            ) AS active_applications
        FROM activities a
        WHERE a.recurrence_group_id = ?
          AND a.is_cancelled = 0
        ORDER BY a.start_at ASC
        LIMIT 5
        """,
        (group_id,),
    ).fetchall()
    conn.close()

    return jsonify(
        {
            "ok": True,
            "groupId": group_id,
            "impact": {
                "activityCount": int(activity_count or 0),
                "applicationCount": int(application_count or 0),
                "previewItems": [
                    {
                        "id": row["id"],
                        "title": row["title"],
                        "startAt": row["start_at"],
                        "endAt": row["end_at"],
                        "place": row["place"],
                        "applicationCount": int(row["active_applications"] or 0),
                    }
                    for row in preview_rows
                ],
            },
        }
    )


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
    return jsonify({"ok": True, "message": "신청이 취소되었습니다."})


def create_attendance_qr_token(activity_id):
    conn = get_db_connection()
    me = get_current_user_row(conn)
    if not me:
        conn.close()
        return jsonify({"ok": False, "message": "로그인이 필요합니다."}), 401
    activity = conn.execute("SELECT id FROM activities WHERE id = ?", (activity_id,)).fetchone()
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
    return jsonify({"ok": True, "token": token, "expiresAt": expires})


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

    activity = conn.execute("SELECT * FROM activities WHERE id = ?", (activity_id,)).fetchone()
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
    return jsonify({"ok": True, "hours": hours, "points": points})


def bulk_attendance(activity_id):
    payload = request.get_json(silent=True) or {}
    entries = payload.get("entries", [])
    if not isinstance(entries, list) or not entries:
        return jsonify({"ok": False, "message": "entries 배열이 필요합니다."}), 400

    conn = get_db_connection()
    activity = conn.execute("SELECT * FROM activities WHERE id = ?", (activity_id,)).fetchone()
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
            (final_status, status, final_hours, final_points, penalty, now_iso(), app_row["id"]),
        )
        updated += 1

    conn.commit()
    conn.close()
    return jsonify({"ok": True, "updated": updated})


def admin_dashboard():
    today = datetime.now().date().isoformat()
    month_prefix = datetime.now().strftime("%Y-%m")

    conn = get_db_connection()
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
    rows = conn.execute(
        "SELECT id, name, username, email, phone, role, status, generation FROM users ORDER BY id ASC"
    ).fetchall()
    conn.close()
    return csv_response(
        "participants.csv",
        ["id", "name", "username", "email", "phone", "role", "status", "generation"],
        [[row["id"], row["name"], row["username"], row["email"], row["phone"], row["role"], row["status"], row["generation"]] for row in rows],
    )


def export_attendance_csv():
    conn = get_db_connection()
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
        ["activity", "start_at", "name", "username", "apply_status", "attendance_status", "hours"],
        [[row["title"], row["start_at"], row["name"], row["username"], row["status"], row["attendance_status"], row["hours"]] for row in rows],
    )


def export_hours_csv():
    conn = get_db_connection()
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
        [[row["name"], row["username"], row["total_hours"], row["total_points"], row["penalty_points"]] for row in rows],
    )


def list_events():
    page = max(1, int(request.args.get("page", "1") or 1))
    page_size = min(100, max(1, int(request.args.get("pageSize", "10") or 10)))
    offset = (page - 1) * page_size
    conn = get_db_connection()
    me = get_current_user_row(conn)
    if not me:
        conn.close()
        return error_response("Unauthorized", 401)
    if not role_at_least(me["role"], "MEMBER"):
        conn.close()
        return error_response("단원 이상만 이벤트를 확인할 수 있습니다.", 403)
    cache_key = f"events:list:{me['id']}:{page}:{page_size}"
    cached = get_cache(cache_key)
    if cached is not None:
        conn.close()
        return success_response(cached)

    total = conn.execute("SELECT COUNT(*) AS c FROM events").fetchone()["c"]
    rows = conn.execute(
        """
        SELECT e.*, u.username AS author_username,
               (SELECT COUNT(*) FROM event_participants p WHERE p.event_id = e.id AND p.status='registered') AS participant_count,
               (SELECT status FROM event_participants p2 WHERE p2.event_id = e.id AND p2.user_id = ? LIMIT 1) AS my_status
        FROM events e
        LEFT JOIN users u ON u.id = e.created_by
        ORDER BY COALESCE(e.start_datetime, e.event_date) ASC
        LIMIT ? OFFSET ?
        """,
        (me["id"], page_size, offset),
    ).fetchall()
    conn.close()
    data = {
        "items": [
            {
                "id": row["id"],
                "title": row["title"],
                "description": row["description"],
                "location": row["location"],
                "supplies": row["supplies"],
                "noticePostId": row["notice_post_id"],
                "startDatetime": row["start_datetime"] or row["event_date"],
                "endDatetime": row["end_datetime"] or row["start_datetime"] or row["event_date"],
                "capacity": int(row["capacity"] or row["max_participants"] or 0),
                "eventDate": row["event_date"],
                "maxParticipants": row["max_participants"],
                "participantCount": row["participant_count"],
                "createdBy": row["created_by"],
                "createdByUsername": row["author_username"],
                "createdAt": row["created_at"],
                "myStatus": row["my_status"],
            }
            for row in rows
        ],
        "pagination": {
            "total": int(total or 0),
            "page": page,
            "pageSize": page_size,
            "totalPages": max(1, (int(total or 0) + page_size - 1) // page_size),
        },
    }
    set_cache(cache_key, data)
    return success_response(data)


def create_event():
    payload = request.get_json(silent=True) or {}
    title = str(payload.get("title", "")).strip()
    start_datetime = str(payload.get("start_datetime", payload.get("event_date", ""))).strip()
    end_datetime = str(payload.get("end_datetime", start_datetime)).strip()
    if not title or not start_datetime:
        return error_response("title/start_datetime은 필수입니다.", 400)
    if not parse_iso_datetime(start_datetime) or not parse_iso_datetime(end_datetime):
        return error_response("start_datetime/end_datetime은 ISO 형식이어야 합니다.", 400)

    conn = get_db_connection()
    me = get_current_user_row(conn)
    if not me:
        conn.close()
        return error_response("Unauthorized", 401)
    cur = conn.cursor()
    cur.execute(
        """
        INSERT INTO events (
            title, description, location, event_date, start_datetime, end_datetime,
            max_participants, capacity, supplies, notice_post_id, created_by, created_at, updated_at
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            title,
            str(payload.get("description", "")).strip(),
            str(payload.get("location", "")).strip(),
            start_datetime,
            start_datetime,
            end_datetime,
            int(payload.get("max_participants", payload.get("capacity", 0)) or 0),
            int(payload.get("capacity", payload.get("max_participants", 0)) or 0),
            str(payload.get("supplies", "")).strip(),
            payload.get("notice_post_id"),
            me["id"],
            now_iso(),
            now_iso(),
        ),
    )
    event_id = cur.lastrowid
    log_audit(conn, "create_event", "event", event_id, me["id"])
    record_user_activity(conn, me["id"], "event_create", "event", event_id, {"title": title})
    conn.commit()
    conn.close()
    invalidate_cache("events:list:")
    write_app_log("info", "create_event", user_id=me["id"], extra={"event_id": event_id})
    return success_response({"event_id": event_id}, 201)


def update_event(event_id):
    payload = request.get_json(silent=True) or {}
    conn = get_db_connection()
    me = get_current_user_row(conn)
    if not me:
        conn.close()
        return error_response("Unauthorized", 401)
    target = conn.execute("SELECT * FROM events WHERE id = ?", (event_id,)).fetchone()
    if not target:
        conn.close()
        return error_response("이벤트를 찾을 수 없습니다.", 404)

    title = str(payload.get("title", target["title"])).strip()
    description = str(payload.get("description", target["description"])).strip()
    location = str(payload.get("location", target["location"])).strip()
    supplies = str(payload.get("supplies", target["supplies"])).strip()
    notice_post_id = payload.get("notice_post_id", target["notice_post_id"])
    start_datetime = str(payload.get("start_datetime", payload.get("event_date", target["start_datetime"] or target["event_date"]))).strip()
    end_datetime = str(payload.get("end_datetime", target["end_datetime"] or start_datetime)).strip()
    capacity = int(payload.get("capacity", payload.get("max_participants", target["capacity"] or target["max_participants"])) or 0)
    if not parse_iso_datetime(start_datetime) or not parse_iso_datetime(end_datetime):
        conn.close()
        return error_response("start_datetime/end_datetime은 ISO 형식이어야 합니다.", 400)

    conn.execute(
        """
        UPDATE events
        SET title = ?, description = ?, location = ?, supplies = ?, notice_post_id = ?,
            event_date = ?, start_datetime = ?, end_datetime = ?, max_participants = ?, capacity = ?, updated_at = ?
        WHERE id = ?
        """,
        (
            title,
            description,
            location,
            supplies,
            notice_post_id,
            start_datetime,
            start_datetime,
            end_datetime,
            capacity,
            capacity,
            now_iso(),
            event_id,
        ),
    )
    notified = send_event_change_notifications(conn, event_id, title)
    log_audit(conn, "update_event", "event", event_id, me["id"])
    conn.commit()
    conn.close()
    invalidate_cache("events:list:")
    write_app_log("info", "update_event", user_id=me["id"], extra={"event_id": event_id, "notified": notified})
    return success_response({"event_id": event_id, "notified": notified})


def get_event_detail(event_id):
    conn = get_db_connection()
    me = get_current_user_row(conn)
    if not me:
        conn.close()
        return error_response("Unauthorized", 401)
    if not role_at_least(me["role"], "MEMBER"):
        conn.close()
        return error_response("단원 이상만 이벤트를 확인할 수 있습니다.", 403)

    row = conn.execute(
        """
        SELECT e.*, u.username AS author_username,
               (SELECT COUNT(*) FROM event_participants p WHERE p.event_id = e.id AND p.status = 'registered') AS participant_count,
               (SELECT status FROM event_participants p2 WHERE p2.event_id = e.id AND p2.user_id = ? LIMIT 1) AS my_status
        FROM events e
        LEFT JOIN users u ON u.id = e.created_by
        WHERE e.id = ?
        """,
        (me["id"], event_id),
    ).fetchone()
    if not row:
        conn.close()
        return error_response("이벤트를 찾을 수 없습니다.", 404)

    participants = conn.execute(
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
            "id": row["id"],
            "title": row["title"],
            "description": row["description"],
            "location": row["location"],
            "supplies": row["supplies"],
            "noticePostId": row["notice_post_id"],
            "startDatetime": row["start_datetime"] or row["event_date"],
            "endDatetime": row["end_datetime"] or row["start_datetime"] or row["event_date"],
            "capacity": int(row["capacity"] or row["max_participants"] or 0),
            "participantCount": int(row["participant_count"] or 0),
            "myStatus": row["my_status"],
            "createdBy": row["created_by"],
            "createdByUsername": row["author_username"],
            "createdAt": row["created_at"],
            "participants": [
                {
                    "userId": p["user_id"],
                    "status": p["status"],
                    "joinedAt": p["created_at"],
                    "nickname": p["nickname"] or p["username"],
                    "role": normalize_role(p["role"]),
                }
                for p in participants
            ],
        }
    )


def list_event_participants(event_id):
    conn = get_db_connection()
    me = get_current_user_row(conn)
    if not me:
        conn.close()
        return error_response("Unauthorized", 401)
    if not role_at_least(me["role"], "MEMBER"):
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
    if not role_at_least(me["role"], "MEMBER"):
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
    if not role_at_least(me["role"], "MEMBER"):
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


def event_detail(event_id):
    conn = get_db_connection()
    me = get_current_user_row(conn)
    if not me:
        conn.close()
        return error_response("Unauthorized", 401)
    if not role_at_least(me["role"], "MEMBER"):
        conn.close()
        return error_response("단원 이상만 접근할 수 있습니다.", 403)

    event = conn.execute("SELECT * FROM events WHERE id = ?", (event_id,)).fetchone()
    if not event:
        conn.close()
        return error_response("이벤트를 찾을 수 없습니다.", 404)
    votes = conn.execute(
        "SELECT vote_status, COUNT(*) AS c FROM event_votes WHERE event_id = ? GROUP BY vote_status",
        (event_id,),
    ).fetchall()
    my_vote = conn.execute(
        "SELECT vote_status FROM event_votes WHERE event_id = ? AND user_id = ?",
        (event_id, me["id"]),
    ).fetchone()
    conn.close()

    summary = {"ATTEND": 0, "ABSENT": 0, "WAITING": 0}
    for row in votes:
        key = str(row["vote_status"] or "").upper()
        if key in summary:
            summary[key] = int(row["c"] or 0)
    return success_response({"event": dict(event), "summary": summary, "my_vote": my_vote["vote_status"] if my_vote else None})


def vote_event(event_id):
    payload = request.get_json(silent=True) or {}
    status = str(payload.get("status", "")).strip().upper()
    if status not in ("ATTEND", "ABSENT", "WAITING"):
        return error_response("투표 상태는 ATTEND/ABSENT/WAITING 중 하나여야 합니다.", 400)

    conn = get_db_connection()
    me = get_current_user_row(conn)
    if not me:
        conn.close()
        return error_response("Unauthorized", 401)
    if not role_at_least(me["role"], "MEMBER"):
        conn.close()
        return error_response("단원 이상만 투표할 수 있습니다.", 403)

    event = conn.execute("SELECT id FROM events WHERE id = ?", (event_id,)).fetchone()
    if not event:
        conn.close()
        return error_response("이벤트를 찾을 수 없습니다.", 404)

    existing = conn.execute(
        "SELECT id FROM event_votes WHERE event_id = ? AND user_id = ?",
        (event_id, me["id"]),
    ).fetchone()
    if existing:
        conn.execute("UPDATE event_votes SET vote_status = ?, updated_at = ? WHERE id = ?", (status, now_iso(), existing["id"]))
    else:
        conn.execute(
            "INSERT INTO event_votes (event_id, user_id, vote_status, created_at, updated_at) VALUES (?, ?, ?, ?, ?)",
            (event_id, me["id"], status, now_iso(), now_iso()),
        )
    log_audit(conn, "vote_event", "event", event_id, me["id"], {"status": status})
    conn.commit()
    conn.close()
    return success_response({"event_id": event_id, "status": status})


