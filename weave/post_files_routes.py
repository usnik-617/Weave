import os

from werkzeug.utils import secure_filename

from weave.authz import get_current_user_row, role_at_least
from weave.core import (
    POST_TOTAL_UPLOAD_BYTES,
    POST_TOTAL_UPLOAD_MB,
    UPLOAD_BATCH_MAX_FILES,
    UPLOAD_DIR,
    UPLOAD_GALLERY_THUMBNAIL_MODE,
    get_db_connection,
    log_audit,
    request,
    send_file,
    transaction,
)
from weave import file_error_policy
from weave import post_file_delivery, post_file_policy
from weave import media_queue, storage_backend
from weave.files import (
    compute_file_sha256_from_filestorage,
    remove_file_safely,
    save_uploaded_file,
)
from weave.responses import error_response, success_response
from weave.time_utils import now_iso, parse_iso_datetime


def _is_truthy(value):
    return str(value or "").strip().lower() in {"1", "true", "yes", "on"}


def _load_post_row(conn, post_id):
    return conn.execute(
        "SELECT id, category, image_url FROM posts WHERE id = ?",
        (post_id,),
    ).fetchone()


def _validate_expires_at_or_error(expires_at):
    if expires_at and not parse_iso_datetime(expires_at):
        return file_error_policy.expires_at_invalid()
    return None


def _should_update_gallery_cover(post_row, requested_set_cover):
    if str(post_row["category"] or "").lower() != "gallery":
        return False
    mode = str(UPLOAD_GALLERY_THUMBNAIL_MODE or "cover_only").strip().lower()
    if mode == "always":
        return True
    has_cover = bool(str(post_row["image_url"] or "").strip())
    if requested_set_cover:
        return True
    return not has_cover


def _upload_single_post_file(
    conn,
    me,
    post_row,
    file_storage,
    *,
    expires_at=None,
    set_cover=False,
):
    post_id = int(post_row["id"])
    post_category = str(post_row["category"] or "").lower()
    filename = secure_filename(str(file_storage.filename or "")) if file_storage else ""
    policy_error, _, _ = post_file_policy.validate_upload_policy(
        post_category,
        filename,
        file_storage.mimetype if file_storage else "",
    )
    if policy_error:
        return None, error_response(policy_error, 400)

    incoming_size = 0
    if file_storage and getattr(file_storage, "stream", None):
        file_storage.stream.seek(0, os.SEEK_END)
        incoming_size = int(file_storage.stream.tell() or 0)
        file_storage.stream.seek(0)
    if incoming_size <= 0:
        return None, error_response("업로드할 파일 크기를 확인할 수 없습니다.", 400)

    current_total_size = conn.execute(
        """
        SELECT COALESCE(SUM(size), 0) AS total_size
        FROM post_files
        WHERE post_id = ? AND (expires_at IS NULL OR expires_at = '' OR expires_at > ?)
        """,
        (post_id, now_iso()),
    ).fetchone()
    used_bytes = int((current_total_size["total_size"] if current_total_size else 0) or 0)
    if used_bytes + incoming_size > POST_TOTAL_UPLOAD_BYTES:
        remain_bytes = max(0, POST_TOTAL_UPLOAD_BYTES - used_bytes)
        return None, error_response(
            f"게시글당 총 업로드 용량은 최대 {POST_TOTAL_UPLOAD_MB}MB입니다. 남은 용량: {round(remain_bytes / (1024 * 1024), 2)}MB",
            400,
        )

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

    is_new_file_saved = False
    existing_ref = str(existing["stored_path"] or "") if existing else ""
    existing_is_object = existing_ref.startswith("obj://")
    if existing and (existing_is_object or os.path.exists(existing_ref)):
        file_info = {
            "original_name": filename,
            "stored_path": existing_ref,
            "mime_type": existing["mime_type"],
            "size": int(existing["size"] or 0),
        }
        created_at = now_iso()
    else:
        file_info, err = save_uploaded_file(file_storage)
        if err:
            return None, error_response(err, 400)
        if not file_info:
            return None, file_error_policy.upload_processing_failed()
        created_at = now_iso()
        is_new_file_saved = True

    should_update_cover = _should_update_gallery_cover(post_row, set_cover)

    try:
        with transaction(conn):
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
            file_id = int(cur.lastrowid or 0)
            file_url = post_file_policy.stored_path_to_upload_url(
                file_info["stored_path"], UPLOAD_DIR
            )
            if should_update_cover:
                conn.execute(
                    "UPDATE posts SET image_url = ?, thumb_url = COALESCE(NULLIF(thumb_url,''), ?) WHERE id = ?",
                    (file_url, file_url, post_id),
                )
            log_audit(conn, "upload_post_file", "post", post_id, me["id"])
    except Exception:
        if is_new_file_saved:
            remove_file_safely(file_info["stored_path"])
        return None, file_error_policy.upload_processing_failed()

    thumb_url = ""
    if should_update_cover:
        queue_result = media_queue.enqueue_cover_derivatives(post_id, file_info["stored_path"])
        if queue_result.get("queued"):
            thumb_url = file_url
        else:
            thumb_url = file_url

    return {
        "file_id": file_id,
        "file_url": file_url,
        "is_cover_updated": bool(should_update_cover),
        "thumb_url": str(thumb_url or ""),
    }, None


