# PostgreSQL 전환 체크리스트

## 목적
- 운영 시작 전에 SQLite 기반 데이터를 PostgreSQL로 이관
- 이관 후 최소 검증을 거친 뒤 런타임 DB를 PostgreSQL로 전환
- 문제 발생 시 빠르게 SQLite로 롤백

## 사전 준비
1. PostgreSQL 데이터베이스 생성
2. 운영 계정 생성
3. `deploy/.env.production.example` 기반 환경 변수 준비
4. 기존 SQLite 백업 생성

```powershell
.\.venv\Scripts\python scripts\backup_db.py --db-path .\weave.db --backup-dir .\backups
```

## 이관
```powershell
.\.venv\Scripts\python scripts\migrate_sqlite_to_postgres.py --sqlite .\weave.db --postgres-dsn "postgresql://weave:password@127.0.0.1:5432/weave"
```

## 이관 후 검증
1. 테이블 건수 비교
```powershell
.\.venv\Scripts\python scripts\compare_sqlite_postgres_counts.py --sqlite .\weave.db --postgres-dsn "postgresql://weave:password@127.0.0.1:5432/weave"
```

2. 운영 전 점검
```powershell
$env:WEAVE_ENV='production'
$env:DATABASE_URL='postgresql://weave:password@127.0.0.1:5432/weave'
$env:WEAVE_STORAGE_BACKEND='r2'
$env:WEAVE_MEDIA_QUEUE_BACKEND='rq'
$env:WEAVE_REDIS_URL='redis://127.0.0.1:6379/0'
$env:WEAVE_REQUIRE_EXTERNAL_SERVICES='1'
.\.venv\Scripts\python scripts\preflight_ops_check.py --env production
```

3. 앱 실행 후 확인
- `/healthz`
- `/metrics`
- 이미지 업로드 1건
- 갤러리/공지 목록 조회
- 게시글 상세 이미지 확인

## 전환 기준
- `compare_sqlite_postgres_counts.py` 에서 핵심 테이블 mismatch 0
- `/metrics.database_mode == postgres`
- 업로드/목록/상세/댓글 핵심 기능 이상 없음

## 롤백 절차
1. 앱 중지
2. `DATABASE_URL` 을 SQLite 값으로 복원
3. `WEAVE_REQUIRE_EXTERNAL_SERVICES=0` 또는 제거
4. 앱 재시작
5. `/healthz`, 주요 화면 확인

## 롤백 조건 예시
- PostgreSQL 연결 불안정
- 핵심 테이블 건수 mismatch
- 이미지/게시글 조회 이상
- 쓰기 요청(공지/갤러리 작성) 실패
