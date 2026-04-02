# 운영 빠른 실행 순서

## 1. 운영 환경 변수 준비
- 기준 파일: `deploy/.env.production.example`
- 실제 값으로 채운 뒤 PowerShell 세션 또는 서비스 환경에 반영

## 2. 운영 전 점검
```powershell
.\scripts\ops_preflight_production.ps1
```

## 3. SQLite -> PostgreSQL 이관
```powershell
.\scripts\ops_postgres_cutover.ps1 -PostgresDsn "postgresql://weave:password@127.0.0.1:5432/weave"
```

## 4. RQ 워커 실행
```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\run_rq_worker.ps1
```

## 5. 앱 실행 후 확인
- `/healthz`
- `/metrics`
- 이미지 업로드 1건
- 공지/갤러리 목록과 상세 확인

## 6. PostgreSQL 백업
```powershell
.\.venv\Scripts\python scripts\backup_postgres.py --dsn "postgresql://weave:password@127.0.0.1:5432/weave"
```

## 7. 롤백
- `DATABASE_URL` 을 SQLite 값으로 복원
- `WEAVE_REQUIRE_EXTERNAL_SERVICES=0` 또는 제거
- 앱 재시작
