from __future__ import annotations

from datetime import datetime

from werkzeug.security import check_password_hash, generate_password_hash

from weave.core_db import get_db_connection
from weave.time_utils import now_iso
from weave.user_migrations import ensure_table_indexes, ensure_users_migration


def ensure_posts_migration(cur):
    existing_cols = {
        row["name"] for row in cur.execute("PRAGMA table_info(posts)").fetchall()
    }
    migrations = [
        ("is_important", "INTEGER NOT NULL DEFAULT 0"),
        ("image_url", "TEXT DEFAULT ''"),
        ("thumb_url", "TEXT DEFAULT ''"),
        ("status", "TEXT NOT NULL DEFAULT 'published'"),
        ("volunteer_start_date", "TEXT"),
        ("volunteer_end_date", "TEXT"),
    ]
    for column_name, column_type in migrations:
        if column_name not in existing_cols:
            cur.execute(f"ALTER TABLE posts ADD COLUMN {column_name} {column_type}")

    now_text = now_iso()
    cur.execute(
        """
        UPDATE posts
        SET status = CASE
            WHEN publish_at IS NOT NULL AND publish_at > ? THEN 'scheduled'
            ELSE 'published'
        END
        """,
        (now_text,),
    )


def ensure_activities_migration(cur):
    existing_cols = {
        row["name"] for row in cur.execute("PRAGMA table_info(activities)").fetchall()
    }
    migrations = [
        ("recurrence_group_id", "TEXT DEFAULT ''"),
        ("is_cancelled", "INTEGER NOT NULL DEFAULT 0"),
        ("cancelled_at", "TEXT"),
    ]
    for column_name, column_type in migrations:
        if column_name not in existing_cols:
            cur.execute(
                f"ALTER TABLE activities ADD COLUMN {column_name} {column_type}"
            )


def ensure_activity_indexes(cur):
    cur.execute(
        "CREATE INDEX IF NOT EXISTS idx_activities_start ON activities(start_at)"
    )
    cur.execute(
        "CREATE INDEX IF NOT EXISTS idx_activities_group ON activities(recurrence_group_id)"
    )
    cur.execute(
        "CREATE INDEX IF NOT EXISTS idx_activities_cancelled ON activities(is_cancelled)"
    )


def ensure_events_migration(cur):
    existing_cols = {
        row["name"] for row in cur.execute("PRAGMA table_info(events)").fetchall()
    }
    migrations = [
        ("supplies", "TEXT DEFAULT ''"),
        ("notice_post_id", "INTEGER"),
        ("start_datetime", "TEXT"),
        ("end_datetime", "TEXT"),
        ("capacity", "INTEGER NOT NULL DEFAULT 0"),
    ]
    for column_name, column_type in migrations:
        if column_name not in existing_cols:
            cur.execute(f"ALTER TABLE events ADD COLUMN {column_name} {column_type}")
    cur.execute(
        "UPDATE events SET start_datetime = COALESCE(start_datetime, event_date) WHERE start_datetime IS NULL OR TRIM(start_datetime) = ''"
    )
    cur.execute(
        "UPDATE events SET end_datetime = COALESCE(end_datetime, start_datetime, event_date) WHERE end_datetime IS NULL OR TRIM(end_datetime) = ''"
    )
    cur.execute(
        "UPDATE events SET capacity = COALESCE(capacity, max_participants, 0) WHERE capacity IS NULL"
    )


def ensure_post_files_migration(cur):
    existing_cols = {
        row["name"] for row in cur.execute("PRAGMA table_info(post_files)").fetchall()
    }
    migrations = [
        ("hash_sha256", "TEXT DEFAULT ''"),
        ("created_at", "TEXT"),
        ("expires_at", "TEXT"),
    ]
    for column_name, column_type in migrations:
        if column_name not in existing_cols:
            cur.execute(
                f"ALTER TABLE post_files ADD COLUMN {column_name} {column_type}"
            )

    cur.execute(
        "UPDATE post_files SET created_at = COALESCE(created_at, uploaded_at, datetime('now'))"
    )


def ensure_attendance_migration(cur):
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS event_attendance (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            event_id INTEGER NOT NULL,
            user_id INTEGER NOT NULL,
            status TEXT NOT NULL DEFAULT 'registered',
            attended_at TEXT,
            duration_minutes INTEGER NOT NULL DEFAULT 0,
            UNIQUE(event_id, user_id)
        )
        """
    )
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS volunteer_activity (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            event_id INTEGER NOT NULL,
            minutes INTEGER NOT NULL DEFAULT 0,
            created_at TEXT NOT NULL
        )
        """
    )
    cur.execute(
        "CREATE INDEX IF NOT EXISTS idx_event_attendance_event_user ON event_attendance(event_id, user_id)"
    )
    cur.execute(
        "CREATE INDEX IF NOT EXISTS idx_volunteer_activity_user ON volunteer_activity(user_id)"
    )


