# TESTING

관련 문서:
- 레거시 응답 전환 계획: `LEGACY_RESPONSE_MIGRATION.md`

Weave 저장소의 테스트는 `tests/` 디렉터리 하나에서 **pytest(.py)** 와 **Playwright(.spec.js)** 를 함께 운용한다.
이 문서는 현재 저장소 설정(`pyproject.toml`, `playwright.config.js`, `package.json`) 기준의 실행 흐름을 정리한다.

## 1. 테스트 종류와 책임

### A. pytest (서버/정책/계약 고정)
- 파일 패턴: `tests/test_*.py`
- 주요 책임:
  - API 응답 계약 고정(키/상태코드/권한)
  - 정책 로직 고정(권한, rate-limit, upload 정책, 카테고리 정책)
  - 서비스/라우팅 스모크 고정(앱 초기화, SPA 라우팅, 레거시 import 가드)
- 예시 파일:
  - `tests/test_posts_routes_contract.py`
  - `tests/test_auth_routes_contract.py`
  - `tests/test_upload_policy.py`
  - `tests/test_smoke_routing.py`
  - `tests/test_about_routes_contract.py`

### B. Playwright (브라우저/E2E 흐름 고정)
- 파일 패턴: `tests/*.spec.js`
- 주요 책임:
  - 실제 브라우저에서 사용자 플로우가 끝까지 동작하는지 검증
  - 프론트-백 통합 동작(페이지 이동, 폼 입력, API 연계) 검증
- 예시 파일:
  - `tests/routing-smoke.spec.js`
  - `tests/auth-and-write.spec.js`
  - `tests/api-regression.spec.js`

## 2. 실행 명령 (현재 저장소 기준)

## 사전 준비
1. Python 의존성 설치
```bash
pip install -r requirements-dev.txt
```
2. Node 의존성 설치
```bash
npm install
```

## pytest 실행
- 전체 pytest
```bash
python -m pytest
```
- 빠른 계약 스모크
```bash
npm run test:quick
```
- 전체 회귀(서버 + E2E)
```bash
npm run test:full
```
- 특정 파일만 실행
```bash
python -m pytest tests/test_posts_routes_contract.py
```

참고:
- `pyproject.toml`에서 `testpaths = ["tests"]`, `addopts = "-q"`가 설정되어 있어 기본 출력은 간결 모드다.

## Playwright 실행
- 권장(정적 루트 동기화 포함):
```bash
npm run test:e2e
```
  - 내부적으로 `npm run sync:static-root && playwright test` 순서로 실행된다.
  - 동기화의 기준 원본은 `static/`이며, 루트 `index.html`, `styles.css`, `js/*`는 미러 파일이다.
- Playwright 단독 실행(필요 시):
```bash
npx playwright test
```

- 전체 E2E(상세 리포터):
```bash
npm run test:e2e:full
```

Windows PowerShell 참고:
- 실행 정책으로 `npm` 호출이 차단될 수 있으므로, 이 경우 `npm.cmd`를 사용한다.
- 예시: `npm.cmd run test:e2e`

## 프론트 품질/동기화 점검

- 프론트 가드레일 + CSS 중복 블록 검사:
```bash
npm run lint:frontend
```
- `static -> root` 미러 동기화 드리프트 검사:
```bash
npm run check:sync-static-root
```

참고:
- `playwright.config.js` 기준:
  - `testDir: ./tests`
  - 웹서버 자동 기동: `python app.py`
  - 기본 URL: `http://127.0.0.1:5111`
  - DB 경로: `instance/playwright.db`

## 3. 언제 어떤 테스트를 돌릴지

### 빠른 로컬 확인 (개발 중)
1. 변경한 서버 모듈과 관련된 pytest 파일만 먼저 실행
2. API 계약/권한 변경이 있으면 관련 contract pytest까지 확장

### PR 전 기본 확인
1. `python -m pytest`
2. `npm run test:e2e`

### 릴리즈/운영 반영 전
1. 전체 pytest
2. 전체 Playwright
3. 실패 시 먼저 pytest(정책/계약)를 고정하고, 이후 E2E에서 플로우 재검증

## 4. 새 기능 추가 시 테스트 우선순위

1. **pytest 우선**
- 새 정책/권한/응답 스키마를 먼저 고정한다.
- 이유: 실패 원인 분리가 쉽고, 디버깅 비용이 낮다.

2. **Playwright는 핵심 사용자 흐름만 추가**
- 사용자 관점에서 실제로 클릭/입력/전환이 중요한 시나리오만 추가한다.

3. 권장 순서
- 단위/서비스 성격 로직 -> pytest
- API contract/권한 -> pytest
- 화면에서 끝까지 이어지는 대표 플로우 -> Playwright

## 5. 중복 테스트를 피하는 기준

1. 동일 책임을 두 프레임워크에 중복으로 쓰지 않는다.
- 권한/상태코드/응답 키 검증: pytest에서 고정
- 브라우저 상호작용/실사용 흐름: Playwright에서 고정

2. Playwright에서 세부 정책 분기까지 모두 재검증하지 않는다.
- 이미 pytest가 고정한 정책은 E2E에서 대표 경로만 확인한다.

3. pytest에서 DOM/렌더링 결과를 검증하지 않는다.
- UI/동선 검증은 Playwright로 한정한다.

## 6. 운영/유지보수 체크리스트

1. 테스트 추가 시 파일 패턴을 지킨다.
- 서버/정책/계약: `tests/test_*.py`
- 브라우저 플로우: `tests/*.spec.js`

2. 회귀 테스트는 "변경 지점 근처 + 계약"을 같이 본다.
- 예: posts 변경 시 posts contract + 관련 policy + 최소 E2E 1개

3. 실패 해석 우선순위
- pytest 실패: 서버 로직/계약 문제를 먼저 수정
- Playwright 실패: UI 플로우/통합 환경 문제를 이후 점검

## 7. Flake 대응 가이드

1. rate-limit 민감 테스트는 독립 실행을 우선한다.
- 예: 업로드 권한/차단 계약 테스트는 해당 파일만 먼저 실행해 원인 범위를 좁힌다.

2. 한 테스트 안에서 같은 엔드포인트를 연속 호출할 때는 상태 간섭을 점검한다.
- 필요 시 테스트 fixture를 통해 rate-limit 상태를 초기화하고 권한/계약 검증을 분리한다.

3. 재실행 순서 권장
- 1차: 실패한 pytest 파일 단독 재실행
- 2차: 관련 계약 묶음 재실행
- 3차: 전체 pytest 및 E2E 재검증
