# Weave 운영 배포 가이드 (실도메인 + 100명 동시접속 기준)

## 1) 사전 준비
- Python 3.11+
- `pip install -r requirements.txt`
- 운영 환경변수 설정

권장 환경변수:
- `WEAVE_SECRET_KEY`: 32자 이상 랜덤 문자열 (필수)
- `WEAVE_TRUSTED_HOSTS`: `weave.com,www.weave.com`
- `WEAVE_PROXY_HOPS`: `1` (Nginx/ALB 뒤 1단 프록시 기준)
- `WEAVE_SESSION_SECURE`: `1` (HTTPS에서만 쿠키 전송)
- `WEAVE_SESSION_SAMESITE`: `Lax`
- `WEAVE_MAX_CONTENT_LENGTH`: `1048576`

## 2) 운영 실행 (Linux 권장)
### Gunicorn (권장)
```bash
gunicorn -c gunicorn.conf.py wsgi:application
```

기본값은 `4 workers x 8 threads`이며 간단한 블로그 API 기준 100명 이상 동시 요청을 처리할 수 있도록 설정되어 있습니다.

## 3) 운영 실행 (Windows)
### Waitress
```bash
waitress-serve --listen=0.0.0.0:8000 --threads=16 wsgi:application
```

## 4) 도메인 연결/Nginx 예시
- DNS A 레코드: `@` / `www` -> 서버 IP
- TLS: Let's Encrypt 권장

Nginx 핵심 예시:
```nginx
server {
    listen 80;
    server_name weave.com www.weave.com;
    return 301 https://$host$request_uri;
}

server {
    listen 443 ssl http2;
    server_name weave.com www.weave.com;

    # ssl_certificate /etc/letsencrypt/live/weave.com/fullchain.pem;
    # ssl_certificate_key /etc/letsencrypt/live/weave.com/privkey.pem;

    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
```

## 5) 상태 확인
- 헬스체크: `GET /healthz`
- 응답 예시: `{ "success": true, "data": { "status": "healthy", "db": "ok" } }`

## 6) 성능 점검 권장
실서비스 오픈 전 최소 100 동시 사용자를 시뮬레이션하세요.

예시(로컬):
- k6, Locust, JMeter 중 1개 선택
- 목표: 로그인/회원가입 API가 p95 1초 이내, 에러율 1% 이하

### 현재 저장소에서 즉시 검증하는 방법
아래 1개 명령으로 서버 실행 + 부하테스트 + 임계치 판정까지 자동 수행됩니다.

```bash
npm run test:load
```

기본 검증 기준:
- 동시 사용자: 120명
- p95 응답시간: 1000ms 이하
- 실패율: 1% 이하
- 총 요청수: 500건 이상

산출물:
- `loadtests/results/weave_stats.csv`

임계치 변경 예시(Windows PowerShell):
```powershell
./scripts/verify_load.ps1 -Users 150 -RunTime 2m -MaxP95Ms 1200 -MaxFailureRatio 0.02
```

## 7) 운영 체크리스트
- 디버그 모드 비활성화 (`debug=False`)
- 기본 시크릿키 미사용
- HTTPS 강제
- 도메인을 `WEAVE_TRUSTED_HOSTS`에 등록
- 로그/백업(weave.db) 주기 설정

## 8) DB 백업/복구

### 백업 실행 (SQLite .backup API)
```bash
python scripts/backup_db.py --db-path ./weave.db --backup-dir ./backups
```

백업 정책:
- 일별 백업 7개 유지 (`daily-YYYYMMDD.db`)
- 주별 백업 4개 유지 (`weekly-YYYY-Www.db`)

### 복구 실행
```bash
python scripts/restore_db.py --backup ./backups/daily-20260304.db --target ./weave.db
```

복구 권장 절차:
1. 앱 프로세스 중지 (`gunicorn`/`waitress`)
2. 현재 DB 파일 별도 보관
3. `restore_db.py` 실행
4. `/healthz` 호출로 DB 연결 상태 확인
5. 앱 재기동 후 핵심 API 스모크 테스트

## 9) 알림 배치(크론)

이벤트 24시간 전 리마인더 발송:
```bash
python scripts/send_due_notifications.py
```

크론 예시(매시간):
```cron
0 * * * * /usr/bin/python /opt/weave/scripts/send_due_notifications.py
```

## 10) PostgreSQL 전환 준비(Alembic)

`DATABASE_URL`을 설정하면 Alembic/SQLAlchemy가 해당 DB를 사용합니다.

```bash
set DATABASE_URL=postgresql+psycopg2://user:pass@host:5432/weave
alembic upgrade head
```

SQLite 유지 시:
```bash
set DATABASE_URL=sqlite:///weave.db
alembic upgrade head
```
