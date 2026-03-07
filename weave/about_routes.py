import os
import re
import json

from weave import core, error_messages
from weave.authz import is_admin_like, role_at_least
from weave.core_audit import log_audit
from weave.core import get_current_user_row, get_db_connection, request
from weave.core_files import validate_image_upload_policy
from weave.files import save_uploaded_file
from weave.responses import error_response, success_response
from weave.time_utils import now_iso

ABOUT_SECTION_KEYS = {
    "executives",
    "history",
    "logo",
    "relatedsites",
    "rules",
    "awards",
    "fees",
    "hero_background",
}

CONTENT_BLOCK_KEYS = {
    "activities_overview",
    "join",
    "home_stats",
    "hero_background",
}

CONTENT_BLOCK_KEY_ALIASES = {
    "hero-background": "hero_background",
    "herobackground": "hero_background",
    "herobackgroundconfig": "hero_background",
    "hero_bg": "hero_background",
    "home_background": "hero_background",
    "homebackground": "hero_background",
    "home-hero-background": "hero_background",
    "home_hero_background": "hero_background",
}

SITE_EDITOR_SECTION_KEY = "site_editor_state_v1"


def _ensure_site_editor_history_table(conn):
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS site_editor_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            snapshot_json TEXT NOT NULL,
            action TEXT NOT NULL DEFAULT 'save',
            created_at TEXT NOT NULL,
            created_by INTEGER
        )
        """
    )
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_site_editor_history_created_at ON site_editor_history(created_at DESC)"
    )
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_site_editor_history_created_by ON site_editor_history(created_by)"
    )


def _site_editor_payload_or_default(raw_payload):
    if not isinstance(raw_payload, dict):
        return {"textEdits": {}, "imageEdits": {}}
    text_edits = raw_payload.get("textEdits", {})
    image_edits = raw_payload.get("imageEdits", {})
    if not isinstance(text_edits, dict):
        text_edits = {}
    if not isinstance(image_edits, dict):
        image_edits = {}
    return {
        "textEdits": {str(k): _sanitize_editor_html(v) for k, v in text_edits.items()},
        "imageEdits": {str(k): str(v) for k, v in image_edits.items()},
    }


def _sanitize_editor_html(value):
    html = str(value or "")
    html = re.sub(r"<\s*(script|style|iframe|object|embed)\b[^>]*>.*?<\s*/\s*\1\s*>", "", html, flags=re.IGNORECASE | re.DOTALL)
    html = re.sub(r"\s+on[a-zA-Z]+\s*=\s*(['\"]).*?\1", "", html, flags=re.IGNORECASE | re.DOTALL)
    html = re.sub(r"\s+on[a-zA-Z]+\s*=\s*[^\s>]+", "", html, flags=re.IGNORECASE)
    html = re.sub(r"(href|src)\s*=\s*(['\"])\s*javascript:.*?\2", r"\1=\2#\2", html, flags=re.IGNORECASE | re.DOTALL)
    return html


def _normalize_site_editor_update_payload(payload):
    if not isinstance(payload, dict):
        return {"textEdits": {}, "imageEdits": {}}, None
    if "state" in payload:
        return _site_editor_payload_or_default(payload.get("state")), payload.get("ifMatchUpdatedAt")
    # Backward-compatible payload shape.
    return _site_editor_payload_or_default(payload), payload.get("ifMatchUpdatedAt")


def _coerce_int(value, default):
    try:
        return int(value)
    except Exception:
        return int(default)


def _validate_hero_background_block(content_html):
    text = str(content_html or "").strip()
    if not text:
        return True, "", ""
    try:
        payload = json.loads(text)
    except Exception:
        return False, "hero_background는 JSON 형식이어야 합니다.", ""
    if not isinstance(payload, dict):
        return False, "hero_background는 객체 형식이어야 합니다.", ""

    payload["imageOffsetX"] = max(-120, min(120, _coerce_int(payload.get("imageOffsetX", 0), 0)))
    payload["imageOffsetY"] = max(-120, min(120, _coerce_int(payload.get("imageOffsetY", 0), 0)))
    payload["backgroundPosX"] = max(0, min(100, _coerce_int(payload.get("backgroundPosX", 50), 50)))
    payload["backgroundPosY"] = max(0, min(100, _coerce_int(payload.get("backgroundPosY", 45), 45)))

    return True, "", json.dumps(payload, ensure_ascii=False)


def _read_site_editor_state(conn):
    row = conn.execute(
        """
        SELECT section_key, content_html, updated_at, updated_by
        FROM about_sections
        WHERE section_key = ?
        """,
        (SITE_EDITOR_SECTION_KEY,),
    ).fetchone()
    if not row:
        return {
            "state": {"textEdits": {}, "imageEdits": {}},
            "updatedAt": None,
            "updatedBy": None,
        }
    try:
        parsed = json.loads(row["content_html"] or "{}")
    except Exception:
        parsed = {}
    return {
        "state": _site_editor_payload_or_default(parsed),
        "updatedAt": row["updated_at"],
        "updatedBy": row["updated_by"],
    }


def _upsert_site_editor_state(conn, payload, user_id):
    conn.execute(
        """
        INSERT INTO about_sections (section_key, content_html, image_url, updated_at, updated_by)
        VALUES (?, ?, '', ?, ?)
        ON CONFLICT(section_key) DO UPDATE SET
            content_html = excluded.content_html,
            updated_at = excluded.updated_at,
            updated_by = excluded.updated_by
        """,
        (
            SITE_EDITOR_SECTION_KEY,
            json.dumps(_site_editor_payload_or_default(payload), ensure_ascii=False),
            now_iso(),
            user_id,
        ),
    )


def _push_site_editor_history(conn, payload, action, user_id):
    conn.execute(
        """
        INSERT INTO site_editor_history (snapshot_json, action, created_at, created_by)
        VALUES (?, ?, ?, ?)
        """,
        (
            json.dumps(_site_editor_payload_or_default(payload), ensure_ascii=False),
            str(action or "save"),
            now_iso(),
            user_id,
        ),
    )


def _require_active_admin(conn):
    me = get_current_user_row(conn)
    if not me:
        return None, error_response(error_messages.UNAUTHORIZED, 401)
    if me["status"] != "active" or not is_admin_like(me):
        return None, error_response(error_messages.POST_HERO_BACKGROUND_ADMIN_ONLY, 403)
    return me, None

ABOUT_SECTION_KEY_ALIASES = {
    **CONTENT_BLOCK_KEY_ALIASES,
    "related_sites": "relatedsites",
    "related-sites": "relatedsites",
}


def _normalize_key(raw_key, aliases):
    key = str(raw_key or "").strip()
    if not key:
        return ""
    lowered = key.lower()
    if lowered in aliases:
        return aliases[lowered]

    normalized = re.sub(r"[^a-z0-9]+", "_", lowered).strip("_")
    if normalized in aliases:
        return aliases[normalized]

    squashed = normalized.replace("_", "")
    if squashed in aliases:
        return aliases[squashed]

    return normalized


def _stored_path_to_upload_url(stored_path):
    rel_path = os.path.relpath(stored_path, core.UPLOAD_DIR).replace("\\", "/")
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
    section_key = _normalize_key(payload.get("key", ""), ABOUT_SECTION_KEY_ALIASES)
    content_html = str(payload.get("contentHtml", ""))
    image_url = str(payload.get("imageUrl", "")).strip()

    if section_key not in ABOUT_SECTION_KEYS:
        return error_response(error_messages.POST_ABOUT_SECTION_INVALID, 400)

    conn = get_db_connection()
    me = get_current_user_row(conn)
    if not me:
        conn.close()
        return error_response(error_messages.UNAUTHORIZED, 401)
    if me["status"] != "active" or not role_at_least(me["role"], "EXECUTIVE"):
        conn.close()
        return error_response(error_messages.POST_EXEC_REQUIRED, 403)

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
    section_key = _normalize_key(request.form.get("key", ""), ABOUT_SECTION_KEY_ALIASES)
    if section_key not in ABOUT_SECTION_KEYS:
        return error_response(error_messages.POST_ABOUT_SECTION_INVALID, 400)

    conn = get_db_connection()
    me = get_current_user_row(conn)
    if not me:
        conn.close()
        return error_response(error_messages.UNAUTHORIZED, 401)
    if me["status"] != "active":
        conn.close()
        return error_response(error_messages.POST_EXEC_REQUIRED, 403)

    if section_key == "hero_background":
        if not is_admin_like(me):
            conn.close()
            return error_response(error_messages.POST_ADMIN_ONLY_BACKGROUND_IMAGE, 403)
    elif not role_at_least(me["role"], "EXECUTIVE"):
        conn.close()
        return error_response(error_messages.POST_EXEC_REQUIRED, 403)

    file_storage = request.files.get("file")
    if not file_storage:
        conn.close()
        return error_response(error_messages.POST_IMAGE_FILE_REQUIRED, 400)

    ok, reason = validate_image_upload_policy(file_storage)
    if not ok:
        conn.close()
        return error_response(reason or error_messages.POST_IMAGE_FILE_TYPE_INVALID, 400)

    file_info, err = save_uploaded_file(file_storage)
    if err:
        conn.close()
        return error_response(err, 400)
    if not file_info:
        conn.close()
        return error_response(error_messages.POST_FILE_PROCESS_FAILED, 400)

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
        WHERE section_key IN (?, ?, ?, ?)
        ORDER BY section_key ASC
        """,
        ("activities_overview", "join", "home_stats", "hero_background"),
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
    block_key = _normalize_key(payload.get("key", ""), CONTENT_BLOCK_KEY_ALIASES)
    content_html = str(payload.get("contentHtml", ""))

    if block_key not in CONTENT_BLOCK_KEYS:
        return error_response(error_messages.POST_CONTENT_BLOCK_INVALID, 400)

    conn = get_db_connection()
    me = get_current_user_row(conn)
    if not me:
        conn.close()
        return error_response(error_messages.UNAUTHORIZED, 401)
    if me["status"] != "active":
        conn.close()
        return error_response(error_messages.POST_EXEC_REQUIRED, 403)

    if block_key in {"home_stats", "hero_background"}:
        if not is_admin_like(me):
            conn.close()
            message = (
                error_messages.POST_HOME_STATS_ADMIN_ONLY
                if block_key == "home_stats"
                else error_messages.POST_HERO_BACKGROUND_ADMIN_ONLY
            )
            return error_response(message, 403)
    elif not role_at_least(me["role"], "EXECUTIVE"):
        conn.close()
        return error_response(error_messages.POST_EXEC_REQUIRED, 403)

    if block_key == "hero_background":
        ok, reason, normalized_content = _validate_hero_background_block(content_html)
        if not ok:
            conn.close()
            return error_response(reason, 400)
        content_html = normalized_content

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
    log_audit(
        actor_user_id=me["id"],
        action="content_block_updated",
        target_type="content_block",
        target_id=None,
        metadata={"key": block_key},
    )
    conn.close()
    return success_response({"ok": True})


