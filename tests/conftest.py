from __future__ import annotations

from pathlib import Path
import shutil
import uuid

import pytest


@pytest.fixture()
def app(monkeypatch: pytest.MonkeyPatch):
    root = Path(__file__).resolve().parents[1]
    test_root = root / "instance" / "pytest_runtime" / uuid.uuid4().hex
    db_path = test_root / "test_weave.db"
    upload_dir = test_root / "uploads"
    test_root.mkdir(parents=True, exist_ok=True)
    upload_dir.mkdir(parents=True, exist_ok=True)

    monkeypatch.setenv("WEAVE_DB_PATH", str(db_path))
    monkeypatch.delenv("WEAVE_HEALTH_TOKEN", raising=False)
    monkeypatch.delenv("WEAVE_HEALTH_ALLOW_IPS", raising=False)

    import weave.core as core
    import weave.post_files_routes as post_files_routes
    import weave.posts_routes as posts_routes
    from weave import create_app

    old_db_path = core.DB_PATH
    old_database_url = core.DATABASE_URL
    old_upload_dir = core.UPLOAD_DIR
    old_post_files_upload_dir = post_files_routes.UPLOAD_DIR
    old_posts_upload_dir = posts_routes.UPLOAD_DIR

    core.DB_PATH = str(db_path)
    core.DATABASE_URL = f"sqlite:///{db_path}"
    core.UPLOAD_DIR = str(upload_dir)

    # Keep upload URL/path conversion consistent in modules that imported constants.
    post_files_routes.UPLOAD_DIR = str(upload_dir)
    posts_routes.UPLOAD_DIR = str(upload_dir)

    app = create_app()
    app.config.update(TESTING=True)
    try:
        yield app
    finally:
        core.DB_PATH = old_db_path
        core.DATABASE_URL = old_database_url
        core.UPLOAD_DIR = old_upload_dir
        post_files_routes.UPLOAD_DIR = old_post_files_upload_dir
        posts_routes.UPLOAD_DIR = old_posts_upload_dir
        shutil.rmtree(test_root, ignore_errors=True)


@pytest.fixture(autouse=True)
def _reset_rate_limit_state(monkeypatch: pytest.MonkeyPatch):
    import weave.core as core

    monkeypatch.setattr(core, "WEAVE_ENV", "development")
    core.clear_all_rate_limit_state()
    yield
    core.clear_all_rate_limit_state()


@pytest.fixture()
def reset_rate_limit_state():
    import weave.core as core

    def _reset():
        core.clear_all_rate_limit_state()

    return _reset


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
def create_post_record(app):
    def _create_post_record(category="notice", author_id=None, publish_at=None, title=None):
        from weave.core import get_db_connection
        from weave.core import invalidate_cache
        from weave import cache_keys
        from weave.time_utils import now_iso

        conn = get_db_connection()
        cur = conn.cursor()
        now = now_iso()
        title_text = title or f"{category}-post-{now}"
        cur.execute(
            """
            INSERT INTO posts (
                category, title, content, is_pinned, is_important, publish_at, status,
                image_url, thumb_url, volunteer_start_date, volunteer_end_date,
                author_id, created_at, updated_at
            ) VALUES (?, ?, ?, 0, 0, ?, 'published', '', '', NULL, NULL, ?, ?, ?)
            """,
            (str(category).lower(), title_text, "테스트 본문", publish_at, author_id, now, now),
        )
        post_id = cur.lastrowid
        conn.commit()
        conn.close()
        for prefix in cache_keys.POSTS_LIST_PREFIXES:
            invalidate_cache(prefix)
        return post_id

    return _create_post_record


@pytest.fixture()
def role_matrix_cases():
    return [
        (None, 401),
        ("GENERAL", 403),
        ("MEMBER", 200),
        ("EXECUTIVE", 200),
        ("LEADER", 200),
        ("ADMIN", 200),
    ]


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


@pytest.fixture()
def png_file_bytes():
    return (
        b"\x89PNG\r\n\x1a\n"
        b"\x00\x00\x00\rIHDR"
        b"\x00\x00\x00\x01\x00\x00\x00\x01\x08\x02\x00\x00\x00"
        b"\x90wS\xde"
        b"\x00\x00\x00\x0cIDATx\x9cc```\x00\x00\x00\x04\x00\x01"
        b"\x0b\xe7\x02\x9d"
        b"\x00\x00\x00\x00IEND\xaeB`\x82"
    )
