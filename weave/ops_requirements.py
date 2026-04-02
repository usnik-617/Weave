from __future__ import annotations

import os
from typing import Any


def _is_truthy(value: str | None) -> bool:
    return str(value or '').strip().lower() in {'1', 'true', 'yes', 'on'}


def validate_runtime_separation() -> dict[str, Any]:
    env = str(os.environ.get('WEAVE_ENV', 'development') or 'development').strip().lower()
    database_url = str(os.environ.get('DATABASE_URL', '') or '').strip()
    storage_backend = str(os.environ.get('WEAVE_STORAGE_BACKEND', 'local') or 'local').strip().lower()
    queue_backend = str(os.environ.get('WEAVE_MEDIA_QUEUE_BACKEND', 'rq') or 'rq').strip().lower()
    strict = _is_truthy(os.environ.get('WEAVE_REQUIRE_EXTERNAL_SERVICES'))

    issues: list[str] = []
    warnings: list[str] = []

    db_mode = 'postgres' if database_url.lower().startswith('postgres') else 'sqlite'
    object_storage = storage_backend in {'s3', 'r2', 'minio'}

    if env == 'production':
        if db_mode != 'postgres':
            issues.append('운영 모드에서는 PostgreSQL 사용을 권장합니다. 현재 DATABASE_URL이 SQLite 기준입니다.')
        if not object_storage:
            issues.append('운영 모드에서는 WEAVE_STORAGE_BACKEND를 s3/r2/minio 중 하나로 설정하는 것을 권장합니다.')
        if queue_backend == 'inline':
            issues.append('운영 모드에서는 썸네일/파생파일 생성을 inline 대신 rq 또는 local 워커로 분리하는 것을 권장합니다.')
        if object_storage:
            if not str(os.environ.get('WEAVE_S3_BUCKET', '') or '').strip():
                issues.append('오브젝트 스토리지 사용 시 WEAVE_S3_BUCKET이 필요합니다.')
            if not str(os.environ.get('WEAVE_S3_ENDPOINT_URL', '') or '').strip():
                warnings.append('WEAVE_S3_ENDPOINT_URL이 비어 있습니다. S3 호환 스토리지(R2/MinIO)라면 endpoint 설정을 확인하세요.')
        if queue_backend == 'rq' and not str(os.environ.get('WEAVE_REDIS_URL', '') or '').strip():
            issues.append('WEAVE_MEDIA_QUEUE_BACKEND=rq 인 경우 WEAVE_REDIS_URL이 필요합니다.')
        if object_storage and not str(os.environ.get('WEAVE_CDN_BASE_URL', '') or '').strip():
            warnings.append('운영 모드에서 CDN URL이 비어 있습니다. 이미지 대량 트래픽 분산을 위해 CDN 연결을 권장합니다.')
    else:
        if db_mode != 'postgres':
            warnings.append('현재는 SQLite 모드입니다. 운영 전 PostgreSQL 전환이 필요합니다.')
        if not object_storage:
            warnings.append('현재는 로컬 파일 저장소입니다. 운영 전 오브젝트 스토리지 전환을 권장합니다.')

    return {
        'env': env,
        'strict': strict,
        'db_mode': db_mode,
        'storage_backend': storage_backend,
        'queue_backend': queue_backend,
        'issues': issues,
        'warnings': warnings,
    }


def enforce_runtime_separation(logger=None) -> dict[str, Any]:
    report = validate_runtime_separation()
    target_logger = logger
    if target_logger:
        for message in report['warnings']:
            target_logger.warning('[ops] %s', message)
        for message in report['issues']:
            target_logger.error('[ops] %s', message)
    if report['strict'] and report['issues']:
        raise RuntimeError(' | '.join(report['issues']))
    return report
