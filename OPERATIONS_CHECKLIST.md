# Weave 운영 시작 기본 점검

운영 오픈 직전에 아래 순서로 점검하세요.

## 1) 자동 점검 실행
```bash
npm run ops:check
```

이 명령은 다음을 자동 점검합니다.
- 필수 파일 존재 여부
- Python 버전
- 운영 환경변수 기본 검증 (`WEAVE_ENV`, `WEAVE_SECRET_KEY`, `WEAVE_TRUSTED_HOSTS`, `WEAVE_PROXY_HOPS`)
- 기본 관리자 시드 비밀번호 문자열 존재 여부
- SQLite 상태 및 `journal_mode`
- `/healthz` 응답

## 2) 수동 점검 (필수)
- DNS 연결: `weave.com`, `www.weave.com`이 운영 서버 IP를 가리키는지 확인
- TLS 인증서: HTTPS 접속 시 경고 없이 유효한지 확인
- 리버스 프록시: HTTP->HTTPS 리다이렉트 및 `X-Forwarded-*` 헤더 전달 확인
- 방화벽: 80/443만 외부 오픈, 내부 포트(예: 8000)는 외부 차단
- 백업: `weave.db` 백업 작업 및 복구 리허설 완료
- 로그: 에러 로그 수집 위치/보존 기간 확인

## 3) 오픈 직후 30분 모니터링
- `/healthz` 5xx 여부
- 로그인/회원가입 실패율 급증 여부
- 평균/95퍼센타일 응답시간 급등 여부
- CPU/메모리 급증 및 프로세스 재시작 여부

## 4) 기준 미달 시
- 즉시 트래픽 제한 또는 점검 페이지 전환
- 최근 설정 변경 롤백
- 원인 파악 후 재오픈
