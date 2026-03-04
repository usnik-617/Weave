from weave.core import *


def upload_post_file(post_id):
    conn = get_db_connection()
    me = get_current_user_row(conn)
    if not me:
        conn.close()
        return error_response("Unauthorized", 401)
    post = conn.execute("SELECT id, category FROM posts WHERE id = ?", (post_id,)).fetchone()
    if not post:
        conn.close()
        return error_response("게시글을 찾을 수 없습니다.", 404)

    file_storage = request.files.get("file")
    file_info, err = save_uploaded_file(file_storage)
    if err:
        conn.close()
        return error_response(err, 400)
    if not file_info:
        conn.close()
        return error_response("파일 처리에 실패했습니다.", 400)

    cur = conn.cursor()
    cur.execute(
        """
        INSERT INTO post_files (post_id, original_name, stored_path, mime_type, size, uploaded_at)
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        (
            post_id,
            file_info["original_name"],
            file_info["stored_path"],
            file_info["mime_type"],
            int(file_info["size"]),
            now_iso(),
        ),
    )
    file_id = cur.lastrowid
    if post["category"] == "gallery":
        relative_path = os.path.relpath(file_info["stored_path"], UPLOAD_DIR).replace("\\", "/")
        conn.execute("UPDATE posts SET image_url = ? WHERE id = ?", (f"/uploads/{relative_path}", post_id))
    log_audit(conn, "upload_post_file", "post", post_id, me["id"])
    conn.commit()
    conn.close()
    return success_response({"file_id": file_id}, 201)


def list_post_files(post_id):
    conn = get_db_connection()
    rows = conn.execute(
        "SELECT id, original_name, mime_type, size, uploaded_at FROM post_files WHERE post_id = ? ORDER BY id DESC",
        (post_id,),
    ).fetchall()
    conn.close()
    return success_response({"items": [dict(row) for row in rows]})


def download_post_file(file_id):
    conn = get_db_connection()
    row = conn.execute("SELECT * FROM post_files WHERE id = ?", (file_id,)).fetchone()
    conn.close()
    if not row:
        return error_response("파일을 찾을 수 없습니다.", 404)
    if not os.path.exists(row["stored_path"]):
        return error_response("저장된 파일이 없습니다.", 404)
    return send_file(row["stored_path"], as_attachment=True, download_name=row["original_name"])


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

    conn = get_db_connection()
    row = conn.execute("SELECT pf.id, p.category FROM post_files pf LEFT JOIN posts p ON p.id = pf.post_id WHERE pf.stored_path = ?", (full_path,)).fetchone()

    if row and row["category"] == "gallery":
        conn.close()
        return send_file(full_path)

    me = get_current_user_row(conn)
    if not me:
        conn.close()
        return error_response("Unauthorized", 401)
    if not role_at_least(me["role"], "MEMBER"):
        conn.close()
        return error_response("단원 이상만 접근할 수 있습니다.", 403)
    conn.close()
    return send_file(full_path)


