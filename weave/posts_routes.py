import json
import os
from datetime import datetime

from weave.authz import (
    normalize_role,
    role_at_least,
    role_to_icon,
    role_to_label,
)
from weave import (
    error_messages,
    gallery_routes,
    notice_routes,
    post_template_service,
    qna_routes,
)
from weave import post_policy
from weave.core import (
    UPLOAD_DIR,
    build_annual_report,
    get_cache,
    get_current_user_row,
    get_db_connection,
    invalidate_cache,
    jsonify,
    log_audit,
    post_visibility_status,
    record_user_activity,
    request,
    set_cache,
)
from weave.files import (
    delete_file_if_unreferenced,
    remove_file_safely,
    upload_url_to_path,
)
from weave.responses import (
    error_response,
    success_response,
)
from weave.time_utils import now_iso, parse_iso_datetime


def _invalidate_post_list_cache():
    for prefix in post_policy.CACHE_INVALIDATION_PREFIXES:
        invalidate_cache(prefix)


CATEGORY_CREATE_HANDLERS = {
    "notice": notice_routes.create_notice_post,
    "gallery": gallery_routes.create_gallery_post,
    "qna": qna_routes.create_qna_post,
}


CATEGORY_UPDATE_HANDLERS = {
    "notice": notice_routes.update_notice_post,
    "gallery": gallery_routes.update_gallery_post,
    "qna": qna_routes.update_qna_post,
}


CATEGORY_DELETE_HANDLERS = {
    "notice": notice_routes.delete_notice_post,
    "gallery": gallery_routes.delete_gallery_post,
    "qna": qna_routes.delete_qna_post,
}


CATEGORY_HANDLERS_BY_ACTION = {
    "create": CATEGORY_CREATE_HANDLERS,
    "update": CATEGORY_UPDATE_HANDLERS,
    "delete": CATEGORY_DELETE_HANDLERS,
}


def _resolve_category_handler(action, category):
    handlers = CATEGORY_HANDLERS_BY_ACTION.get(action, {})
    return handlers.get(str(category or "").strip().lower())


def _validate_supported_category(category):
    if not post_policy.is_creatable_category(category):
        return error_response(error_messages.POST_INVALID_CATEGORY, 400)
    return None


def get_press_kit():
    return success_response(
        {
            "ok": True,
            "logoGuide": "로고는 기본 비율을 유지하고, 주변 여백을 확보해 사용하세요.",
            "officialIntro": "고양시 청소년봉사단 위브는 지역사회 문제를 해결하기 위한 변화를 만드는 봉사 커뮤니티입니다.",
            "downloads": [
                {"label": "공식 로고", "url": "/logo.png"},
                {"label": "기관 소개문구", "url": "/api/press-kit"},
            ],
        }
    )


def list_rules_versions():
    conn = get_db_connection()
    rows = conn.execute(
        "SELECT id, version_tag, effective_date, summary, content, created_at FROM rules_versions ORDER BY id DESC"
    ).fetchall()
    conn.close()
    return success_response(
        {
            "ok": True,
            "items": [
                {
                    "id": row["id"],
                    "version": row["version_tag"],
                    "effectiveDate": row["effective_date"],
                    "summary": row["summary"],
                    "content": row["content"],
                    "createdAt": row["created_at"],
                }
                for row in rows
            ],
        }
    )


def create_rules_version():
    payload = request.get_json(silent=True) or {}
    version = str(payload.get("version", "")).strip()
    effective_date = str(payload.get("effectiveDate", "")).strip()
    summary = str(payload.get("summary", "")).strip()
    content = str(payload.get("content", "")).strip()

    if not version or not effective_date or not summary:
        return error_response("version/effectiveDate/summary는 필수입니다.", 400)

    conn = get_db_connection()
    conn.execute(
        "INSERT INTO rules_versions (version_tag, effective_date, summary, content, created_at) VALUES (?, ?, ?, ?, ?)",
        (version, effective_date, summary, content, now_iso()),
    )
    conn.commit()
    conn.close()
    return success_response({"ok": True, "message": "개정 이력이 기록되었습니다."})


