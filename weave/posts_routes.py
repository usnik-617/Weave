import json
import os
from datetime import datetime
from pathlib import Path

from werkzeug.utils import secure_filename

from weave.core import (
    UPLOAD_DIR,
    save_uploaded_file,
    build_annual_report,
    delete_file_if_unreferenced,
    error_response,
    get_cache,
    get_current_user_row,
    get_db_connection,
    invalidate_cache,
    jsonify,
    log_audit,
    make_thumbnail_like,
    normalize_role,
    now_iso,
    parse_iso_datetime,
    post_visibility_status,
    record_user_activity,
    remove_file_safely,
    request,
    role_at_least,
    role_to_icon,
    role_to_label,
    set_cache,
    success_response,
    success_response_legacy,
    upload_url_to_path,
)


ABOUT_SECTION_KEYS = {
    "executives",
    "history",
    "logo",
    "relatedsites",
    "rules",
    "awards",
    "fees",
}

CONTENT_BLOCK_KEYS = {
    "activities_overview",
    "join",
    "home_stats",
}


def _stored_path_to_upload_url(stored_path):
    rel_path = os.path.relpath(stored_path, UPLOAD_DIR).replace("\\", "/")
    return f"/uploads/{rel_path}"


def list_about_sections():
    conn = get_db_connection()
    rows = conn.execute(
        """
        SELECT section_key, content_html, image_url, updated_at, updated_by
        FROM about_sections
        ORDER BY section_key ASC
        """
    ).fetchall()
    conn.close()

    items = {}
    for row in rows:
        items[row["section_key"]] = {
            "contentHtml": row["content_html"] or "",
            "imageUrl": row["image_url"] or "",
            "updatedAt": row["updated_at"],
            "updatedBy": row["updated_by"],
        }
    return success_response({"items": items})


def update_about_section():
    payload = request.get_json(silent=True) or {}
    section_key = str(payload.get("key", "")).strip().lower()
    content_html = str(payload.get("contentHtml", ""))
    image_url = str(payload.get("imageUrl", "")).strip()

    if section_key not in ABOUT_SECTION_KEYS:
        return error_response("유효하지 않은 소개 탭 키입니다.", 400)

    conn = get_db_connection()
    me = get_current_user_row(conn)
    if not me:
        conn.close()
        return error_response("Unauthorized", 401)
    if me["status"] != "active" or not role_at_least(me["role"], "EXECUTIVE"):
        conn.close()
        return error_response("운영진 이상만 수정할 수 있습니다.", 403)

    conn.execute(
        """
        INSERT INTO about_sections (section_key, content_html, image_url, updated_at, updated_by)
        VALUES (?, ?, ?, ?, ?)
        ON CONFLICT(section_key) DO UPDATE SET
            content_html = excluded.content_html,
            image_url = excluded.image_url,
            updated_at = excluded.updated_at,
            updated_by = excluded.updated_by
        """,
        (section_key, content_html, image_url, now_iso(), me["id"]),
    )
    conn.commit()
    conn.close()
    return success_response({"ok": True})


def upload_about_section_image():
    section_key = str(request.form.get("key", "")).strip().lower()
    if section_key not in ABOUT_SECTION_KEYS:
        return error_response("유효하지 않은 소개 탭 키입니다.", 400)

    conn = get_db_connection()
    me = get_current_user_row(conn)
    if not me:
        conn.close()
        return error_response("Unauthorized", 401)
    if me["status"] != "active" or not role_at_least(me["role"], "EXECUTIVE"):
        conn.close()
        return error_response("운영진 이상만 수정할 수 있습니다.", 403)

    file_storage = request.files.get("file")
    if not file_storage:
        conn.close()
        return error_response("이미지 파일이 필요합니다.", 400)

    original_name = secure_filename(str(file_storage.filename or ""))
    extension = Path(original_name).suffix.lower()
    mime_type = str(file_storage.mimetype or "").lower()
    image_exts = {".jpg", ".jpeg", ".png", ".webp", ".gif"}
    image_mimes = {
        "image/jpeg",
        "image/png",
        "image/webp",
        "image/gif",
    }
    if extension not in image_exts or mime_type not in image_mimes:
        conn.close()
        return error_response("소개 탭 이미지는 jpg/jpeg/png/webp/gif만 업로드할 수 있습니다.", 400)

    file_info, err = save_uploaded_file(file_storage)
    if err:
        conn.close()
        return error_response(err, 400)
    if not file_info:
        conn.close()
        return error_response("파일 처리에 실패했습니다.", 400)

    image_url = _stored_path_to_upload_url(file_info["stored_path"])
    conn.execute(
        """
        INSERT INTO about_sections (section_key, content_html, image_url, updated_at, updated_by)
        VALUES (?, ?, ?, ?, ?)
        ON CONFLICT(section_key) DO UPDATE SET
            image_url = excluded.image_url,
            updated_at = excluded.updated_at,
            updated_by = excluded.updated_by
        """,
        (section_key, "", image_url, now_iso(), me["id"]),
    )
    conn.commit()
    conn.close()
    return success_response({"imageUrl": image_url}, 201)


