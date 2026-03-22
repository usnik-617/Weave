from weave.authz import role_at_least
from weave.core import (
    get_db_connection,
    log_audit,
    record_user_activity,
)
from weave.responses import error_response, success_response
from weave.time_utils import now_iso, parse_iso_datetime
from weave.notice_calendar_integrity import (
    _delete_activity_with_relations,
    _delete_event_with_relations,
    sync_notice_linked_calendar,
)


def create_notice_post(payload, conn, me, post_visibility_status):
    title = str(payload.get("title", "")).strip()
    publish_at = str(payload.get("publish_at", "")).strip() or None
    if publish_at and not parse_iso_datetime(publish_at):
        return None, error_response("publish_at은 ISO 형식이어야 합니다.", 400)

    status = post_visibility_status(publish_at)

    cur = conn.cursor()
    cur.execute(
        """
        INSERT INTO posts (
            category, title, content, is_pinned, is_important, publish_at, status, image_url, thumb_url,
            volunteer_start_date, volunteer_end_date, author_id, created_at, updated_at
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            "notice",
            title,
            str(payload.get("content", "")),
            1 if bool(payload.get("is_pinned", False)) else 0,
            1 if bool(payload.get("is_important", False)) else 0,
            publish_at,
            status,
            str(payload.get("image_url", "")).strip(),
            str(payload.get("thumb_url", "")).strip(),
            str(payload.get("volunteerStartDate", "")).strip() or None,
            str(payload.get("volunteerEndDate", "")).strip()
            or str(payload.get("volunteerStartDate", "")).strip()
            or None,
            me["id"],
            now_iso(),
            now_iso(),
        ),
    )
    post_id = cur.lastrowid

    volunteer_start = str(payload.get("volunteerStartDate", "")).strip() or None
    volunteer_end = str(payload.get("volunteerEndDate", "")).strip() or volunteer_start
    if volunteer_start:
        activity_start = f"{volunteer_start}T09:00:00"
        activity_end = f"{(volunteer_end or volunteer_start)}T18:00:00"
        conn.execute(
            """
            INSERT INTO activities (
                title, description, start_at, end_at, place, supplies, gather_time,
                manager_name, recruitment_limit, notice_post_id, created_by, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                title,
                str(payload.get("content", ""))[:300],
                activity_start,
                activity_end,
                str(payload.get("place", "")).strip(),
                str(payload.get("supplies", "")).strip(),
                "",
                (
                    me["nickname"]
                    if "nickname" in me.keys() and me["nickname"]
                    else me["username"]
                ),
                int(payload.get("recruitment_limit", 0) or 0),
                post_id,
                me["id"],
                now_iso(),
            ),
        )

    log_audit(conn, "create_post", "post", post_id, me["id"], {"category": "notice"})
    record_user_activity(
        conn, me["id"], "post_create", "post", post_id, {"category": "notice"}
    )
    return post_id, None


def update_notice_post(post_id, payload, conn, me, post_visibility_status):
    post = conn.execute("SELECT * FROM posts WHERE id = ?", (post_id,)).fetchone()
    if not post:
        return error_response("게시글을 찾을 수 없습니다.", 404)

    publish_at = (
        str(payload.get("publish_at", post["publish_at"] or "")).strip() or None
    )
    if publish_at and not parse_iso_datetime(publish_at):
        return error_response("publish_at은 ISO 형식이어야 합니다.", 400)
    status = post_visibility_status(publish_at)

    conn.execute(
        """
        UPDATE posts
        SET category = ?, title = ?, content = ?, is_pinned = ?, is_important = ?, publish_at = ?, status = ?,
            volunteer_start_date = ?, volunteer_end_date = ?, updated_at = ?
        WHERE id = ?
        """,
        (
            "notice",
            str(payload.get("title", post["title"])).strip(),
            str(payload.get("content", post["content"])),
            1 if bool(payload.get("is_pinned", bool(post["is_pinned"]))) else 0,
            1
            if bool(payload.get("is_important", bool(post["is_important"])))
            else 0,
            publish_at,
            status,
            str(
                payload.get(
                    "volunteerStartDate",
                    post["volunteer_start_date"] or "",
                )
            ).strip()
            or None,
            str(
                payload.get(
                    "volunteerEndDate",
                    post["volunteer_end_date"] or "",
                )
            ).strip()
            or str(
                payload.get(
                    "volunteerStartDate",
                    post["volunteer_start_date"] or "",
                )
            ).strip()
            or None,
            now_iso(),
            post_id,
        ),
    )
    refreshed = conn.execute("SELECT * FROM posts WHERE id = ?", (post_id,)).fetchone()
    if refreshed:
        sync_notice_linked_calendar(conn, refreshed)
    log_audit(conn, "update_post", "post", post_id, me["id"])
    return None


