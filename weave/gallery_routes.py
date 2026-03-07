from weave.authz import role_at_least
from weave.core import get_current_user_row, get_db_connection, log_audit, request
from weave.files import remove_file_safely, upload_url_to_path
from weave.responses import error_response, success_response
from weave.time_utils import now_iso, parse_iso_datetime


def create_gallery_post(payload, conn, me, post_visibility_status):
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
            "gallery",
            title,
            str(payload.get("content", "")),
            1 if bool(payload.get("is_pinned", False)) else 0,
            1 if bool(payload.get("is_important", False)) else 0,
            publish_at,
            status,
            str(payload.get("image_url", "")).strip(),
            str(payload.get("thumb_url", "")).strip(),
            None,
            None,
            me["id"],
            now_iso(),
            now_iso(),
        ),
    )
    post_id = cur.lastrowid
    log_audit(conn, "create_post", "post", post_id, me["id"], {"category": "gallery"})
    from weave.core import record_user_activity

    record_user_activity(
        conn, me["id"], "post_create", "post", post_id, {"category": "gallery"}
    )
    return post_id, None


def update_gallery_post(post_id, payload, conn, me, post_visibility_status):
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
            volunteer_start_date = NULL, volunteer_end_date = NULL, updated_at = ?
        WHERE id = ?
        """,
        (
            "gallery",
            str(payload.get("title", post["title"])).strip(),
            str(payload.get("content", post["content"])),
            1 if bool(payload.get("is_pinned", bool(post["is_pinned"]))) else 0,
            1
            if bool(payload.get("is_important", bool(post["is_important"])))
            else 0,
            publish_at,
            status,
            now_iso(),
            post_id,
        ),
    )
    log_audit(conn, "update_post", "post", post_id, me["id"])
    return None


def delete_gallery_post(post_id, conn, me):
    from weave.files import delete_file_if_unreferenced

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
    conn.execute("DELETE FROM posts WHERE id = ?", (post_id,))
    log_audit(
        conn, "delete_post", "post", post_id, me["id"], {"category": post["category"]}
    )
    return None


def list_gallery_albums():
    conn = get_db_connection()
    rows = conn.execute("SELECT * FROM gallery_albums ORDER BY id DESC").fetchall()
    conn.close()
    return success_response(
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
        return error_response("앨범 제목이 필요합니다.", 400)
    if visibility not in ("public", "private", "internal"):
        return error_response("공개 범위가 올바르지 않습니다.", 400)
    if not portrait_consent:
        return error_response("초상권 동의가 필요합니다.", 400)

    conn = get_db_connection()
    me = get_current_user_row(conn)
    if not me:
        conn.close()
        return error_response("로그인이 필요합니다.", 401)
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
    return success_response({"ok": True, "albumId": album_id})


def add_gallery_photos(album_id):
    payload = request.get_json(silent=True) or {}
    photos = payload.get("photos", [])
    if not isinstance(photos, list) or not photos:
        return error_response("photos 배열이 필요합니다.", 400)

    conn = get_db_connection()
    album = conn.execute(
        "SELECT id FROM gallery_albums WHERE id = ?", (album_id,)
    ).fetchone()
    if not album:
        conn.close()
        return error_response("앨범을 찾을 수 없습니다.", 404)

    from weave.files import make_thumbnail_like

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
    return success_response({"ok": True, "created": created})


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

