import os
import shutil
from pathlib import Path

from werkzeug.utils import secure_filename

from weave.authz import get_current_user_row, role_at_least
from weave.core import (
    UPLOAD_DIR,
    get_db_connection,
    log_audit,
    request,
    send_file,
)
from weave.files import (
    compute_file_sha256_from_filestorage,
    remove_file_safely,
    save_uploaded_file,
)
from weave import post_file_delivery, post_file_policy
from weave.responses import error_response, success_response
from weave.time_utils import now_iso, parse_iso_datetime


def _thumbnail_save_format(ext):
    return post_file_policy.thumbnail_save_format(ext)


def _generate_gallery_thumbnail(original_file_info):
    original_path = str(original_file_info["stored_path"])
    original_ext = Path(original_path).suffix.lower()
    thumb_ext, save_format = _thumbnail_save_format(original_ext)
    original_stem = Path(original_path).stem
    thumb_name = f"{original_stem}_thumb{thumb_ext}"
    thumb_path = str(Path(original_path).with_name(thumb_name))

    try:
        from PIL import Image
    except Exception:
        try:
            shutil.copyfile(original_path, thumb_path)
        except Exception:
            remove_file_safely(thumb_path)
            return None, "갤러리 썸네일 생성에 실패했습니다."
        mime_map = {
            ".jpg": "image/jpeg",
            ".png": "image/png",
            ".webp": "image/webp",
            ".gif": "image/gif",
        }
        return {
            "stored_path": thumb_path,
            "mime_type": mime_map.get(thumb_ext, "image/jpeg"),
            "size": int(
                os.path.getsize(thumb_path) if os.path.exists(thumb_path) else 0
            ),
            "url": post_file_policy.stored_path_to_upload_url(thumb_path, UPLOAD_DIR),
        }, None

    try:
        with Image.open(original_path) as image:
            image.thumbnail((400, 400))
            if save_format == "JPEG" and image.mode in ("RGBA", "LA", "P"):
                image = image.convert("RGB")
            save_kwargs = {}
            if save_format in ("JPEG", "WEBP"):
                save_kwargs["quality"] = 85
            image.save(thumb_path, format=save_format, **save_kwargs)
    except Exception:
        remove_file_safely(thumb_path)
        try:
            shutil.copyfile(original_path, thumb_path)
        except Exception:
            remove_file_safely(thumb_path)
            return None, "갤러리 썸네일 생성에 실패했습니다."

    mime_map = {
        ".jpg": "image/jpeg",
        ".png": "image/png",
        ".webp": "image/webp",
        ".gif": "image/gif",
    }
    return {
        "stored_path": thumb_path,
        "mime_type": mime_map.get(thumb_ext, "image/jpeg"),
        "size": int(os.path.getsize(thumb_path) if os.path.exists(thumb_path) else 0),
        "url": post_file_policy.stored_path_to_upload_url(thumb_path, UPLOAD_DIR),
    }, None