def get_annual_report(year):
    conn = get_db_connection()
    data = build_annual_report(conn, year)
    conn.execute(
        """
        INSERT INTO annual_reports (report_year, total_activities, total_hours, total_participants, impact_metric, created_at, updated_at)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(report_year) DO UPDATE SET
            total_activities = excluded.total_activities,
            total_hours = excluded.total_hours,
            total_participants = excluded.total_participants,
            impact_metric = excluded.impact_metric,
            updated_at = excluded.updated_at
        """,
        (
            year,
            data["totalActivities"],
            data["totalHours"],
            data["totalParticipants"],
            data["impact"],
            now_iso(),
            now_iso(),
        ),
    )
    conn.commit()
    conn.close()
    return success_response({"ok": True, "report": data})


def get_templates():
    return success_response(
        {
            "ok": True,
            "items": post_template_service.list_template_items(),
        }
    )


def generate_template():
    payload = request.get_json(silent=True) or {}
    template_type = str(payload.get("type", "")).strip().lower()
    title = post_template_service.default_template_title(payload.get("title"))
    content = post_template_service.build_template_content(template_type, title)
    if not content:
        return error_response(error_messages.POST_TEMPLATE_UNSUPPORTED, 400)
    return success_response({"ok": True, "content": content})


def list_posts():
    page = max(1, int(request.args.get("page", "1") or 1))
    page_size = min(100, max(1, int(request.args.get("pageSize", "10") or 10)))
    offset = (page - 1) * page_size
    category = (
        str(request.args.get("type", request.args.get("category", ""))).strip().lower()
    )
    keyword = str(request.args.get("query", request.args.get("q", ""))).strip()
    include_scheduled = str(
        request.args.get("include_scheduled", "")
    ).strip().lower() in {"1", "true", "yes"}

    conn = get_db_connection()
    me = get_current_user_row(conn)
    can_include_scheduled = post_policy.can_include_scheduled_posts(
        me, include_scheduled
    )

    where = ["1=1"]
    params = []
    mapped = post_policy.normalize_list_category(category)
    if mapped:
        where.append("p.category = ?")
        params.append(mapped)
    if keyword:
        where.append("(p.title LIKE ? OR p.content LIKE ?)")
        params.extend([f"%{keyword}%", f"%{keyword}%"])
    if not can_include_scheduled:
        where.append("(p.publish_at IS NULL OR p.publish_at <= ?)")
        params.append(now_iso())

    where_sql = " AND ".join(where)
    should_cache = post_policy.should_cache_post_list(category, keyword)
    cache_key = post_policy.post_list_cache_key(
        category, page, page_size, can_include_scheduled
    )
    if should_cache:
        cached = get_cache(cache_key)
        if cached is not None:
            conn.close()
            return success_response(cached)

    total = conn.execute(
        f"SELECT COUNT(*) AS c FROM posts p WHERE {where_sql}", params
    ).fetchone()["c"]
    rows = conn.execute(
        f"""
         SELECT p.*, u.username AS author_username, u.nickname AS author_nickname, u.role AS author_role,
               (SELECT COUNT(*) FROM post_files pf WHERE pf.post_id = p.id) AS file_count
        FROM posts p
        LEFT JOIN users u ON u.id = p.author_id
        WHERE {where_sql}
         ORDER BY CASE WHEN p.category = 'notice' THEN p.is_important ELSE 0 END DESC,
               CASE WHEN p.category = 'notice' THEN p.is_pinned ELSE 0 END DESC,
                 COALESCE(p.publish_at, p.created_at) DESC,
                 p.id DESC
        LIMIT ? OFFSET ?
        """,
        [*params, page_size, offset],
    ).fetchall()
    conn.close()

    items = [
        {
            "id": row["id"],
            "category": row["category"],
            "type": row["category"],
            "title": row["title"],
            "content": row["content"],
            "is_pinned": bool(row["is_pinned"]),
            "is_important": bool(row["is_important"]),
            "publish_at": row["publish_at"],
            "status": row["status"],
            "image_url": row["image_url"],
            "thumb_url": row["thumb_url"],
            "volunteerStartDate": row["volunteer_start_date"],
            "volunteerEndDate": row["volunteer_end_date"],
            "author_id": row["author_id"],
            "author_name": row["author_username"],
            "author": {
                "nickname": row["author_nickname"] or row["author_username"],
                "role": normalize_role(row["author_role"]),
                "role_label": role_to_label(row["author_role"]),
                "role_icon": role_to_icon(row["author_role"]),
            },
            "created_at": row["created_at"],
            "updated_at": row["updated_at"],
            "file_count": row["file_count"],
        }
        for row in rows
    ]
    data = {
        "items": items,
        "pagination": {
            "total": int(total or 0),
            "page": page,
            "pageSize": page_size,
            "totalPages": max(1, (int(total or 0) + page_size - 1) // page_size),
        },
    }
    if should_cache:
        set_cache(cache_key, data)
    return success_response(data)


def create_post():
    payload = request.get_json(silent=True) or {}
    category = post_policy.normalize_create_category(payload.get("category", ""))
    category_error = _validate_supported_category(category)
    if category_error:
        return category_error
    title = str(payload.get("title", "")).strip()
    if not title:
        return error_response(error_messages.POST_TITLE_REQUIRED, 400)
    publish_at = str(payload.get("publish_at", "")).strip() or None
    if publish_at and not parse_iso_datetime(publish_at):
        return error_response(error_messages.POST_PUBLISH_AT_INVALID, 400)
    conn = get_db_connection()
    me = get_current_user_row(conn)
    if not me:
        conn.close()
        return error_response(error_messages.UNAUTHORIZED, 401)
    if me["status"] == "suspended":
        conn.close()
        return error_response(error_messages.POST_SUSPENDED_FORBIDDEN, 403)

    permission_error = post_policy.create_permission_error(category, me)
    if permission_error:
        conn.close()
        return error_response(permission_error, 403)

    create_handler = _resolve_category_handler("create", category)
    if create_handler:
        post_id, err = create_handler(payload, conn, me, post_visibility_status)
        if err:
            conn.close()
            return err
    else:
        publish_at = str(payload.get("publish_at", "")).strip() or None
        if publish_at and not parse_iso_datetime(publish_at):
            conn.close()
            return error_response(error_messages.POST_PUBLISH_AT_INVALID, 400)
        status = post_visibility_status(publish_at)
        volunteer_start = str(payload.get("volunteerStartDate", "")).strip() or None
        volunteer_end = (
            str(payload.get("volunteerEndDate", "")).strip() or volunteer_start
        )

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
                category,
                title,
                str(payload.get("content", "")),
                1 if bool(payload.get("is_pinned", False)) else 0,
                1 if bool(payload.get("is_important", False)) else 0,
                publish_at,
                status,
                str(payload.get("image_url", "")).strip(),
                str(payload.get("thumb_url", "")).strip(),
                volunteer_start,
                volunteer_end,
                me["id"],
                now_iso(),
                now_iso(),
            ),
        )
        post_id = cur.lastrowid
        log_audit(
            conn, "create_post", "post", post_id, me["id"], {"category": category}
        )
        record_user_activity(
            conn, me["id"], "post_create", "post", post_id, {"category": category}
        )

    conn.commit()
    conn.close()
    _invalidate_post_list_cache()
    return success_response({"post_id": post_id}, 201)