def get_site_editor_state():
    conn = get_db_connection()
    _ensure_site_editor_history_table(conn)
    current = _read_site_editor_state(conn)
    conn.close()
    return success_response(current)


def update_site_editor_state():
    payload = request.get_json(silent=True) or {}
    next_state, if_match_updated_at = _normalize_site_editor_update_payload(payload)
    conn = get_db_connection()
    _ensure_site_editor_history_table(conn)
    me, err = _require_active_admin(conn)
    if err:
        conn.close()
        return err
    if not me:
        conn.close()
        return error_response(error_messages.UNAUTHORIZED, 401)

    current = _read_site_editor_state(conn)
    if if_match_updated_at and str(if_match_updated_at) != str(current.get("updatedAt") or ""):
        conn.close()
        return error_response(error_messages.POST_SITE_EDITOR_CONFLICT, 409)

    _push_site_editor_history(conn, current["state"], "save", me["id"])
    _upsert_site_editor_state(conn, next_state, me["id"])
    conn.commit()

    updated = _read_site_editor_state(conn)
    log_audit(
        actor_user_id=me["id"],
        action="site_editor_saved",
        target_type="site_editor",
        target_id=None,
        metadata={"ifMatchUpdatedAt": if_match_updated_at, "updatedAt": updated.get("updatedAt")},
    )
    conn.close()
    return success_response(updated)


