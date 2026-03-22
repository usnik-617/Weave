from __future__ import annotations

import io
import os
from typing import Optional

from weave import core
from weave import post_file_policy
from weave import storage_backend


def _thumbnail_bytes_from_image_bytes(image_bytes: bytes):
    try:
        from PIL import Image
    except Exception:
        return None, None

    with Image.open(io.BytesIO(image_bytes)) as image:
        image.thumbnail((400, 400))
        if image.mode in ("RGBA", "LA", "P"):
            image = image.convert("RGB")
        output = io.BytesIO()
        image.save(output, format="WEBP", quality=85)
        return output.getvalue(), "image/webp"


def _load_original_bytes(stored_path: str) -> Optional[bytes]:
    raw = str(stored_path or "").strip()
    if not raw:
        return None
    if raw.startswith("obj://"):
        return storage_backend.read_stored_bytes(raw)
    try:
        with open(raw, "rb") as fp:
            return fp.read()
    except Exception:
        return None


def _save_thumbnail_for_ref(stored_path: str, thumb_bytes: bytes, mime_type: str):
    raw = str(stored_path or "").strip()
    if raw.startswith("obj://"):
        key = storage_backend.object_key_from_ref(raw)
        if not key:
            return ""
        root, _ = os.path.splitext(key)
        thumb_key = f"{root}_thumb.webp"
        storage_backend.save_bytes_object(thumb_key, thumb_bytes, mime_type)
        storage_backend.bump_storage_stat("object_put_count", 1)
        return storage_backend.object_ref_from_key(thumb_key)

    base, _ = os.path.splitext(raw)
    thumb_path = f"{base}_thumb.webp"
    with open(thumb_path, "wb") as fp:
        fp.write(thumb_bytes)
    return thumb_path


def generate_cover_derivatives(post_id: int, stored_path: str):
    conn = core.get_db_connection()
    try:
        post = conn.execute(
            "SELECT id, category FROM posts WHERE id = ? LIMIT 1",
            (int(post_id),),
        ).fetchone()
        if not post:
            return {"ok": False, "reason": "post_not_found"}
        category = str(post["category"] or "").lower()
        if category != "gallery":
            return {"ok": True, "skipped": "not_gallery"}

        image_url = post_file_policy.stored_path_to_upload_url(stored_path, core.UPLOAD_DIR)

        original_bytes = _load_original_bytes(stored_path)
        if not original_bytes:
            conn.execute("UPDATE posts SET image_url = ? WHERE id = ?", (image_url, int(post_id)))
            conn.commit()
            return {"ok": True, "thumb": "", "image_url": image_url, "degraded": True}

        thumb_bytes, thumb_mime = _thumbnail_bytes_from_image_bytes(original_bytes)
        if not thumb_bytes:
            conn.execute("UPDATE posts SET image_url = ? WHERE id = ?", (image_url, int(post_id)))
            conn.commit()
            return {"ok": True, "thumb": "", "image_url": image_url, "degraded": True}

        thumb_ref = _save_thumbnail_for_ref(stored_path, thumb_bytes, thumb_mime or "image/webp")
        thumb_url = (
            post_file_policy.stored_path_to_upload_url(thumb_ref, core.UPLOAD_DIR)
            if thumb_ref
            else image_url
        )
        conn.execute(
            "UPDATE posts SET image_url = ?, thumb_url = ? WHERE id = ?",
            (image_url, thumb_url, int(post_id)),
        )
        conn.commit()
        return {"ok": True, "thumb": thumb_url, "image_url": image_url}
    finally:
        conn.close()