def delete_notice_post(post_id, conn, me):
    from weave.files import delete_file_if_unreferenced, remove_file_safely, upload_url_to_path

    post = conn.execute("SELECT * FROM posts WHERE id = ?", (post_id,)).fetchone()
    if not post:
        return error_response("게시글을 찾을 수 없습니다.", 404)
    if not (
        role_at_least(me["role"], "EXECUTIVE")
        or int(post["author_id"] or 0) == int(me["id"])
    ):
        return error_response("작성자 또는 운영권한이 필요합니다.", 403)

    files = conn.execute(
        "SELECT * FROM post_files WHERE post_id = ?", (post_id,)
    ).fetchall()
    for file_row in files:
        conn.execute("DELETE FROM post_files WHERE id = ?", (file_row["id"],))
        delete_file_if_unreferenced(conn, file_row["stored_path"])
    remove_file_safely(upload_url_to_path(post["thumb_url"]))
    linked_event_rows = conn.execute(
        "SELECT id FROM events WHERE notice_post_id = ?",
        (post_id,),
    ).fetchall()
    linked_activity_rows = conn.execute(
        "SELECT id FROM activities WHERE notice_post_id = ?",
        (post_id,),
    ).fetchall()
    for row in linked_event_rows:
        _delete_event_with_relations(conn, int(row["id"]))
    for row in linked_activity_rows:
        _delete_activity_with_relations(conn, int(row["id"]))

    # Backward compatibility cleanup for older notice-linked activities without notice_post_id.
    volunteer_start = str(post["volunteer_start_date"] or "").strip()
    volunteer_end = str(post["volunteer_end_date"] or volunteer_start or "").strip()
    if volunteer_start:
        candidates = conn.execute(
            """
            SELECT id, title, place, start_at, end_at, created_by
            FROM activities
            WHERE title = ?
            """,
            (str(post["title"] or "").strip(),),
        ).fetchall()
        for row in candidates:
            place = str(row["place"] or "").strip()
            if place and place != "공지사항":
                continue
            if int(row["created_by"] or 0) != int(post["author_id"] or 0):
                continue
            start_at = str(row["start_at"] or "").strip()
            end_at = str(row["end_at"] or "").strip()
            if not start_at.startswith(volunteer_start):
                continue
            if volunteer_end and not end_at.startswith(volunteer_end):
                continue
            _delete_activity_with_relations(conn, int(row["id"]))

    conn.execute("DELETE FROM posts WHERE id = ?", (post_id,))
    log_audit(
        conn, "delete_post", "post", post_id, me["id"], {"category": post["category"]}
    )
    return None


def important_notices():
    conn = get_db_connection()
    rows = conn.execute(
        """
        SELECT id, title, publish_at, created_at
        FROM posts
        WHERE category = 'notice' AND is_important = 1
          AND (publish_at IS NULL OR publish_at <= ?)
        ORDER BY is_pinned DESC, COALESCE(publish_at, created_at) DESC
        LIMIT 3
        """,
        (now_iso(),),
    ).fetchall()
    conn.close()
    return success_response({"items": [dict(row) for row in rows]})