def list_content_blocks():
    conn = get_db_connection()
    rows = conn.execute(
        """
        SELECT section_key, content_html, updated_at, updated_by
        FROM about_sections
        WHERE section_key IN (?, ?, ?)
        ORDER BY section_key ASC
        """,
        ("activities_overview", "join", "home_stats"),
    ).fetchall()
    conn.close()

    items = {}
    for row in rows:
        items[row["section_key"]] = {
            "contentHtml": row["content_html"] or "",
            "updatedAt": row["updated_at"],
            "updatedBy": row["updated_by"],
        }
    return success_response({"items": items})


def update_content_block():
    payload = request.get_json(silent=True) or {}
    block_key = str(payload.get("key", "")).strip().lower()
    content_html = str(payload.get("contentHtml", ""))

    if block_key not in CONTENT_BLOCK_KEYS:
        return error_response("유효하지 않은 콘텐츠 키입니다.", 400)

    conn = get_db_connection()
    me = get_current_user_row(conn)
    if not me:
        conn.close()
        return error_response("Unauthorized", 401)
    if me["status"] != "active":
        conn.close()
        return error_response("운영진 이상만 수정할 수 있습니다.", 403)

    if block_key == "home_stats":
        is_admin_flag = bool(me["is_admin"]) if "is_admin" in me.keys() else False
        if not (role_at_least(me["role"], "ADMIN") or is_admin_flag):
            conn.close()
            return error_response("운영자만 홈 통계를 수정할 수 있습니다.", 403)
    elif not role_at_least(me["role"], "EXECUTIVE"):
        conn.close()
        return error_response("운영진 이상만 수정할 수 있습니다.", 403)

    conn.execute(
        """
        INSERT INTO about_sections (section_key, content_html, image_url, updated_at, updated_by)
        VALUES (?, ?, ?, ?, ?)
        ON CONFLICT(section_key) DO UPDATE SET
            content_html = excluded.content_html,
            updated_at = excluded.updated_at,
            updated_by = excluded.updated_by
        """,
        (block_key, content_html, "", now_iso(), me["id"]),
    )
    conn.commit()
    conn.close()
    return success_response({"ok": True})


def list_gallery_albums():
    conn = get_db_connection()
    rows = conn.execute("SELECT * FROM gallery_albums ORDER BY id DESC").fetchall()
    conn.close()
    return success_response_legacy(
        {
            "ok": True,
            "items": [
                {
                    "id": row["id"],
                    "title": row["title"],
                    "activityId": row["activity_id"],
                    "visibility": row["visibility"],
                    "portraitConsent": bool(row["portrait_consent"]),
                    "createdAt": row["created_at"],
                }
                for row in rows
            ],
        }
    )


