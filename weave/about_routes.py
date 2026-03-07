import os
import re
from pathlib import Path

from werkzeug.utils import secure_filename

from weave import core, error_messages
from weave.authz import is_admin_like, role_at_least
from weave.core import get_current_user_row, get_db_connection, request
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
        return error_response(error_messages.POST_IMAGE_FILE_TYPE_INVALID, 400)

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
