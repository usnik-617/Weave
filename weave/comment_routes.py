from weave.authz import can_comment_notice
from weave.core import (
    get_current_user_row,
    get_db_connection,
    log_audit,
    record_user_activity,
)
from weave.responses import error_response, success_response
from weave.time_utils import now_iso


def create_post_comment(post_id):
    from weave.core import request

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
    if post["category"] in ("notice", "gallery") and not can_comment_notice(me):
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
