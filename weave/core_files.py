from __future__ import annotations

import hashlib
import os
from datetime import datetime
from pathlib import Path

from werkzeug.utils import secure_filename

from weave import core

ALLOWED_IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp", ".gif"}
ALLOWED_IMAGE_MIME_TYPES = {
    "image/jpeg",
    "image/png",
    "image/webp",
    "image/gif",
}


def save_uploaded_file(file_storage):
    if not file_storage:
        return None, "파일이 없습니다."
    if not file_storage.filename:
        return None, "파일명이 없습니다."
    raw_name = str(file_storage.filename)
    if "/" in raw_name or "\\" in raw_name:
        return None, "파일명에 경로 구분자를 사용할 수 없습니다."

    original_name = secure_filename(raw_name)
    if not original_name:
        return None, "유효하지 않은 파일명입니다."
    extension = Path(original_name).suffix.lower()
    if extension not in core.ALLOWED_UPLOAD_EXT:
        return None, "허용되지 않은 파일 확장자입니다."

    mime_type = (file_storage.mimetype or "").lower()
    if mime_type not in core.ALLOWED_UPLOAD_MIME:
        return None, "허용되지 않은 파일 형식입니다."

    file_storage.stream.seek(0, os.SEEK_END)
    size = file_storage.stream.tell()
    file_storage.stream.seek(0)
    if size > core.MAX_UPLOAD_BYTES:
        return None, f"파일 크기는 최대 {core.MAX_UPLOAD_MB}MB까지 허용됩니다."

    stored_name = f"{core.uuid.uuid4().hex}{extension}"
    now = datetime.now()
    subdir = os.path.join(core.UPLOAD_DIR, f"{now.year:04d}", f"{now.month:02d}")
    os.makedirs(subdir, exist_ok=True)
    stored_path = os.path.join(subdir, stored_name)
    file_storage.save(stored_path)
    return {
        "original_name": original_name,
        "stored_name": stored_name,
        "stored_path": stored_path,
        "mime_type": mime_type,
        "size": size,
    }, None


def validate_image_upload_policy(file_storage):
    if not file_storage:
        return False, "이미지 파일이 필요합니다."
    original_name = secure_filename(str(file_storage.filename or ""))
    extension = Path(original_name).suffix.lower()
    mime_type = str(file_storage.mimetype or "").lower()
    if extension not in ALLOWED_IMAGE_EXTENSIONS:
        return False, "소개 섹션 이미지는 jpg/jpeg/png/webp/gif만 업로드할 수 있습니다."
    if mime_type not in ALLOWED_IMAGE_MIME_TYPES:
        return False, "소개 섹션 이미지는 jpg/jpeg/png/webp/gif만 업로드할 수 있습니다."
    return True, ""


def remove_file_safely(path):
    if not path:
        return
    try:
        target = os.path.abspath(path)
        root = os.path.abspath(core.UPLOAD_DIR)
        if not target.startswith(root):
            core.logger.warning(
                core.json.dumps(
                    {
                        "action": "skip_file_delete",
                        "reason": "outside_upload_root",
                        "path": target,
                    },
                    ensure_ascii=False,
                )
            )
            return
        if os.path.exists(target):
            os.remove(target)
    except Exception as exc:
        core.logger.error(
            core.json.dumps(
                {
                    "action": "file_delete_failed",
                    "path": str(path),
                    "error": str(exc),
                },
                ensure_ascii=False,
            )
        )


def upload_url_to_path(upload_url):
    text = str(upload_url or "").strip()
    if not text.startswith("/uploads/"):
        return None
    rel = text[len("/uploads/") :]
    rel = os.path.normpath(rel).replace("\\", "/")
    if rel.startswith(".."):
        return None
    return os.path.abspath(os.path.join(core.UPLOAD_DIR, rel))


def compute_file_sha256_from_filestorage(file_storage):
    if not file_storage:
        return ""
    sha = hashlib.sha256()
    stream = file_storage.stream
    stream.seek(0)
    while True:
        chunk = stream.read(1024 * 1024)
        if not chunk:
            break
        sha.update(chunk)
    stream.seek(0)
    return sha.hexdigest()
