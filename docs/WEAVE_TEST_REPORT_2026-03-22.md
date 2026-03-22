# 위브(Weave) 테스트 리포트

- 작성일: 2026-03-22
- 작성자: Codex

## 1) 실행 환경
- OS: Windows (PowerShell)
- Python: venv 환경 사용
- 브라우저 자동 E2E: 샌드박스 제약으로 일부 실행 제한(spawn EPERM)

## 2) 자동 테스트 결과
### 백엔드/통합
- 명령: `D:/Blog/Weave/venv/Scripts/python.exe -m pytest -q`
- 결과: PASS (전체 통과)

### 프론트 정적 점검
- 명령: `npm run -s lint:frontend`
- 결과: PASS

### static-root 동기화 점검
- 명령: `python scripts/check_static_sync_drift.py`
- 결과: PASS

## 3) 수동 스모크 점검
- 로컬 서버 구동 후 홈 진입/네비/모달 구조 확인
- 확인 항목:
  - 홈/네비/모바일 오프캔버스 렌더
  - 로그인/회원가입/계정찾기 UI 노출
  - 캘린더 및 알림 모달 노출 기본 동작

## 4) 이번 수정 사항
- 글쓰기 권한 정책 반영
  - 일반/단원은 Q&A만 작성 가능
  - 일반/단원에서 갤러리 관리/홈 통계 관리 탭 숨김
- 명예의 전당 검색 버튼 세로깨짐 수정
  - 검색 버튼 가로 텍스트 고정 및 최소 너비 적용
- 구조 안정성 보강
  - Bootstrap 미로딩 환경에서 일부 예외 방지 가드 추가

## 5) 리스크/제약
- 샌드박스에서 Playwright worker spawn 제한으로 전체 E2E 자동화 미실행
- CDN 리소스 차단 환경에서 스타일/스크립트가 일부 축소 로딩될 수 있음

## 6) 권장 후속
- CI에서 E2E를 별도 러너(제한 없는 환경)로 분리 실행
- Bootstrap/CSS 외부 CDN에 대한 로컬 fallback 정식 적용
- 월간 회귀 테스트 기준선(test baseline) 버전 관리