def reset_site_editor_state():
    conn = get_db_connection()
    _ensure_site_editor_history_table(conn)
    me, err = _require_active_admin(conn)
    if err:
        conn.close()
        return err
    if not me:
        conn.close()
        return error_response(error_messages.UNAUTHORIZED, 401)

    current = _read_site_editor_state(conn)
    _push_site_editor_history(conn, current["state"], "reset", me["id"])
    _upsert_site_editor_state(conn, {"textEdits": {}, "imageEdits": {}}, me["id"])
    conn.commit()

    updated = _read_site_editor_state(conn)
    log_audit(
        actor_user_id=me["id"],
        action="site_editor_reset",
        target_type="site_editor",
        target_id=None,
        metadata={"updatedAt": updated.get("updatedAt")},
    )
    conn.close()
    return success_response(updated)


def list_site_editor_history():
    limit = int(request.args.get("limit", "20") or 20)
    limit = max(1, min(limit, 100))

    conn = get_db_connection()
    _ensure_site_editor_history_table(conn)
    me, err = _require_active_admin(conn)
    if err:
        conn.close()
        return err
    if not me:
        conn.close()
        return error_response(error_messages.UNAUTHORIZED, 401)

    rows = conn.execute(
        """
        SELECT h.id, h.snapshot_json, h.action, h.created_at, h.created_by,
               u.username AS created_by_username
        FROM site_editor_history h
        LEFT JOIN users u ON u.id = h.created_by
        ORDER BY h.id DESC
        LIMIT ?
        """,
        (limit,),
    ).fetchall()
    conn.close()

    items = []
    for row in rows:
        try:
            parsed = json.loads(row["snapshot_json"] or "{}")
        except Exception:
            parsed = {}
        items.append(
            {
                "id": row["id"],
                "action": row["action"],
                "createdAt": row["created_at"],
                "createdBy": row["created_by"],
                "createdByUsername": row["created_by_username"],
                "state": _site_editor_payload_or_default(parsed),
            }
        )
    return success_response({"items": items})