def upload_post_file(post_id):
    conn = get_db_connection()
    me = get_current_user_row(conn)
    if not me:
        conn.close()
        return error_response("Unauthorized", 401)
    if not role_at_least(me["role"], "MEMBER"):
        conn.close()
        return error_response("단원 이상만 파일을 업로드할 수 있습니다.", 403)
    post = conn.execute(
        "SELECT id, category FROM posts WHERE id = ?", (post_id,)
    ).fetchone()
    if not post:
        conn.close()
        return error_response("게시글을 찾을 수 없습니다.", 404)

    file_storage = request.files.get("file")
    post_category = str(post["category"] or "").lower()
    filename = secure_filename(str(file_storage.filename or "")) if file_storage else ""
    extension = post_file_policy.extension_of(filename)
    mime_type = post_file_policy.mime_of(file_storage.mimetype) if file_storage else ""
    policy_error = post_file_policy.upload_policy_error_message(
        post_category, extension, mime_type
    )
    if policy_error:
        conn.close()
        return error_response(policy_error, 400)

    expires_at = post_file_policy.normalize_expires_at(request.form)
    if expires_at and not parse_iso_datetime(expires_at):
        conn.close()
        return error_response("expires_at은 ISO 형식이어야 합니다.", 400)

    file_hash = compute_file_sha256_from_filestorage(file_storage)
    existing = conn.execute(
        """
        SELECT stored_path, mime_type, size
        FROM post_files
        WHERE hash_sha256 = ?
        ORDER BY id ASC
        LIMIT 1
        """,
        (file_hash,),
    ).fetchone()

    if existing and os.path.exists(existing["stored_path"]):
        file_info = {
            "original_name": filename,
            "stored_path": existing["stored_path"],
            "mime_type": existing["mime_type"],
            "size": int(existing["size"] or 0),
        }
        created_at = now_iso()
    else:
        file_info, err = save_uploaded_file(file_storage)
        if err:
            conn.close()
            return error_response(err, 400)
        if not file_info:
            conn.close()
            return error_response("파일 처리에 실패했습니다.", 400)
        created_at = now_iso()

    thumb_info = None
    if post_file_policy.should_generate_gallery_thumbnail(post_category):
        thumb_info, thumb_err = _generate_gallery_thumbnail(file_info)
        if thumb_err:
            remove_file_safely(file_info["stored_path"])
            conn.close()
            return error_response(thumb_err, 500)

    cur = conn.cursor()
    cur.execute(
        """
        INSERT INTO post_files (post_id, original_name, stored_path, mime_type, size, hash_sha256, uploaded_at, created_at, expires_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            post_id,
            file_info["original_name"],
            file_info["stored_path"],
            file_info["mime_type"],
            int(file_info["size"]),
            file_hash,
            created_at,
            created_at,
            expires_at,
        ),
    )
    file_id = cur.lastrowid
    if post_file_policy.should_generate_gallery_thumbnail(post_category):
        if thumb_info is None:
            remove_file_safely(file_info["stored_path"])
            conn.close()
            return error_response("갤러리 썸네일 생성에 실패했습니다.", 500)
        conn.execute(
            "UPDATE posts SET image_url = ?, thumb_url = ? WHERE id = ?",
            (
                post_file_policy.stored_path_to_upload_url(
                    file_info["stored_path"], UPLOAD_DIR
                ),
                thumb_info["url"],
                post_id,
            ),
        )
    log_audit(conn, "upload_post_file", "post", post_id, me["id"])
    conn.commit()
    conn.close()
    return success_response({"file_id": file_id}, 201)


def list_post_files(post_id):
    conn = get_db_connection()
    me = get_current_user_row(conn)
    if not me:
        conn.close()
        return error_response("Unauthorized", 401)
    rows = conn.execute(
        """
        SELECT id, original_name, mime_type, size, uploaded_at, stored_path
        FROM post_files
        WHERE post_id = ? AND (expires_at IS NULL OR expires_at = '' OR expires_at > ?)
        ORDER BY id DESC
        """,
        (post_id, now_iso()),
    ).fetchall()
    conn.close()

    items = []
    for row in rows:
        item = {
            "id": row["id"],
            "original_name": row["original_name"],
            "mime_type": row["mime_type"],
            "size": row["size"],
            "uploaded_at": row["uploaded_at"],
            "file_url": post_file_policy.stored_path_to_upload_url(
                row["stored_path"], UPLOAD_DIR
            ),
        }
        items.append(item)
    return success_response({"items": items})


def download_post_file(file_id):
    conn = get_db_connection()
    me = get_current_user_row(conn)
    if not me:
        conn.close()
        return error_response("Unauthorized", 401)
    row = conn.execute(
        "SELECT * FROM post_files WHERE id = ? AND (expires_at IS NULL OR expires_at = '' OR expires_at > ?)",
        (file_id, now_iso()),
    ).fetchone()
    conn.close()
    if not row:
        return error_response("파일을 찾을 수 없습니다.", 404)
    if not os.path.exists(row["stored_path"]):
        return error_response("저장된 파일이 없습니다.", 404)
    return post_file_delivery.send_download_response(
        row,
        post_file_policy.is_inline_requested(request.args),
        send_file,
    )


def serve_uploaded_file(filename):
    safe_rel = os.path.normpath(filename).replace("\\", "/").lstrip("/")
    if safe_rel.startswith("..") or "/../" in safe_rel:
        return error_response("Invalid path", 400)

    full_path = os.path.abspath(os.path.join(UPLOAD_DIR, safe_rel))
    uploads_root = os.path.abspath(UPLOAD_DIR)
    if not full_path.startswith(uploads_root):
        return error_response("Invalid path", 400)
    if not os.path.exists(full_path):
        return error_response("파일을 찾을 수 없습니다.", 404)

    upload_url = f"/uploads/{safe_rel}"
    conn = get_db_connection()
    row = conn.execute(
        """
        SELECT pf.id, pf.original_name, pf.mime_type, p.category
        FROM post_files pf
        LEFT JOIN posts p ON p.id = pf.post_id
        WHERE pf.stored_path = ? AND (pf.expires_at IS NULL OR pf.expires_at = '' OR pf.expires_at > ?)
        """,
        (full_path, now_iso()),
    ).fetchone()
    post_match = row
    if not post_match:
        post_match = conn.execute(
            "SELECT id, category FROM posts WHERE image_url = ? OR thumb_url = ? LIMIT 1",
            (upload_url, upload_url),
        ).fetchone()

    about_match = conn.execute(
        "SELECT section_key FROM about_sections WHERE image_url = ? LIMIT 1",
        (upload_url,),
    ).fetchone()

    if post_match and post_match["category"] == "gallery":
        conn.close()
        return post_file_delivery.send_uploaded_file(full_path, send_file)
    if about_match:
        conn.close()
        return post_file_delivery.send_uploaded_file(full_path, send_file)

    me = get_current_user_row(conn)
    if not me:
        conn.close()
        return error_response("Unauthorized", 401)
    if not role_at_least(me["role"], "MEMBER"):
        conn.close()
        return error_response("단원 이상만 접근할 수 있습니다.", 403)
    conn.close()

    if row and post_file_policy.is_pdf_mime(row["mime_type"]):
        return post_file_delivery.send_uploaded_pdf_inline(
            full_path,
            row["original_name"],
            send_file,
        )

    return post_file_delivery.send_uploaded_file(full_path, send_file)


def cleanup_orphan_files():
    conn = get_db_connection()
    db_rows = conn.execute("SELECT DISTINCT stored_path FROM post_files").fetchall()
    conn.close()
    referenced = {
        os.path.abspath(str(row["stored_path"]))
        for row in db_rows
        if row["stored_path"]
    }

    removed = 0
    kept = 0
    uploads_root = os.path.abspath(UPLOAD_DIR)
    for root, _, files in os.walk(uploads_root):
        for name in files:
            full_path = os.path.abspath(os.path.join(root, name))
            if full_path in referenced:
                kept += 1
                continue
            try:
                os.remove(full_path)
                removed += 1
            except Exception:
                pass
    return {"removed": removed, "kept": kept}
