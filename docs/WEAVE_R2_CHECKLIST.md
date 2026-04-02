# R2 운영 체크리스트

## 목적
- 위브 이미지/첨부 저장소를 로컬 디스크 대신 Cloudflare R2 로 분리
- CDN 까지 연결해 초기 대량 이미지 업로드와 조회를 안정화

## 준비 항목
1. R2 버킷 생성
2. Access Key 생성
3. Public base URL 또는 CDN 도메인 준비
4. 앱 환경 변수 설정

## 필수 환경 변수
```env
WEAVE_STORAGE_BACKEND=r2
WEAVE_S3_BUCKET=weave-prod
WEAVE_S3_ENDPOINT_URL=https://<accountid>.r2.cloudflarestorage.com
WEAVE_S3_REGION=auto
WEAVE_S3_ACCESS_KEY_ID=...
WEAVE_S3_SECRET_ACCESS_KEY=...
WEAVE_S3_PUBLIC_BASE_URL=https://pub-xxxxxxxx.r2.dev
WEAVE_CDN_BASE_URL=https://cdn.weave.example.com
```

## 확인 항목
1. 앱 시작 로그에 storage backend 경고가 없는지 확인
2. `/metrics` 의 `storage.backend` 가 `r2` 인지 확인
3. 게시글 이미지 업로드 후 `post_files.stored_path` 가 `obj://` 로 저장되는지 확인
4. 목록/상세 이미지가 정상 표시되는지 확인

## 권장 정책
- 원본은 R2 에 저장
- 썸네일/WebP 는 워커가 별도 생성
- 공개 전달은 CDN URL 사용
- 원본 직접 URL 노출 최소화

## 장애 시 1차 점검
- `WEAVE_S3_BUCKET`
- `WEAVE_S3_ENDPOINT_URL`
- `WEAVE_S3_ACCESS_KEY_ID`
- `WEAVE_S3_SECRET_ACCESS_KEY`
- CDN 도메인 캐시/권한 설정

## 운영 팁
- 초기 과거 이미지 이관은 한 번에 전부 브라우저 업로드하지 말고, 서버 배치/스크립트로 나누어 넣는 편이 안전합니다.
- 운영 시작 후에는 앱 서버 디스크 용량보다 R2 사용량/전송량 모니터링이 더 중요합니다.