def get_post(post_id):
    conn = get_db_connection()
    me = get_current_user_row(conn)
    row = conn.execute(
        """
        SELECT p.*, u.username AS author_username, u.nickname AS author_nickname, u.role AS author_role
        FROM posts p
        LEFT JOIN users u ON u.id = p.author_id
        WHERE p.id = ?
        """,
        (post_id,),
    ).fetchone()
    if not row:
        conn.close()
        return error_response(error_messages.POST_NOT_FOUND, 404)

    can_view_scheduled = post_policy.can_view_scheduled_post_detail(me)
    publish_at_dt = parse_iso_datetime(row["publish_at"]) if row["publish_at"] else None
    if not can_view_scheduled and publish_at_dt and publish_at_dt > datetime.now():
        conn.close()
        return error_response(error_messages.POST_NOT_FOUND, 404)

    comments = conn.execute(
        """
        SELECT c.*, u.nickname, u.username, u.role
        FROM comments c
        JOIN users u ON u.id = c.user_id
        WHERE c.post_id = ?
        ORDER BY c.created_at ASC
        """,
        (post_id,),
    ).fetchall()
    recommend_count = conn.execute(
        "SELECT COUNT(*) AS c FROM recommends WHERE post_id = ?", (post_id,)
    ).fetchone()["c"]
    files = conn.execute(
        """
        SELECT id, original_name, mime_type, size, uploaded_at, stored_path
        FROM post_files
        WHERE post_id = ? AND (expires_at IS NULL OR expires_at = '' OR expires_at > ?)
        ORDER BY id DESC
        """,
        (post_id, now_iso()),
    ).fetchall()
    conn.close()

    file_items = []
    for f in files:
        relative_path = os.path.relpath(f["stored_path"], UPLOAD_DIR).replace("\\", "/")
        file_url = f"/uploads/{relative_path}"
        file_items.append(
            {
                "id": f["id"],
                "original_name": f["original_name"],
                "mime_type": f["mime_type"],
                "size": f["size"],
                "uploaded_at": f["uploaded_at"],
                "file_url": file_url,
            }
        )

    return success_response(
        {
            "id": row["id"],
            "type": row["category"],
            "title": row["title"],
            "content": row["content"],
            "is_pinned": bool(row["is_pinned"]),
            "is_important": bool(row["is_important"]),
            "publish_at": row["publish_at"],
            "status": row["status"],
            "image_url": row["image_url"],
            "thumb_url": row["thumb_url"],
            "volunteerStartDate": row["volunteer_start_date"],
            "volunteerEndDate": row["volunteer_end_date"],
            "author": {
                "nickname": row["author_nickname"] or row["author_username"],
                "role": normalize_role(row["author_role"]),
                "role_label": role_to_label(row["author_role"]),
                "role_icon": role_to_icon(row["author_role"]),
            },
            "recommend_count": int(recommend_count or 0),
            "comments": [
                {
                    "id": c["id"],
                    "content": c["content"],
                    "parent_id": c["parent_id"],
                    "created_at": c["created_at"],
                    "author": {
                        "nickname": c["nickname"] or c["username"],
                        "role": normalize_role(c["role"]),
                        "role_label": role_to_label(c["role"]),
                        "role_icon": role_to_icon(c["role"]),
                    },
                }
                for c in comments
            ],
            "files": file_items,
        }
    )


