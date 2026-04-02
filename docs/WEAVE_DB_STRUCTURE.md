# 위브 DB 구조 정리 메모

## 기준
- Flask 업로드 패턴: <https://flask.palletsprojects.com/en/stable/patterns/fileuploads/>
- MDN `multiple` 파일 입력: <https://developer.mozilla.org/en-US/docs/Web/HTML/Element/input/file>
- SQLite Foreign Keys: <https://sqlite.org/foreignkeys.html>

위 자료를 기준으로, 현재 위브는 "글 본문/첨부/댓글/추천/일정/신청"이 서로 느슨하게 연결된 부분을 우선 정리 대상으로 봅니다.

## 현재 운영 기준 핵심 테이블
- `users`: 사용자, 역할, 상태
- `posts`: 공지/FAQ/Q&A/갤러리의 공통 본문
- `post_files`: 게시글 업로드 파일
- `comments`: 댓글
- `recommends`: 추천
- `activities`: 공지와 연동되는 봉사 일정
- `activity_applications`: 일정 신청
- `in_app_notifications`: 앱 내 알림
- `audit_logs`: 감사 로그

## 현재 구조에서 보이는 문제
- `posts`와 별도로 `gallery_albums`, `gallery_photos`, `qna_posts` 같은 레거시성 테이블이 남아 있어 실제 운영 중심 모델이 흐려짐
- SQLite 외래키 기준으로 보면 테이블 간 참조 의도는 있으나, 실제 제약과 점검 자동화가 약함
- 갤러리 활동 기간이 프런트 캐시에만 남는 흐름이 있어 재동기화/다른 PC에서 정보 손실 위험이 있었음
- 업로드 기능은 `posts + post_files`가 핵심인데, 일부 기능은 여전히 로컬 캐시 저장에 크게 의존함

## 이번 정리 방향
1. 글 본문 모델은 `posts`를 단일 진실원본으로 유지
2. 첨부/이미지는 `post_files`로 분리 유지
3. 갤러리 활동 기간도 `posts.volunteer_start_date`, `posts.volunteer_end_date`에 저장
4. 일정-공지 연결은 `activities.notice_post_id`를 기준으로 유지
5. 로컬 스토리지는 서버 데이터를 보조하는 캐시로만 취급

## 권장 운영 모델
### 콘텐츠
- `posts`
  - `category`: `notice`, `faq`, `qna`, `gallery`
  - `title`, `content`
  - `image_url`, `thumb_url`
  - `volunteer_start_date`, `volunteer_end_date`
  - `publish_at`, `status`
  - `author_id`, `created_at`, `updated_at`

### 첨부
- `post_files`
  - `post_id`
  - `stored_path`, `mime_type`, `size`, `hash_sha256`
  - 필요 시 만료 정책 `expires_at`

### 커뮤니티
- `comments`
- `recommends`

### 봉사 운영
- `activities`
- `activity_applications`
- `event_attendance`
- `volunteer_activity`

### 운영 추적
- `audit_logs`
- `in_app_notifications`

## 레거시 테이블 정책
- `gallery_albums`, `gallery_photos`, `qna_posts`는 즉시 삭제하지 않고 유지
- 다만 신규 기능은 `posts` 중심으로만 확장
- 실제 사용량/참조 여부를 점검한 뒤 별도 마이그레이션 브랜치에서 제거 검토

## 점검 항목
- 고아 `post_files` 존재 여부
- 고아 `comments`/`recommends` 존재 여부
- `activities.notice_post_id`가 삭제된 공지를 참조하는지 여부
- `activity_applications.activity_id`가 삭제된 일정 참조 여부

## 실행 스크립트
```powershell
.\.venv\Scripts\python scripts\check_db_structure_health.py
```

이 스크립트는 위 핵심 연결 관계의 고아 데이터와 기본 건수를 점검합니다.