def upload_post_file(post_id):
    conn = get_db_connection()
    me = get_current_user_row(conn)
    if not me:
        conn.close()
        return file_error_policy.unauthorized()
    if not role_at_least(me["role"], "MEMBER"):
        conn.close()
        return file_error_policy.member_required_upload()
    post = _load_post_row(conn, post_id)
    if not post:
        conn.close()
        return file_error_policy.post_not_found()

    file_storage = request.files.get("file")
    expires_at = post_file_policy.normalize_expires_at(request.form)
    expires_error = _validate_expires_at_or_error(expires_at)
    if expires_error:
        conn.close()
        return expires_error

    upload_result, upload_error = _upload_single_post_file(
        conn,
        me,
        post,
        file_storage,
        expires_at=expires_at,
        set_cover=_is_truthy(request.form.get("set_cover", "")),
    )
    if upload_error:
        conn.close()
        return upload_error

    conn.close()
    return success_response({"file_id": int(upload_result["file_id"])}, 201)


def upload_post_files_batch(post_id):
    conn = get_db_connection()
    me = get_current_user_row(conn)
    if not me:
        conn.close()
        return file_error_policy.unauthorized()
    if not role_at_least(me["role"], "MEMBER"):
        conn.close()
        return file_error_policy.member_required_upload()
    post = _load_post_row(conn, post_id)
    if not post:
        conn.close()
        return file_error_policy.post_not_found()

    files = list(request.files.getlist("files") or [])
    if not files:
        single = request.files.get("file")
        if single:
            files = [single]
    if not files:
        conn.close()
        return error_response("업로드할 파일이 없습니다.", 400)
    if len(files) > int(max(1, UPLOAD_BATCH_MAX_FILES)):
        conn.close()
        return error_response(
            f"한 번에 업로드 가능한 파일 수를 초과했습니다. 최대 {int(max(1, UPLOAD_BATCH_MAX_FILES))}개까지 가능합니다.",
            400,
        )

    expires_at = post_file_policy.normalize_expires_at(request.form)
    expires_error = _validate_expires_at_or_error(expires_at)
    if expires_error:
        conn.close()
        return expires_error

    representative_index = -1
    try:
        representative_index = int(str(request.form.get("representative_index", "-1") or "-1"))
    except Exception:
        representative_index = -1

    tokens = list(request.form.getlist("tokens") or [])
    items = []
    failed = []

    for index, file_storage in enumerate(files):
        set_cover = representative_index >= 0 and index == representative_index
        if representative_index < 0 and str(post["category"] or "").lower() == "gallery":
            set_cover = index == (len(files) - 1)
        result, error = _upload_single_post_file(
            conn,
            me,
            post,
            file_storage,
            expires_at=expires_at,
            set_cover=set_cover,
        )
        token = str(tokens[index] if index < len(tokens) else "").strip()
        if error:
            failed.append(
                {
                    "index": index,
                    "token": token,
                    "filename": str(getattr(file_storage, "filename", "") or ""),
                    "error": str((error.get_json() or {}).get("error") or "업로드 실패"),
                }
            )
            continue
        items.append(
            {
                "index": index,
                "token": token,
                "file_id": int(result["file_id"]),
                "file_url": str(result["file_url"]),
                "thumb_url": str(result.get("thumb_url") or ""),
                "is_cover_updated": bool(result.get("is_cover_updated")),
            }
        )

    conn.close()
    status = 201 if not failed else 207
    return success_response(
        {
            "items": items,
            "failed": failed,
            "count": len(items),
            "failed_count": len(failed),
        },
        status,
    )


def list_post_files(post_id):
    conn = get_db_connection()
    me = get_current_user_row(conn)
    if not me:
        conn.close()
        return file_error_policy.unauthorized()
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
        return file_error_policy.unauthorized()
    row = conn.execute(
        "SELECT * FROM post_files WHERE id = ? AND (expires_at IS NULL OR expires_at = '' OR expires_at > ?)",
        (file_id, now_iso()),
    ).fetchone()
    conn.close()
    if not row:
        return file_error_policy.file_not_found()
    stored_ref = str(row["stored_path"] or "").strip()
    if stored_ref.startswith("obj://"):
        payload = storage_backend.read_stored_bytes(stored_ref)
        if payload is None:
            return file_error_policy.stored_file_missing()
        storage_backend.bump_storage_stat("object_get_count", 1)
        return post_file_delivery.send_object_download_response(
            payload,
            str(row["mime_type"] or "application/octet-stream"),
            str(row["original_name"] or "download"),
            post_file_policy.is_inline_requested(request.args),
        )
    if not os.path.exists(stored_ref):
        return file_error_policy.stored_file_missing()
    return post_file_delivery.send_download_response(
        row,
        post_file_policy.is_inline_requested(request.args),
        send_file,
    )