def update_post(post_id):
    payload = request.get_json(silent=True) or {}
    conn = get_db_connection()
    me = get_current_user_row(conn)
    if not me:
        conn.close()
        return error_response(error_messages.UNAUTHORIZED, 401)
    post = conn.execute("SELECT * FROM posts WHERE id = ?", (post_id,)).fetchone()
    if not post:
        conn.close()
        return error_response(error_messages.POST_NOT_FOUND, 404)

    if not (
        role_at_least(me["role"], "EXECUTIVE")
        or int(post["author_id"] or 0) == int(me["id"])
    ):
        conn.close()
        return error_response(error_messages.POST_AUTHOR_OR_EXEC_REQUIRED, 403)

    category = str(payload.get("category", post["category"]))
    if not category:
        conn.close()
        return error_response(error_messages.POST_CATEGORY_REQUIRED, 400)
    next_category = post_policy.normalize_create_category(category)

    category_error = _validate_supported_category(next_category)
    if category_error:
        conn.close()
        return category_error

    permission_error = post_policy.update_permission_error(next_category, me)
    if permission_error:
        conn.close()
        return error_response(permission_error, 403)

    update_handler = _resolve_category_handler("update", next_category)
    if update_handler:
        err = update_handler(post_id, payload, conn, me, post_visibility_status)
    else:
        publish_at = (
            str(payload.get("publish_at", post["publish_at"] or "")).strip() or None
        )
        if publish_at and not parse_iso_datetime(publish_at):
            conn.close()
            return error_response(error_messages.POST_PUBLISH_AT_INVALID, 400)
        status = post_visibility_status(publish_at)

        conn.execute(
            """
            UPDATE posts
            SET category = ?, title = ?, content = ?, is_pinned = ?, publish_at = ?, status = ?, updated_at = ?
            WHERE id = ?
            """,
            (
                category,
                str(payload.get("title", post["title"])).strip(),
                str(payload.get("content", post["content"])),
                1 if bool(payload.get("is_pinned", bool(post["is_pinned"]))) else 0,
                publish_at,
                status,
                now_iso(),
                post_id,
            ),
        )
        log_audit(conn, "update_post", "post", post_id, me["id"])
        err = None
    if err:
        conn.close()
        return err
    conn.commit()
    conn.close()
    _invalidate_post_list_cache()
    return success_response({"post_id": post_id})


