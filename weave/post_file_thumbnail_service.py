from __future__ import annotations

import os
import shutil
from pathlib import Path

from weave.files import remove_file_safely
from weave import post_file_policy


def generate_gallery_thumbnail(original_file_info, upload_dir):
    original_path = str(original_file_info["stored_path"])
    original_ext = Path(original_path).suffix.lower()
    thumb_ext, save_format = post_file_policy.thumbnail_save_format(original_ext)
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
        return {
            "stored_path": thumb_path,
            "mime_type": _thumb_mime(thumb_ext),
            "size": int(os.path.getsize(thumb_path) if os.path.exists(thumb_path) else 0),
            "url": post_file_policy.stored_path_to_upload_url(thumb_path, upload_dir),
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

    return {
        "stored_path": thumb_path,
        "mime_type": _thumb_mime(thumb_ext),
        "size": int(os.path.getsize(thumb_path) if os.path.exists(thumb_path) else 0),
        "url": post_file_policy.stored_path_to_upload_url(thumb_path, upload_dir),
    }, None


def _thumb_mime(ext):
    mime_map = {
        ".jpg": "image/jpeg",
        ".png": "image/png",
        ".webp": "image/webp",
        ".gif": "image/gif",
    }
    return mime_map.get(ext, "image/jpeg")
