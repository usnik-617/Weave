from __future__ import annotations

import os
from pathlib import Path


GALLERY_IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp", ".gif"}
GALLERY_IMAGE_MIME_TYPES = {
    "image/jpeg",
    "image/png",
    "image/webp",
    "image/gif",
}
NOTICE_ALLOWED_EXTENSIONS = GALLERY_IMAGE_EXTENSIONS | {".pdf"}
NOTICE_ALLOWED_MIME_TYPES = GALLERY_IMAGE_MIME_TYPES | {"application/pdf"}


def stored_path_to_upload_url(stored_path, upload_dir):
    rel_path = os.path.relpath(stored_path, upload_dir).replace("\\", "/")
    return f"/uploads/{rel_path}"


def extension_of(filename):
    return Path(str(filename or "")).suffix.lower()


def mime_of(raw_mime):
    return str(raw_mime or "").lower()


def upload_policy_error_message(category, extension, mime_type):
    post_category = str(category or "").lower()
    if post_category == "gallery":
        if (
            extension not in GALLERY_IMAGE_EXTENSIONS
            or mime_type not in GALLERY_IMAGE_MIME_TYPES
        ):
            return "갤러리는 이미지 파일만 업로드할 수 있습니다.(jpg/jpeg/png/webp/gif)"
    elif post_category == "notice":
        if (
            extension not in NOTICE_ALLOWED_EXTENSIONS
            or mime_type not in NOTICE_ALLOWED_MIME_TYPES
        ):
            return "공지사항에는 이미지 또는 PDF만 첨부할 수 있습니다."
    return ""


def validate_upload_policy(category, filename, raw_mime):
    extension = extension_of(filename)
    mime_type = mime_of(raw_mime)
    error_message = upload_policy_error_message(category, extension, mime_type)
    return error_message, extension, mime_type


def should_generate_gallery_thumbnail(category):
    return str(category or "").lower() == "gallery"


def thumbnail_save_format(ext):
    lowered = str(ext or "").lower()
    if lowered in (".jpg", ".jpeg"):
        return ".jpg", "JPEG"
    if lowered == ".png":
        return ".png", "PNG"
    if lowered == ".webp":
        return ".webp", "WEBP"
    if lowered == ".gif":
        return ".gif", "GIF"
    return ".jpg", "JPEG"


def normalize_expires_at(form_data):
    if not form_data:
        return None
    value = str(form_data.get("expires_at", "")).strip()
    return value or None


def is_pdf_mime(mime_type):
    return str(mime_type or "").lower() == "application/pdf"


def is_inline_requested(query_args):
    return str(query_args.get("inline", "")).strip().lower() in {"1", "true", "yes"}