def create_gallery_album():
    payload = request.get_json(silent=True) or {}
    title = str(payload.get("title", "")).strip()
    visibility = str(payload.get("visibility", "internal")).strip().lower()
    portrait_consent = bool(payload.get("portraitConsent", False))
    if not title:
        return jsonify({"ok": False, "message": "앨범 제목이 필요합니다."}), 400
    if visibility not in ("public", "private", "internal"):
        return jsonify({"ok": False, "message": "공개 범위가 올바르지 않습니다."}), 400
    if not portrait_consent:
        return jsonify({"ok": False, "message": "초상권 동의가 필요합니다."}), 400

    conn = get_db_connection()
    me = get_current_user_row(conn)
    if not me:
        conn.close()
        return jsonify({"ok": False, "message": "로그인이 필요합니다."}), 401
    cur = conn.cursor()
    cur.execute(
        "INSERT INTO gallery_albums (title, activity_id, visibility, portrait_consent, created_by, created_at) VALUES (?, ?, ?, ?, ?, ?)",
        (
            title,
            payload.get("activityId"),
            visibility,
            1 if portrait_consent else 0,
            me["id"],
            now_iso(),
        ),
    )
    album_id = cur.lastrowid
    conn.commit()
    conn.close()
    return success_response_legacy({"ok": True, "albumId": album_id})


def add_gallery_photos(album_id):
    payload = request.get_json(silent=True) or {}
    photos = payload.get("photos", [])
    if not isinstance(photos, list) or not photos:
        return jsonify({"ok": False, "message": "photos 배열이 필요합니다."}), 400

    conn = get_db_connection()
    album = conn.execute(
        "SELECT id FROM gallery_albums WHERE id = ?", (album_id,)
    ).fetchone()
    if not album:
        conn.close()
        return jsonify({"ok": False, "message": "앨범을 찾을 수 없습니다."}), 404

    created = 0
    for photo in photos:
        image_url = str(photo.get("imageUrl", "")).strip()
        if not image_url:
            continue
        title = str(photo.get("title", "")).strip()
        thumb = make_thumbnail_like(image_url)
        conn.execute(
            "INSERT INTO gallery_photos (album_id, title, image_url, thumbnail_url, created_at) VALUES (?, ?, ?, ?, ?)",
            (album_id, title, image_url, thumb, now_iso()),
        )
        created += 1

    conn.commit()
    conn.close()
    return success_response_legacy({"ok": True, "created": created})


def delete_gallery_photo(photo_id):
    conn = get_db_connection()
    me = get_current_user_row(conn)
    if not me:
        conn.close()
        return error_response("Unauthorized", 401)

    row = conn.execute(
        "SELECT * FROM gallery_photos WHERE id = ?", (photo_id,)
    ).fetchone()
    if not row:
        conn.close()
        return error_response("사진을 찾을 수 없습니다.", 404)

    remove_file_safely(upload_url_to_path(row["image_url"]))
    remove_file_safely(upload_url_to_path(row["thumbnail_url"]))

    conn.execute("DELETE FROM gallery_photos WHERE id = ?", (photo_id,))
    conn.commit()
    conn.close()
    log_audit(me["id"], "delete_gallery_photo", "gallery_photo", photo_id)
    return success_response({"ok": True})


