# 운영 분리 구조 가이드

## 권장 운영 구조
- 웹 앱: Flask/Waitress(or Gunicorn)
- 데이터베이스: PostgreSQL
- 이미지/첨부: R2/S3/MinIO 같은 오브젝트 스토리지
- 파생파일 생성: RQ + Redis 워커
- 전달 가속: CDN

## 왜 이렇게 분리하나
- 초기 업로드 이미지가 1000장 이상일 때 서버 디스크와 앱 프로세스 부담을 줄일 수 있습니다.
- 앱 서버 재배포/이전 시 이미지 유실 위험이 줄어듭니다.
- DB 백업과 파일 백업을 따로 가져갈 수 있어 복구가 쉬워집니다.

## 필수 환경 변수
- 예시 파일: `deploy/.env.production.example`
- 운영 모드 강제 체크:
  - `WEAVE_REQUIRE_EXTERNAL_SERVICES=1`
  - 이 값을 켜면 운영 모드에서 SQLite/로컬 스토리지/inline 파생파일 생성 같은 구성이 남아 있을 때 앱 시작을 막습니다.

## 운영 시작 전 순서
1. PostgreSQL 준비
2. R2/S3/MinIO 버킷 준비
3. Redis 준비
4. `deploy/.env.production.example` 기반 환경 변수 설정
5. `python scripts/preflight_ops_check.py --env production`
6. SQLite -> PostgreSQL 데이터 이관
   - `python scripts/migrate_sqlite_to_postgres.py --sqlite weave.db --postgres-dsn "postgresql://..."`
7. RQ 워커 실행
   - `python scripts/run_rq_worker.py`
8. 앱 실행 후 `/healthz` 와 `/metrics` 확인

## 백업
### PostgreSQL
```powershell
.\.venv\Scripts\python scripts\backup_postgres.py --dsn "postgresql://weave:password@127.0.0.1:5432/weave"
```

### SQLite 개발 백업
```powershell
.\.venv\Scripts\python scripts\backup_db.py --db-path .\weave.db --backup-dir .\backups
```

## 점검 포인트
- `/metrics` 에서 `database_mode` 가 `postgres` 인지 확인
- `/metrics` 의 `storage.backend` 가 `r2`, `s3`, `minio` 중 하나인지 확인
- `/metrics` 의 `media_queue.backend` 가 `rq` 또는 `local` 인지 확인
- 썸네일 생성이 워커에서 처리되는지 확인

## 참고 문서
- Flask file uploads: https://flask.palletsprojects.com/en/stable/patterns/fileuploads/
- PostgreSQL backup: https://www.postgresql.org/docs/14/backup-dump.html
- SQLite foreign keys: https://sqlite.org/foreignkeys.html