def delete_post(post_id):
    conn = get_db_connection()
    me = get_current_user_row(conn)
    if not me:
        conn.close()
        return error_response(error_messages.UNAUTHORIZED, 401)
    post = conn.execute("SELECT * FROM posts WHERE id = ?", (post_id,)).fetchone()
    if not post:
        conn.close()
        return error_response(error_messages.POST_NOT_FOUND, 404)
    if not (
        role_at_least(me["role"], "EXECUTIVE")
        or int(post["author_id"] or 0) == int(me["id"])
    ):
        conn.close()
        return error_response(error_messages.POST_AUTHOR_OR_EXEC_REQUIRED, 403)
    category = str(post["category"] or "").lower()
    delete_handler = _resolve_category_handler("delete", category)
    if delete_handler:
        err = delete_handler(post_id, conn, me)
    else:
        files = conn.execute(
            "SELECT * FROM post_files WHERE post_id = ?", (post_id,)
        ).fetchall()
        for file_row in files:
            conn.execute("DELETE FROM post_files WHERE id = ?", (file_row["id"],))
            delete_file_if_unreferenced(conn, file_row["stored_path"])
        remove_file_safely(upload_url_to_path(post["thumb_url"]))
        conn.execute("DELETE FROM posts WHERE id = ?", (post_id,))
        log_audit(
            conn,
            "delete_post",
            "post",
            post_id,
            me["id"],
            {"category": post["category"]},
        )
        err = None
    if err:
        conn.close()
        return err
    conn.commit()
    conn.close()
    _invalidate_post_list_cache()
    return success_response({"deleted": True})


def recommend_post(post_id):
    conn = get_db_connection()
    me = get_current_user_row(conn)
    if not me:
        conn.close()
        return error_response(error_messages.UNAUTHORIZED, 401)
    post = conn.execute("SELECT id FROM posts WHERE id = ?", (post_id,)).fetchone()
    if not post:
        conn.close()
        return error_response(error_messages.POST_NOT_FOUND, 404)

    existing = conn.execute(
        "SELECT id FROM recommends WHERE post_id = ? AND user_id = ?",
        (post_id, me["id"]),
    ).fetchone()
    if existing:
        conn.close()
        return error_response(error_messages.POST_ALREADY_RECOMMENDED, 409)

    conn.execute(
        "INSERT INTO recommends (post_id, user_id, created_at) VALUES (?, ?, ?)",
        (post_id, me["id"], now_iso()),
    )
    log_audit(conn, "recommend_post", "post", post_id, me["id"])
    conn.commit()
    count = conn.execute(
        "SELECT COUNT(*) AS c FROM recommends WHERE post_id = ?", (post_id,)
    ).fetchone()["c"]
    conn.close()
    return success_response({"recommend_count": int(count or 0)})