def get_press_kit():
    return success_response_legacy(
        {
            "ok": True,
            "logoGuide": "로고는 원본 비율을 유지하고, 주변 여백을 확보해 사용하세요.",
            "officialIntro": "남양주청년봉사단 위브는 지역과 청년을 연결해 지속 가능한 변화를 만드는 청년 봉사 커뮤니티입니다.",
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
    return success_response_legacy(
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
        return (
            jsonify(
                {"ok": False, "message": "version/effectiveDate/summary는 필수입니다."}
            ),
            400,
        )

    conn = get_db_connection()
    conn.execute(
        "INSERT INTO rules_versions (version_tag, effective_date, summary, content, created_at) VALUES (?, ?, ?, ?, ?)",
        (version, effective_date, summary, content, now_iso()),
    )
    conn.commit()
    conn.close()
    return success_response_legacy(
        {"ok": True, "message": "개정 이력이 등록되었습니다."}
    )


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
    return success_response_legacy({"ok": True, "report": data})


def get_templates():
    return success_response_legacy(
        {
            "ok": True,
            "items": [
                {"type": "notice", "label": "공지 템플릿"},
                {"type": "review", "label": "활동 후기 템플릿"},
                {"type": "minutes", "label": "회의록 템플릿"},
            ],
        }
    )


def generate_template():
    payload = request.get_json(silent=True) or {}
    template_type = str(payload.get("type", "")).strip().lower()
    title = str(payload.get("title", "제목"))

    templates = {
        "notice": f"[공지] {title}\n\n1) 일정\n2) 장소\n3) 준비물\n4) 유의사항",
        "review": f"[활동후기] {title}\n\n- 활동 개요\n- 참여 소감\n- 다음 개선점",
        "minutes": f"[회의록] {title}\n\n- 참석자\n- 논의 안건\n- 결정 사항\n- 액션 아이템",
    }

    content = templates.get(template_type)
    if not content:
        return jsonify({"ok": False, "message": "지원하지 않는 템플릿입니다."}), 400
    return success_response_legacy({"ok": True, "content": content})


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
    can_include_scheduled = bool(
        me and role_at_least(me["role"], "VICE_LEADER") and include_scheduled
    )

    where = ["1=1"]
    params = []
    if category in ("notice", "faq", "qna", "gallery", "review", "recruit"):
        mapped = "review" if category == "faq" else category
        where.append("p.category = ?")
        params.append(mapped)
    if keyword:
        where.append("(p.title LIKE ? OR p.content LIKE ?)")
        params.extend([f"%{keyword}%", f"%{keyword}%"])
    if not can_include_scheduled:
        where.append("(p.publish_at IS NULL OR p.publish_at <= ?)")
        params.append(now_iso())

    where_sql = " AND ".join(where)
    should_cache = category in ("notice", "gallery") and not keyword
    cache_key = (
        f"posts:list:{category}:{page}:{page_size}:{int(bool(can_include_scheduled))}"
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
    category = str(payload.get("category", "")).strip().lower()
    if category not in ("notice", "review", "recruit", "qna", "gallery"):
        return error_response(
            "type(category)는 notice|review|recruit|qna|gallery만 허용됩니다.", 400
        )
    title = str(payload.get("title", "")).strip()
    if not title:
        return error_response("title은 필수입니다.", 400)
    publish_at = str(payload.get("publish_at", "")).strip() or None
    if publish_at and not parse_iso_datetime(publish_at):
        return error_response("publish_at은 ISO 형식이어야 합니다.", 400)
    status = post_visibility_status(publish_at)

    conn = get_db_connection()
    me = get_current_user_row(conn)
    if not me:
        conn.close()
        return error_response("Unauthorized", 401)
    if me["status"] == "suspended":
        conn.close()
        return error_response("정지된 계정은 게시글을 작성할 수 없습니다.", 403)

    if category in ("notice", "gallery") and not role_at_least(me["role"], "EXECUTIVE"):
        conn.close()
        return error_response("공지/갤러리 작성은 임원 이상만 가능합니다.", 403)

    if category == "qna" and not role_at_least(me["role"], "GENERAL"):
        conn.close()
        return error_response("Q&A 작성 권한이 없습니다.", 403)

    volunteer_start = str(payload.get("volunteerStartDate", "")).strip() or None
    volunteer_end = str(payload.get("volunteerEndDate", "")).strip() or volunteer_start

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

    if category == "notice" and volunteer_start:
        activity_start = f"{volunteer_start}T09:00:00"
        activity_end = f"{(volunteer_end or volunteer_start)}T18:00:00"
        conn.execute(
            """
            INSERT INTO activities (
                title, description, start_at, end_at, place, supplies, gather_time,
                manager_name, recruitment_limit, created_by, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
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
                me["id"],
                now_iso(),
            ),
        )

    log_audit(conn, "create_post", "post", post_id, me["id"], {"category": category})
    record_user_activity(
        conn, me["id"], "post_create", "post", post_id, {"category": category}
    )
    conn.commit()
    conn.close()
    invalidate_cache("posts:list:notice:")
    invalidate_cache("posts:list:gallery:")
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
        return error_response("게시글을 찾을 수 없습니다.", 404)

    can_view_scheduled = role_at_least(me["role"], "VICE_LEADER") if me else False
    publish_at_dt = parse_iso_datetime(row["publish_at"]) if row["publish_at"] else None
    if not can_view_scheduled and publish_at_dt and publish_at_dt > datetime.now():
        conn.close()
        return error_response("게시글을 찾을 수 없습니다.", 404)

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
        return error_response("Unauthorized", 401)
    post = conn.execute("SELECT * FROM posts WHERE id = ?", (post_id,)).fetchone()
    if not post:
        conn.close()
        return error_response("게시글을 찾을 수 없습니다.", 404)
    category = str(payload.get("category", post["category"]))
    if not category:
        conn.close()
        return error_response("category는 필수입니다.", 400)
    publish_at = (
        str(payload.get("publish_at", post["publish_at"] or "")).strip() or None
    )
    if publish_at and not parse_iso_datetime(publish_at):
        conn.close()
        return error_response("publish_at은 ISO 형식이어야 합니다.", 400)
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
    conn.commit()
    conn.close()
    invalidate_cache("posts:list:notice:")
    invalidate_cache("posts:list:gallery:")
    return success_response({"post_id": post_id})


def delete_post(post_id):
    conn = get_db_connection()
    me = get_current_user_row(conn)
    if not me:
        conn.close()
        return error_response("Unauthorized", 401)
    post = conn.execute("SELECT * FROM posts WHERE id = ?", (post_id,)).fetchone()
    if not post:
        conn.close()
        return error_response("게시글을 찾을 수 없습니다.", 404)
    if not (
        role_at_least(me["role"], "EXECUTIVE")
        or int(post["author_id"] or 0) == int(me["id"])
    ):
        conn.close()
        return error_response("작성자 또는 운영권한이 필요합니다.", 403)
    files = conn.execute(
        "SELECT * FROM post_files WHERE post_id = ?", (post_id,)
    ).fetchall()
    for file_row in files:
        conn.execute("DELETE FROM post_files WHERE id = ?", (file_row["id"],))
        delete_file_if_unreferenced(conn, file_row["stored_path"])
    remove_file_safely(upload_url_to_path(post["thumb_url"]))
    conn.execute("DELETE FROM posts WHERE id = ?", (post_id,))
    log_audit(
        conn, "delete_post", "post", post_id, me["id"], {"category": post["category"]}
    )
    conn.commit()
    conn.close()
    invalidate_cache("posts:list:notice:")
    invalidate_cache("posts:list:gallery:")
    return success_response({"deleted": True})


def create_post_comment(post_id):
    payload = request.get_json(silent=True) or {}
    content = str(payload.get("content", "")).strip()
    if not content:
        return error_response("댓글 내용을 입력해주세요.", 400)

    conn = get_db_connection()
    me = get_current_user_row(conn)
    if not me:
        conn.close()
        return error_response("Unauthorized", 401)
    if me["status"] == "suspended":
        conn.close()
        return error_response("정지된 계정은 댓글을 작성할 수 없습니다.", 403)
    post = conn.execute(
        "SELECT id, category FROM posts WHERE id = ?", (post_id,)
    ).fetchone()
    if not post:
        conn.close()
        return error_response("게시글을 찾을 수 없습니다.", 404)
    if post["category"] in ("notice", "gallery") and not role_at_least(
        me["role"], "MEMBER"
    ):
        conn.close()
        return error_response("공지/갤러리 댓글은 단원 이상만 가능합니다.", 403)

    cur = conn.cursor()
    cur.execute(
        """
        INSERT INTO comments (post_id, user_id, content, parent_id, created_at, updated_at)
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        (
            post_id,
            me["id"],
            content,
            payload.get("parent_id"),
            now_iso(),
            now_iso(),
        ),
    )
    comment_id = cur.lastrowid
    log_audit(conn, "create_comment", "post", post_id, me["id"])
    record_user_activity(
        conn, me["id"], "comment_create", "comment", comment_id, {"post_id": post_id}
    )
    conn.commit()
    conn.close()
    return success_response({"ok": True}, 201)


def recommend_post(post_id):
    conn = get_db_connection()
    me = get_current_user_row(conn)
    if not me:
        conn.close()
        return error_response("Unauthorized", 401)
    post = conn.execute("SELECT id FROM posts WHERE id = ?", (post_id,)).fetchone()
    if not post:
        conn.close()
        return error_response("게시글을 찾을 수 없습니다.", 404)

    existing = conn.execute(
        "SELECT id FROM recommends WHERE post_id = ? AND user_id = ?",
        (post_id, me["id"]),
    ).fetchone()
    if existing:
        conn.close()
        return error_response("이미 추천하셨습니다.", 409)

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
