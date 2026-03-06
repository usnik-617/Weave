from __future__ import annotations

import io
from datetime import datetime, timedelta
from pathlib import Path

import pytest


@pytest.fixture()
def app(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    db_path = tmp_path / "test_authz_permissions.db"
    monkeypatch.setenv("WEAVE_DB_PATH", str(db_path))
    monkeypatch.delenv("WEAVE_HEALTH_TOKEN", raising=False)
    monkeypatch.delenv("WEAVE_HEALTH_ALLOW_IPS", raising=False)

    import weave.core as core
    from weave import create_app

    core.DB_PATH = str(db_path)
    core.DATABASE_URL = f"sqlite:///{db_path}"

    app = create_app()
    app.config.update(TESTING=True)
    return app


@pytest.fixture()
def client(app):
    with app.test_client() as test_client:
        yield test_client


@pytest.fixture()
def create_user(app):
    def _create_user(role="GENERAL", status="active"):
        from weave.core import get_db_connection
        from weave.time_utils import now_iso

        conn = get_db_connection()
        cur = conn.cursor()
        seed = cur.execute("SELECT COALESCE(MAX(id), 0) + 1 AS n FROM users").fetchone()[
            "n"
        ]
        username = f"u{seed}_{str(role).lower()}"
        email = f"{username}@example.com"
        now = now_iso()
        cur.execute(
            """
            INSERT INTO users (
                name, username, email, phone, birth_date, password_hash, join_date,
                role, is_admin, status, nickname, nickname_updated_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                f"User {seed}",
                username,
                email,
                "010-0000-0000",
                "1990-01-01",
                "test-hash",
                now,
                str(role).upper(),
                1 if str(role).upper() == "ADMIN" else 0,
                status,
                username,
                now,
            ),
        )
        user_id = cur.lastrowid
        conn.commit()
        row = conn.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()
        conn.close()
        return row

    return _create_user


@pytest.fixture()
def login_as(client):
    def _login_as(user_row=None):
        with client.session_transaction() as sess:
            if user_row:
                sess["user_id"] = int(user_row["id"])
            else:
                sess.pop("user_id", None)
            sess["csrf_token"] = "test-csrf-token"

    return _login_as


@pytest.fixture()
def csrf_headers(client):
    def _csrf_headers():
        with client.session_transaction() as sess:
            token = sess.get("csrf_token") or "test-csrf-token"
            sess["csrf_token"] = token
        return {"X-CSRF-Token": token}

    return _csrf_headers


@pytest.fixture()
def sample_notice_post(app):
    def _sample_notice_post(author_id=None):
        from weave.core import get_db_connection
        from weave.time_utils import now_iso

        conn = get_db_connection()
        cur = conn.cursor()
        now = now_iso()
        cur.execute(
            """
            INSERT INTO posts (
                category, title, content, is_pinned, is_important, publish_at, status,
                image_url, thumb_url, volunteer_start_date, volunteer_end_date,
                author_id, created_at, updated_at
            ) VALUES (?, ?, ?, 0, 0, NULL, 'published', '', '', NULL, NULL, ?, ?, ?)
            """,
            ("notice", "테스트 공지", "공지 본문", author_id, now, now),
        )
        post_id = cur.lastrowid
        conn.commit()
        conn.close()
        return post_id

    return _sample_notice_post


@pytest.fixture()
def sample_gallery_post(app):
    def _sample_gallery_post(author_id=None):
        from weave.core import get_db_connection
        from weave.time_utils import now_iso

        conn = get_db_connection()
        cur = conn.cursor()
        now = now_iso()
        cur.execute(
            """
            INSERT INTO posts (
                category, title, content, is_pinned, is_important, publish_at, status,
                image_url, thumb_url, volunteer_start_date, volunteer_end_date,
                author_id, created_at, updated_at
            ) VALUES (?, ?, ?, 0, 0, NULL, 'published', '', '', NULL, NULL, ?, ?, ?)
            """,
            ("gallery", "테스트 갤러리", "갤러리 본문", author_id, now, now),
        )
        post_id = cur.lastrowid
        conn.commit()
        conn.close()
        return post_id

    return _sample_gallery_post


@pytest.fixture()
def sample_event(app):
    def _sample_event(author_id=None):
        from weave.core import get_db_connection
        from weave.time_utils import now_iso

        conn = get_db_connection()
        cur = conn.cursor()
        now = now_iso()
        cur.execute(
            """
            INSERT INTO events (
                title, description, location, event_date, max_participants,
                supplies, notice_post_id, start_datetime, end_datetime, capacity,
                created_by, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                "테스트 이벤트",
                "설명",
                "장소",
                "2099-01-01T10:00:00",
                10,
                "준비물",
                None,
                "2099-01-01T10:00:00",
                "2099-01-01T12:00:00",
                10,
                author_id,
                now,
                now,
            ),
        )
        event_id = cur.lastrowid
        conn.commit()
        conn.close()
        return event_id

    return _sample_event


@pytest.fixture()
def sample_role_request(app):
    def _sample_role_request(user_id, from_role="GENERAL", to_role="MEMBER"):
        from weave.core import get_db_connection
        from weave.time_utils import now_iso

        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute(
            """
            INSERT INTO role_requests (user_id, from_role, to_role, status, created_at)
            VALUES (?, ?, ?, 'PENDING', ?)
            """,
            (user_id, from_role, to_role, now_iso()),
        )
        request_id = cur.lastrowid
        conn.commit()
        conn.close()
        return request_id

    return _sample_role_request


# A. General user

def test_general_can_view_public_posts(client, create_user, login_as, sample_notice_post):
    general = create_user(role="GENERAL")
    sample_notice_post(author_id=general["id"])
    login_as(general)

    response = client.get("/api/posts?type=notice")

    assert response.status_code == 200


def test_general_cannot_comment_notice_or_gallery(
    client,
    create_user,
    login_as,
    csrf_headers,
    sample_notice_post,
    sample_gallery_post,
):
    general = create_user(role="GENERAL")
    login_as(general)
    headers = csrf_headers()

    notice_id = sample_notice_post()
    gallery_id = sample_gallery_post()

    notice_res = client.post(
        f"/api/posts/{notice_id}/comments",
        json={"content": "댓글"},
        headers=headers,
    )
    gallery_res = client.post(
        f"/api/posts/{gallery_id}/comments",
        json={"content": "댓글"},
        headers=headers,
    )

    assert notice_res.status_code == 403
    assert gallery_res.status_code == 403


def test_general_cannot_view_event_details_or_join(
    client, create_user, login_as, csrf_headers, sample_event
):
    general = create_user(role="GENERAL")
    event_id = sample_event(author_id=general["id"])
    login_as(general)

    detail_res = client.get(f"/api/events/{event_id}")
    join_res = client.post(f"/api/events/{event_id}/join", headers=csrf_headers())

    assert detail_res.status_code == 403
    assert join_res.status_code == 403


def test_general_cannot_create_notice_or_gallery_posts(
    client, create_user, login_as, csrf_headers
):
    general = create_user(role="GENERAL")
    login_as(general)
    headers = csrf_headers()

    notice_res = client.post(
        "/api/posts",
        json={"category": "notice", "title": "공지", "content": "본문"},
        headers=headers,
    )
    gallery_res = client.post(
        "/api/posts",
        json={"category": "gallery", "title": "갤러리", "content": "본문"},
        headers=headers,
    )

    assert notice_res.status_code == 403
    assert gallery_res.status_code == 403


def test_general_can_create_qna_when_policy_allows(client, create_user, login_as, csrf_headers):
    general = create_user(role="GENERAL")
    login_as(general)

    response = client.post(
        "/api/posts",
        json={"category": "qna", "title": "질문", "content": "질문 본문"},
        headers=csrf_headers(),
    )

    assert response.status_code == 201


def test_gallery_post_does_not_auto_create_calendar_activity(
    client, create_user, login_as, csrf_headers
):
    import time

    executive = create_user(role="EXECUTIVE")
    login_as(executive)
    headers = csrf_headers()
    unique = int(time.time() * 1000)
    gallery_title = f"갤러리 업로드 {unique}"
    notice_title = f"소식 봉사 일정 {unique}"

    gallery_res = client.post(
        "/api/posts",
        json={
            "category": "gallery",
            "title": gallery_title,
            "content": "본문",
            "volunteerStartDate": "2026-04-11",
            "volunteerEndDate": "2026-04-12",
        },
        headers=headers,
    )
    assert gallery_res.status_code == 201

    notice_res = client.post(
        "/api/posts",
        json={
            "category": "notice",
            "title": notice_title,
            "content": "본문",
            "volunteerStartDate": "2026-04-11",
            "volunteerEndDate": "2026-04-12",
        },
        headers=headers,
    )
    assert notice_res.status_code == 201

    from weave.core import get_db_connection

    conn = get_db_connection()
    scoped_rows = conn.execute(
        "SELECT title FROM activities WHERE title IN (?, ?) ORDER BY id ASC",
        (gallery_title, notice_title),
    ).fetchall()
    conn.close()

    titles = [row["title"] for row in scoped_rows]
    assert notice_title in titles
    assert gallery_title not in titles


def test_gallery_rejects_pdf_upload_notice_accepts_pdf_upload(
    client,
    create_user,
    login_as,
    csrf_headers,
    sample_notice_post,
    sample_gallery_post,
):
    executive = create_user(role="EXECUTIVE")
    login_as(executive)
    headers = csrf_headers()

    notice_id = sample_notice_post(author_id=executive["id"])
    gallery_id = sample_gallery_post(author_id=executive["id"])

    notice_upload = client.post(
        f"/api/posts/{notice_id}/files",
        data={"file": (io.BytesIO(b"%PDF-1.4\n%%EOF\n"), "notice-test.pdf", "application/pdf")},
        headers=headers,
        content_type="multipart/form-data",
    )
    gallery_upload = client.post(
        f"/api/posts/{gallery_id}/files",
        data={"file": (io.BytesIO(b"%PDF-1.4\n%%EOF\n"), "gallery-test.pdf", "application/pdf")},
        headers=headers,
        content_type="multipart/form-data",
    )

    assert notice_upload.status_code == 201
    assert gallery_upload.status_code == 400
    payload = gallery_upload.get_json() or {}
    msg = str(payload.get("error") or payload.get("message") or "")
    assert "갤러리" in msg


def test_gallery_list_exposes_thumb_url_after_image_upload(
    client,
    create_user,
    login_as,
    csrf_headers,
    sample_gallery_post,
):
    executive = create_user(role="EXECUTIVE")
    login_as(executive)
    headers = csrf_headers()

    gallery_id = sample_gallery_post(author_id=executive["id"])
    png_bytes = (
        b"\x89PNG\r\n\x1a\n"
        b"\x00\x00\x00\rIHDR"
        b"\x00\x00\x00\x01\x00\x00\x00\x01\x08\x02\x00\x00\x00"
        b"\x90wS\xde"
        b"\x00\x00\x00\x0cIDATx\x9cc```\x00\x00\x00\x04\x00\x01"
        b"\x0b\xe7\x02\x9d"
        b"\x00\x00\x00\x00IEND\xaeB`\x82"
    )
    upload_res = client.post(
        f"/api/posts/{gallery_id}/files",
        data={"file": (io.BytesIO(png_bytes), "gallery-test.png", "image/png")},
        headers=headers,
        content_type="multipart/form-data",
    )
    assert upload_res.status_code == 201

    list_res = client.get("/api/posts?category=gallery&page=1&pageSize=50")
    assert list_res.status_code == 200
    body = list_res.get_json() or {}
    items = (body.get("data") or {}).get("items") or body.get("items") or []
    target = next((it for it in items if int(it.get("id") or 0) == int(gallery_id)), None)
    assert target is not None
    assert "/uploads/" in str(target.get("thumb_url") or "")


def test_scheduled_posts_hidden_for_general_before_publish_at(
    client,
    create_user,
    login_as,
    csrf_headers,
):
    executive = create_user(role="EXECUTIVE")
    general = create_user(role="GENERAL")
    future = (datetime.now() + timedelta(days=2)).replace(microsecond=0).isoformat()

    login_as(executive)
    create_res = client.post(
        "/api/posts",
        json={
            "category": "notice",
            "title": f"예약공지-{int(datetime.now().timestamp())}",
            "content": "예약 테스트",
            "publish_at": future,
        },
        headers=csrf_headers(),
    )
    assert create_res.status_code == 201
    post_id = int((create_res.get_json() or {}).get("data", {}).get("post_id") or 0)
    assert post_id > 0

    login_as(general)
    list_res = client.get("/api/posts?type=notice&pageSize=100")
    assert list_res.status_code == 200
    list_body = list_res.get_json() or {}
    items = (list_body.get("data") or {}).get("items") or list_body.get("items") or []
    assert all(int(item.get("id") or 0) != post_id for item in items)

    detail_res = client.get(f"/api/posts/{post_id}")
    assert detail_res.status_code == 404


# B. Member

def test_member_can_view_join_cancel_events(
    client, create_user, login_as, csrf_headers, sample_event
):
    member = create_user(role="MEMBER")
    event_id = sample_event(author_id=member["id"])
    login_as(member)

    detail_res = client.get(f"/api/events/{event_id}")
    join_res = client.post(f"/api/events/{event_id}/join", headers=csrf_headers())
    cancel_res = client.post(
        f"/api/events/{event_id}/cancel", headers=csrf_headers()
    )

    assert detail_res.status_code == 200
    assert join_res.status_code == 200
    assert cancel_res.status_code == 200


def test_member_can_comment_notice_gallery_but_cannot_create_notice_gallery(
    client,
    create_user,
    login_as,
    csrf_headers,
    sample_notice_post,
    sample_gallery_post,
):
    member = create_user(role="MEMBER")
    login_as(member)
    headers = csrf_headers()

    notice_id = sample_notice_post()
    gallery_id = sample_gallery_post()

    comment_notice = client.post(
        f"/api/posts/{notice_id}/comments",
        json={"content": "단원 댓글"},
        headers=headers,
    )
    comment_gallery = client.post(
        f"/api/posts/{gallery_id}/comments",
        json={"content": "단원 댓글"},
        headers=headers,
    )
    create_notice = client.post(
        "/api/posts",
        json={"category": "notice", "title": "공지", "content": "본문"},
        headers=headers,
    )
    create_gallery = client.post(
        "/api/posts",
        json={"category": "gallery", "title": "갤러리", "content": "본문"},
        headers=headers,
    )

    assert comment_notice.status_code == 201
    assert comment_gallery.status_code == 201
    assert create_notice.status_code == 403
    assert create_gallery.status_code == 403


# C. Executive

def test_executive_can_create_notice_gallery_comment_and_join_event(
    client,
    create_user,
    login_as,
    csrf_headers,
    sample_notice_post,
    sample_event,
):
    executive = create_user(role="EXECUTIVE")
    login_as(executive)
    headers = csrf_headers()

    create_notice = client.post(
        "/api/posts",
        json={"category": "notice", "title": "임원 공지", "content": "본문"},
        headers=headers,
    )
    create_gallery = client.post(
        "/api/posts",
        json={"category": "gallery", "title": "임원 갤러리", "content": "본문"},
        headers=headers,
    )

    notice_id = sample_notice_post(author_id=executive["id"])
    comment_res = client.post(
        f"/api/posts/{notice_id}/comments",
        json={"content": "임원 댓글"},
        headers=headers,
    )

    event_id = sample_event(author_id=executive["id"])
    event_detail = client.get(f"/api/events/{event_id}")
    event_join = client.post(f"/api/events/{event_id}/join", headers=headers)

    assert create_notice.status_code == 201
    assert create_gallery.status_code == 201
    assert comment_res.status_code == 201
    assert event_detail.status_code == 200
    assert event_join.status_code == 200


def test_executive_cannot_access_admin_only_endpoints(client, create_user, login_as):
    executive = create_user(role="EXECUTIVE")
    login_as(executive)

    res_pending = client.get("/api/admin/pending-users")
    res_dashboard = client.get("/api/admin/dashboard")

    assert res_pending.status_code == 403
    assert res_dashboard.status_code == 403


# D. Leader / Vice Leader / Admin

@pytest.mark.parametrize("role", ["LEADER", "VICE_LEADER", "ADMIN"])
def test_admin_like_roles_can_access_admin_pages(
    role, client, create_user, login_as
):
    user = create_user(role=role)
    login_as(user)

    pending_res = client.get("/api/admin/pending-users")
    dashboard_res = client.get("/api/admin/dashboard")

    assert pending_res.status_code == 200
    assert dashboard_res.status_code == 200


@pytest.mark.parametrize("role", ["LEADER", "VICE_LEADER", "ADMIN"])
def test_admin_like_roles_can_approve_role_requests(
    role, client, create_user, login_as, csrf_headers, sample_role_request
):
    reviewer = create_user(role=role)
    target = create_user(role="GENERAL")
    request_id = sample_role_request(target["id"], from_role="GENERAL", to_role="MEMBER")
    login_as(reviewer)

    response = client.post(
        f"/api/admin/role-requests/{request_id}/approve",
        headers=csrf_headers(),
    )

    assert response.status_code == 200


@pytest.mark.parametrize("role", ["LEADER", "VICE_LEADER", "ADMIN"])
def test_admin_like_roles_can_manage_user_and_attendance(
    role,
    client,
    create_user,
    login_as,
    csrf_headers,
    sample_event,
):
    manager = create_user(role=role)
    target = create_user(role="MEMBER")
    event_id = sample_event(author_id=manager["id"])
    login_as(target)
    client.post(f"/api/events/{event_id}/join", headers=csrf_headers())

    login_as(manager)
    suspend_res = client.post(
        f"/api/admin/users/{target['id']}/suspend",
        headers=csrf_headers(),
    )
    attendance_res = client.post(
        f"/api/events/{event_id}/attendance",
        json={"user_id": target["id"], "status": "attended"},
        headers=csrf_headers(),
    )

    assert suspend_res.status_code == 200
    assert attendance_res.status_code == 200


# Representative endpoint groups + unauthenticated checks

def test_unauthenticated_requests_are_blocked_for_login_required_routes(client, login_as):
    login_as(None)

    me_activity = client.get("/api/me/activity")
    events_list = client.get("/api/events")
    admin_page = client.get("/api/admin/pending-users")

    assert me_activity.status_code == 401
    assert events_list.status_code == 401
    assert admin_page.status_code == 401


def test_upload_group_enforces_backend_permission(
    client, create_user, login_as, csrf_headers, sample_notice_post
):
    general = create_user(role="GENERAL")
    post_id = sample_notice_post(author_id=general["id"])
    login_as(general)

    list_res = client.get(f"/api/posts/{post_id}/files")
    upload_res = client.post(
        f"/api/posts/{post_id}/files",
        headers=csrf_headers(),
    )

    assert list_res.status_code == 200
    assert upload_res.status_code == 403