def init_db(default_admin_password):
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("PRAGMA journal_mode=WAL")
    cur.execute("PRAGMA synchronous=NORMAL")
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            username TEXT NOT NULL UNIQUE,
            email TEXT NOT NULL UNIQUE,
            phone TEXT NOT NULL,
            birth_date TEXT NOT NULL,
            password_hash TEXT NOT NULL,
            join_date TEXT NOT NULL
        )
        """
    )
    ensure_users_migration(cur)
    ensure_table_indexes(cur)

    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS activities (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            description TEXT DEFAULT '',
            start_at TEXT NOT NULL,
            end_at TEXT NOT NULL,
            place TEXT DEFAULT '',
            supplies TEXT DEFAULT '',
            gather_time TEXT DEFAULT '',
            manager_name TEXT DEFAULT '',
            recruitment_limit INTEGER NOT NULL DEFAULT 0,
            created_by INTEGER,
            created_at TEXT NOT NULL
        )
        """
    )
    ensure_activities_migration(cur)
    ensure_activity_indexes(cur)

    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS activity_applications (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            activity_id INTEGER NOT NULL,
            user_id INTEGER NOT NULL,
            status TEXT NOT NULL DEFAULT 'waiting',
            attendance_status TEXT NOT NULL DEFAULT 'pending',
            attendance_method TEXT DEFAULT '',
            hours REAL NOT NULL DEFAULT 0,
            points INTEGER NOT NULL DEFAULT 0,
            penalty_points INTEGER NOT NULL DEFAULT 0,
            applied_at TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            UNIQUE(activity_id, user_id)
        )
        """
    )

    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS attendance_qr_tokens (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            activity_id INTEGER NOT NULL,
            token TEXT NOT NULL UNIQUE,
            expires_at TEXT NOT NULL,
            created_by INTEGER,
            created_at TEXT NOT NULL
        )
        """
    )

    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS gallery_albums (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            activity_id INTEGER,
            visibility TEXT NOT NULL DEFAULT 'internal',
            portrait_consent INTEGER NOT NULL DEFAULT 0,
            created_by INTEGER,
            created_at TEXT NOT NULL
        )
        """
    )

    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS gallery_photos (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            album_id INTEGER NOT NULL,
            title TEXT DEFAULT '',
            image_url TEXT NOT NULL,
            thumbnail_url TEXT NOT NULL,
            created_at TEXT NOT NULL
        )
        """
    )

    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS rules_versions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            version_tag TEXT NOT NULL,
            effective_date TEXT NOT NULL,
            summary TEXT NOT NULL,
            content TEXT DEFAULT '',
            created_at TEXT NOT NULL
        )
        """
    )

    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS annual_reports (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            report_year INTEGER NOT NULL UNIQUE,
            total_activities INTEGER NOT NULL DEFAULT 0,
            total_hours REAL NOT NULL DEFAULT 0,
            total_participants INTEGER NOT NULL DEFAULT 0,
            impact_metric TEXT DEFAULT '',
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        )
        """
    )

    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS scheduled_notices (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            publish_at TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'pending',
            created_at TEXT NOT NULL
        )
        """
    )

    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS qna_posts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            answer TEXT DEFAULT '',
            created_at TEXT NOT NULL
        )
        """
    )

    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS about_sections (
            section_key TEXT PRIMARY KEY,
            content_html TEXT NOT NULL DEFAULT '',
            image_url TEXT NOT NULL DEFAULT '',
            updated_at TEXT NOT NULL,
            updated_by INTEGER
        )
        """
    )

    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS site_editor_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            snapshot_json TEXT NOT NULL,
            action TEXT NOT NULL DEFAULT 'save',
            created_at TEXT NOT NULL,
            created_by INTEGER
        )
        """
    )
    cur.execute(
        "CREATE INDEX IF NOT EXISTS idx_site_editor_history_created_at ON site_editor_history(created_at DESC)"
    )
    cur.execute(
        "CREATE INDEX IF NOT EXISTS idx_site_editor_history_created_by ON site_editor_history(created_by)"
    )

    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS expenses (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            due_date TEXT NOT NULL,
            settled INTEGER NOT NULL DEFAULT 0,
            created_at TEXT NOT NULL
        )
        """
    )

    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS events (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            description TEXT DEFAULT '',
            location TEXT DEFAULT '',
            event_date TEXT NOT NULL,
            max_participants INTEGER NOT NULL DEFAULT 0,
            supplies TEXT DEFAULT '',
            notice_post_id INTEGER,
            created_by INTEGER,
            created_at TEXT NOT NULL,
            updated_at TEXT
        )
        """
    )
    ensure_events_migration(cur)

    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS participants (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            event_id INTEGER NOT NULL,
            user_id INTEGER NOT NULL,
            status TEXT NOT NULL DEFAULT 'registered',
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            UNIQUE(event_id, user_id)
        )
        """
    )

    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS event_participants (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            event_id INTEGER NOT NULL,
            user_id INTEGER NOT NULL,
            status TEXT NOT NULL DEFAULT 'registered',
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            UNIQUE(event_id, user_id)
        )
        """
    )
    cur.execute(
        """
        INSERT OR IGNORE INTO event_participants (event_id, user_id, status, created_at, updated_at)
        SELECT event_id, user_id, status, created_at, updated_at
        FROM participants
        """
    )

    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS user_activity (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            activity_type TEXT NOT NULL,
            target_type TEXT DEFAULT '',
            target_id INTEGER,
            metadata_json TEXT DEFAULT '{}',
            created_at TEXT NOT NULL
        )
        """
    )

    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS posts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            category TEXT NOT NULL,
            title TEXT NOT NULL,
            content TEXT DEFAULT '',
            is_pinned INTEGER NOT NULL DEFAULT 0,
            is_important INTEGER NOT NULL DEFAULT 0,
            publish_at TEXT,
            status TEXT NOT NULL DEFAULT 'published',
            image_url TEXT DEFAULT '',
            thumb_url TEXT DEFAULT '',
            volunteer_start_date TEXT,
            volunteer_end_date TEXT,
            author_id INTEGER,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        )
        """
    )
    ensure_posts_migration(cur)

    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS role_requests (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            from_role TEXT NOT NULL,
            to_role TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'PENDING',
            created_at TEXT NOT NULL,
            decided_at TEXT,
            decided_by INTEGER
        )
        """
    )

    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS comments (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            post_id INTEGER NOT NULL,
            user_id INTEGER NOT NULL,
            content TEXT NOT NULL,
            parent_id INTEGER,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        )
        """
    )

    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS recommends (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            post_id INTEGER NOT NULL,
            user_id INTEGER NOT NULL,
            created_at TEXT NOT NULL,
            UNIQUE(post_id, user_id)
        )
        """
    )

    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS event_votes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            event_id INTEGER NOT NULL,
            user_id INTEGER NOT NULL,
            vote_status TEXT NOT NULL,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            UNIQUE(event_id, user_id)
        )
        """
    )

    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS post_files (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            post_id INTEGER NOT NULL,
            original_name TEXT NOT NULL,
            stored_path TEXT NOT NULL,
            mime_type TEXT NOT NULL,
            size INTEGER NOT NULL,
            uploaded_at TEXT NOT NULL,
            hash_sha256 TEXT DEFAULT '',
            created_at TEXT,
            expires_at TEXT
        )
        """
    )
    ensure_post_files_migration(cur)
    ensure_attendance_migration(cur)

    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS audit_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            actor_user_id INTEGER,
            action TEXT NOT NULL,
            target_type TEXT DEFAULT '',
            target_id INTEGER,
            metadata_json TEXT DEFAULT '{}',
            created_at TEXT NOT NULL
        )
        """
    )
    audit_cols = {
        row["name"] for row in cur.execute("PRAGMA table_info(audit_logs)").fetchall()
    }
    if "actor_user_id" not in audit_cols:
        cur.execute("ALTER TABLE audit_logs ADD COLUMN actor_user_id INTEGER")
    if "action" not in audit_cols:
        cur.execute("ALTER TABLE audit_logs ADD COLUMN action TEXT")
    if "target_type" not in audit_cols:
        cur.execute("ALTER TABLE audit_logs ADD COLUMN target_type TEXT DEFAULT ''")
    if "target_id" not in audit_cols:
        cur.execute("ALTER TABLE audit_logs ADD COLUMN target_id INTEGER")
    if "metadata_json" not in audit_cols:
        cur.execute(
            "ALTER TABLE audit_logs ADD COLUMN metadata_json TEXT DEFAULT '{}' "
        )
    if "created_at" not in audit_cols:
        cur.execute("ALTER TABLE audit_logs ADD COLUMN created_at TEXT")

    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS notification_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            notification_type TEXT NOT NULL,
            target_type TEXT NOT NULL,
            target_id TEXT NOT NULL,
            recipient TEXT NOT NULL,
            sent_at TEXT NOT NULL,
            UNIQUE(notification_type, target_type, target_id, recipient)
        )
        """
    )

    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS site_editor_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            snapshot_json TEXT NOT NULL,
            action TEXT NOT NULL DEFAULT 'save',
            created_at TEXT NOT NULL,
            created_by INTEGER
        )
        """
    )

    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS email_notifications (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            event_id INTEGER,
            type TEXT NOT NULL,
            sent_at TEXT NOT NULL,
            UNIQUE(user_id, event_id, type)
        )
        """
    )

    cur.execute("CREATE INDEX IF NOT EXISTS idx_events_date ON events(event_date)")
    cur.execute(
        "CREATE INDEX IF NOT EXISTS idx_participants_event ON participants(event_id)"
    )
    cur.execute(
        "CREATE INDEX IF NOT EXISTS idx_event_participants_event ON event_participants(event_id)"
    )
    cur.execute(
        "CREATE INDEX IF NOT EXISTS idx_event_participants_user ON event_participants(user_id)"
    )
    cur.execute("CREATE INDEX IF NOT EXISTS idx_posts_category ON posts(category)")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_posts_publish_at ON posts(publish_at)")
    cur.execute(
        "CREATE INDEX IF NOT EXISTS idx_posts_status_publish ON posts(status, publish_at)"
    )
    cur.execute("CREATE INDEX IF NOT EXISTS idx_posts_important ON posts(is_important)")
    cur.execute(
        "CREATE INDEX IF NOT EXISTS idx_post_files_hash ON post_files(hash_sha256)"
    )
    cur.execute(
        "CREATE INDEX IF NOT EXISTS idx_role_requests_status ON role_requests(status)"
    )
    cur.execute("CREATE INDEX IF NOT EXISTS idx_comments_post ON comments(post_id)")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_recommends_post ON recommends(post_id)")
    cur.execute(
        "CREATE INDEX IF NOT EXISTS idx_event_votes_event ON event_votes(event_id)"
    )
    cur.execute(
        "CREATE UNIQUE INDEX IF NOT EXISTS idx_users_nickname_unique ON users(nickname)"
    )
    cur.execute(
        "CREATE INDEX IF NOT EXISTS idx_audit_created ON audit_logs(created_at)"
    )
    cur.execute(
        "CREATE INDEX IF NOT EXISTS idx_user_activity_user_created ON user_activity(user_id, created_at DESC)"
    )
    conn.commit()

    seed_initial_data(cur, default_admin_password)

    conn.commit()
    conn.close()


def seed_initial_data(cur, default_admin_password):
    admin_email = "admin@weave.com"
    admin_defaults = {
        "name": "관리자",
        "username": "admin",
        "email": admin_email,
        "phone": "010-0000-0000",
        "birth_date": "1990.01.01",
        "role": "ADMIN",
        "status": "active",
        "generation": "운영",
        "interests": "운영 총괄",
        "certificates": "CPR",
        "availability": "상시",
    }
    admin_now = now_iso()
    admin_row = cur.execute(
        "SELECT * FROM users WHERE username = ?", (admin_defaults["username"],)
    ).fetchone()
    if not admin_row:
        admin_row = cur.execute(
            "SELECT * FROM users WHERE email = ?", (admin_defaults["email"],)
        ).fetchone()

    if admin_row:
        needs_password_reset = not check_password_hash(
            admin_row["password_hash"], default_admin_password
        )
        password_hash_value = (
            generate_password_hash(default_admin_password)
            if needs_password_reset
            else admin_row["password_hash"]
        )
        cur.execute(
            """
            UPDATE users
            SET name = ?,
                username = ?,
                email = ?,
                phone = ?,
                birth_date = ?,
                password_hash = ?,
                role = ?,
                is_admin = 1,
                status = ?,
                approved_at = COALESCE(approved_at, ?),
                generation = CASE WHEN generation IS NULL OR generation = '' THEN ? ELSE generation END,
                interests = CASE WHEN interests IS NULL OR interests = '' THEN ? ELSE interests END,
                certificates = CASE WHEN certificates IS NULL OR certificates = '' THEN ? ELSE certificates END,
                availability = CASE WHEN availability IS NULL OR availability = '' THEN ? ELSE availability END
            WHERE id = ?
            """,
            (
                admin_defaults["name"],
                admin_defaults["username"],
                admin_defaults["email"],
                admin_defaults["phone"],
                admin_defaults["birth_date"],
                password_hash_value,
                admin_defaults["role"],
                admin_defaults["status"],
                admin_now,
                admin_defaults["generation"],
                admin_defaults["interests"],
                admin_defaults["certificates"],
                admin_defaults["availability"],
                admin_row["id"],
            ),
        )
    else:
        cur.execute(
            """
            INSERT INTO users (
                name, username, email, phone, birth_date, password_hash, join_date,
                role, is_admin, status, approved_at, generation, interests, certificates, availability, nickname, nickname_updated_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                admin_defaults["name"],
                admin_defaults["username"],
                admin_defaults["email"],
                admin_defaults["phone"],
                admin_defaults["birth_date"],
                generate_password_hash(default_admin_password),
                admin_now,
                admin_defaults["role"],
                1,
                admin_defaults["status"],
                admin_now,
                admin_defaults["generation"],
                admin_defaults["interests"],
                admin_defaults["certificates"],
                admin_defaults["availability"],
                admin_defaults["username"],
                admin_now,
            ),
        )

    seed_rules = cur.execute("SELECT id FROM rules_versions LIMIT 1").fetchone()
    if not seed_rules:
        cur.execute(
            """
            INSERT INTO rules_versions (version_tag, effective_date, summary, content, created_at)
            VALUES (?, ?, ?, ?, ?)
            """,
            (
                "v1.0",
                datetime.now().date().isoformat(),
                "초기 운영 규칙 등록",
                "규칙/규약 초기 버전",
                now_iso(),
            ),
        )

    seed_year = datetime.now().year
    sample_activities = [
        {
            "title": "유기견 봉사",
            "description": "유기견 보호소 환경정리 및 산책 봉사",
            "start_at": f"{seed_year}-03-14T09:30:00",
            "end_at": f"{seed_year}-03-14T12:00:00",
            "place": "남양주 유기동물 보호소",
            "supplies": "편한 복장, 장갑",
            "gather_time": "09:20",
            "manager_name": "운영진",
            "recruitment_limit": 30,
        },
        {
            "title": "백봉산 플로깅 및 산불조심 캠페인 봉사",
            "description": "백봉산 일대 플로깅 및 산불예방 캠페인 진행",
            "start_at": f"{seed_year}-03-28T09:00:00",
            "end_at": f"{seed_year}-03-28T12:30:00",
            "place": "백봉산 입구",
            "supplies": "집게, 봉투, 물",
            "gather_time": "08:50",
            "manager_name": "운영진",
            "recruitment_limit": 40,
        },
    ]
    for item in sample_activities:
        already_exists = cur.execute(
            "SELECT id FROM activities WHERE title = ? AND start_at = ? LIMIT 1",
            (item["title"], item["start_at"]),
        ).fetchone()
        if already_exists:
            continue
        cur.execute(
            """
            INSERT INTO activities (
                title, description, start_at, end_at, place, supplies, gather_time,
                manager_name, recruitment_limit, created_by, created_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, NULL, ?)
            """,
            (
                item["title"],
                item["description"],
                item["start_at"],
                item["end_at"],
                item["place"],
                item["supplies"],
                item["gather_time"],
                item["manager_name"],
                item["recruitment_limit"],
                now_iso(),
            ),
        )

    cur.execute(
        """
        UPDATE activities
        SET start_at = ?, end_at = ?
        WHERE title = ?
          AND start_at = ?
          AND end_at = ?
        """,
        (
            f"{seed_year}-03-28T09:00:00",
            f"{seed_year}-03-28T12:30:00",
            "백봉산 플로깅 및 산불조심 캠페인 봉사",
            f"{seed_year}-03-21T09:00:00",
            f"{seed_year}-03-21T12:30:00",
        ),
    )

    cur.execute(
        """
        DELETE FROM activities
        WHERE title = ?
          AND start_at = ?
          AND id NOT IN (
              SELECT MIN(id)
              FROM activities
              WHERE title = ? AND start_at = ?
          )
        """,
        (
            "백봉산 플로깅 및 산불조심 캠페인 봉사",
            f"{seed_year}-03-28T09:00:00",
            "백봉산 플로깅 및 산불조심 캠페인 봉사",
            f"{seed_year}-03-28T09:00:00",
        ),
    )

