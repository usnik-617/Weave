from __future__ import annotations

import os
import threading
from typing import Optional

from weave import core


class StorageError(Exception):
    pass


def _backend_name() -> str:
    return str(os.environ.get("WEAVE_STORAGE_BACKEND", "local") or "local").strip().lower()


def _cdn_base_url() -> str:
    return str(os.environ.get("WEAVE_CDN_BASE_URL", "") or "").strip().rstrip("/")


def is_object_storage_enabled() -> bool:
    return _backend_name() in {"s3", "r2", "minio"}


def _build_s3_client():
    try:
        import boto3  # type: ignore
    except Exception as exc:  # pragma: no cover
        raise StorageError("boto3가 설치되지 않아 오브젝트 스토리지를 사용할 수 없습니다.") from exc

    endpoint_url = str(os.environ.get("WEAVE_S3_ENDPOINT_URL", "") or "").strip() or None
    region = str(os.environ.get("WEAVE_S3_REGION", "auto") or "auto").strip() or None
    access_key = str(os.environ.get("WEAVE_S3_ACCESS_KEY_ID", "") or "").strip() or None
    secret_key = str(os.environ.get("WEAVE_S3_SECRET_ACCESS_KEY", "") or "").strip() or None

    session = boto3.session.Session()
    return session.client(
        "s3",
        endpoint_url=endpoint_url,
        region_name=region,
        aws_access_key_id=access_key,
        aws_secret_access_key=secret_key,
    )


def _bucket_name() -> str:
    value = str(os.environ.get("WEAVE_S3_BUCKET", "") or "").strip()
    if not value:
        raise StorageError("WEAVE_S3_BUCKET 환경변수가 비어 있습니다.")
    return value


def object_ref_from_key(key: str) -> str:
    safe_key = str(key or "").strip().lstrip("/")
    return f"obj://{safe_key}"


def object_key_from_ref(stored_ref: str) -> str:
    text = str(stored_ref or "").strip()
    if not text.startswith("obj://"):
        return ""
    return text[len("obj://") :].lstrip("/")


def save_bytes_object(key: str, data: bytes, mime_type: str = "application/octet-stream"):
    bucket = _bucket_name()
    client = _build_s3_client()
    client.put_object(
        Bucket=bucket,
        Key=str(key).lstrip("/"),
        Body=data,
        ContentType=str(mime_type or "application/octet-stream"),
    )


def save_filestorage(file_storage, object_key: str):
    bucket = _bucket_name()
    client = _build_s3_client()
    stream = getattr(file_storage, "stream", None)
    if stream is None:
        raise StorageError("업로드 스트림을 찾을 수 없습니다.")
    stream.seek(0)
    client.upload_fileobj(
        stream,
        bucket,
        str(object_key).lstrip("/"),
        ExtraArgs={"ContentType": str(file_storage.mimetype or "application/octet-stream")},
    )


def load_object_bytes(object_key: str) -> bytes:
    bucket = _bucket_name()
    client = _build_s3_client()
    response = client.get_object(Bucket=bucket, Key=str(object_key).lstrip("/"))
    body = response.get("Body")
    if not body:
        raise StorageError("오브젝트 본문을 읽을 수 없습니다.")
    return body.read()


def delete_object(stored_ref: str):
    key = object_key_from_ref(stored_ref)
    if not key:
        return
    try:
        bucket = _bucket_name()
        client = _build_s3_client()
        client.delete_object(Bucket=bucket, Key=key)
    except Exception:
        return


def object_public_url(stored_ref: str) -> str:
    key = object_key_from_ref(stored_ref)
    if not key:
        return ""
    cdn = _cdn_base_url()
    if cdn:
        return f"{cdn}/{key}"
    backend = _backend_name()
    if backend in {"s3", "r2", "minio"}:
        endpoint = str(os.environ.get("WEAVE_S3_PUBLIC_BASE_URL", "") or "").strip().rstrip("/")
        if endpoint:
            return f"{endpoint}/{key}"
    return ""


def read_stored_bytes(stored_ref: str) -> Optional[bytes]:
    if not is_object_storage_enabled():
        return None
    key = object_key_from_ref(stored_ref)
    if not key:
        return None
    try:
        return load_object_bytes(key)
    except Exception:
        return None


_UPLOAD_STATS = {
    "object_put_count": 0,
    "object_get_count": 0,
    "object_delete_count": 0,
}
_UPLOAD_STATS_LOCK = threading.Lock()


def bump_storage_stat(name: str, delta: int = 1):
    with _UPLOAD_STATS_LOCK:
        _UPLOAD_STATS[name] = int(_UPLOAD_STATS.get(name, 0)) + int(delta)


def snapshot_storage_stats() -> dict:
    with _UPLOAD_STATS_LOCK:
        return {
            "backend": _backend_name(),
            "object_storage_enabled": is_object_storage_enabled(),
            "stats": dict(_UPLOAD_STATS),
        }