def undo_site_editor_state():
    conn = get_db_connection()
    _ensure_site_editor_history_table(conn)
    me, err = _require_active_admin(conn)
    if err:
        conn.close()
        return err
    if not me:
        conn.close()
        return error_response(error_messages.UNAUTHORIZED, 401)

    last = conn.execute(
        """
        SELECT id, snapshot_json
        FROM site_editor_history
        ORDER BY id DESC
        LIMIT 1
        """
    ).fetchone()
    if not last:
        conn.close()
        return error_response(error_messages.POST_SITE_EDITOR_HISTORY_EMPTY, 404)

    try:
        snapshot = json.loads(last["snapshot_json"] or "{}")
    except Exception:
        snapshot = {}

    _upsert_site_editor_state(conn, _site_editor_payload_or_default(snapshot), me["id"])
    conn.execute("DELETE FROM site_editor_history WHERE id = ?", (last["id"],))
    conn.commit()

    updated = _read_site_editor_state(conn)
    log_audit(
        actor_user_id=me["id"],
        action="site_editor_undo",
        target_type="site_editor_history",
        target_id=last["id"],
        metadata={"updatedAt": updated.get("updatedAt")},
    )
    conn.close()
    return success_response(updated)


def restore_site_editor_state():
    payload = request.get_json(silent=True) or {}
    history_id = int(payload.get("historyId") or 0)
    if history_id <= 0:
        return error_response(error_messages.POST_SITE_EDITOR_HISTORY_NOT_FOUND, 404)

    conn = get_db_connection()
    _ensure_site_editor_history_table(conn)
    me, err = _require_active_admin(conn)
    if err:
        conn.close()
        return err
    if not me:
        conn.close()
        return error_response(error_messages.UNAUTHORIZED, 401)

    target = conn.execute(
        """
        SELECT id, snapshot_json
        FROM site_editor_history
        WHERE id = ?
        """,
        (history_id,),
    ).fetchone()
    if not target:
        conn.close()
        return error_response(error_messages.POST_SITE_EDITOR_HISTORY_NOT_FOUND, 404)

    current = _read_site_editor_state(conn)
    _push_site_editor_history(conn, current["state"], "restore", me["id"])

    try:
        snapshot = json.loads(target["snapshot_json"] or "{}")
    except Exception:
        snapshot = {}

    _upsert_site_editor_state(conn, _site_editor_payload_or_default(snapshot), me["id"])
    conn.commit()

    updated = _read_site_editor_state(conn)
    log_audit(
        actor_user_id=me["id"],
        action="site_editor_restore",
        target_type="site_editor_history",
        target_id=history_id,
        metadata={"updatedAt": updated.get("updatedAt")},
    )
    conn.close()
    return success_response(updated)