def serve_uploaded_file(filename):
    safe_rel = os.path.normpath(filename).replace("\\", "/").lstrip("/")
    if safe_rel.startswith("..") or "/../" in safe_rel:
        return file_error_policy.invalid_path()

    is_object_route = safe_rel.startswith("object/")
    object_ref = ""
    full_path = ""
    if is_object_route:
        object_key = safe_rel[len("object/") :].lstrip("/")
        if not object_key:
            return file_error_policy.invalid_path()
        object_ref = storage_backend.object_ref_from_key(object_key)
    else:
        full_path = os.path.abspath(os.path.join(UPLOAD_DIR, safe_rel))
        uploads_root = os.path.abspath(UPLOAD_DIR)
        if not full_path.startswith(uploads_root):
            return file_error_policy.invalid_path()
        if not os.path.exists(full_path):
            return file_error_policy.file_not_found()

    upload_url = f"/uploads/{safe_rel}"
    conn = get_db_connection()
    row = conn.execute(
        """
        SELECT pf.id, pf.original_name, pf.mime_type, p.category
        FROM post_files pf
        LEFT JOIN posts p ON p.id = pf.post_id
        WHERE pf.stored_path = ? AND (pf.expires_at IS NULL OR pf.expires_at = '' OR pf.expires_at > ?)
        """,
        ((object_ref if is_object_route else full_path), now_iso()),
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
        if is_object_route:
            cdn_url = storage_backend.object_public_url(object_ref)
            if cdn_url:
                conn.close()
                return post_file_delivery.redirect_to_public_asset(cdn_url)
        conn.close()
        if is_object_route:
            payload = storage_backend.read_stored_bytes(object_ref)
            if payload is None:
                return file_error_policy.file_not_found()
            storage_backend.bump_storage_stat("object_get_count", 1)
            return post_file_delivery.send_uploaded_object(payload, "application/octet-stream")
        response = post_file_delivery.send_uploaded_file(full_path, send_file)
        response.headers["Cache-Control"] = "public, max-age=31536000, immutable"
        return response
    if about_match:
        if is_object_route:
            cdn_url = storage_backend.object_public_url(object_ref)
            if cdn_url:
                conn.close()
                return post_file_delivery.redirect_to_public_asset(cdn_url)
        conn.close()
        if is_object_route:
            payload = storage_backend.read_stored_bytes(object_ref)
            if payload is None:
                return file_error_policy.file_not_found()
            storage_backend.bump_storage_stat("object_get_count", 1)
            return post_file_delivery.send_uploaded_object(payload, "application/octet-stream")
        response = post_file_delivery.send_uploaded_file(full_path, send_file)
        response.headers["Cache-Control"] = "public, max-age=86400"
        return response

    me = get_current_user_row(conn)
    if not me:
        conn.close()
        return file_error_policy.unauthorized()
    if not role_at_least(me["role"], "MEMBER"):
        conn.close()
        return file_error_policy.member_required_access()
    conn.close()

    if row and post_file_policy.is_pdf_mime(row["mime_type"]):
        if is_object_route:
            payload = storage_backend.read_stored_bytes(object_ref)
            if payload is None:
                return file_error_policy.file_not_found()
            storage_backend.bump_storage_stat("object_get_count", 1)
            return post_file_delivery.send_uploaded_object_pdf_inline(
                payload, str(row["original_name"] or "document.pdf")
            )
        return post_file_delivery.send_uploaded_pdf_inline(
            full_path,
            row["original_name"],
            send_file,
        )

    if is_object_route:
        payload = storage_backend.read_stored_bytes(object_ref)
        if payload is None:
            return file_error_policy.file_not_found()
        storage_backend.bump_storage_stat("object_get_count", 1)
        return post_file_delivery.send_uploaded_object(payload, str(row["mime_type"] if row else "application/octet-stream"))
    response = post_file_delivery.send_uploaded_file(full_path, send_file)
    response.headers["Cache-Control"] = "private, max-age=0, must-revalidate"
    return response


def cleanup_orphan_files():
    conn = get_db_connection()
    db_rows = conn.execute("SELECT DISTINCT stored_path FROM post_files").fetchall()
    conn.close()
    object_refs = set()
    referenced = {
        os.path.abspath(str(row["stored_path"]))
        for row in db_rows
        if row["stored_path"] and not str(row["stored_path"]).startswith("obj://")
    }
    for row in db_rows:
        raw = str(row["stored_path"] or "").strip()
        if raw.startswith("obj://"):
            object_refs.add(raw)

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
    return {"removed": removed, "kept": kept, "object_refs": len(object_refs)}
