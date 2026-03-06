import os
import sqlite3
import uuid
import hashlib
import csv
import io
import json
import logging
import smtplib
import time
import shutil
import threading
from datetime import datetime, timedelta, timezone
from email.message import EmailMessage
from pathlib import Path

from flask import (
    Flask,
    Response,
    g,
    jsonify,
    request,
    send_from_directory,
    send_file,
    session,
)
from werkzeug.middleware.proxy_fix import ProxyFix
from werkzeug.security import check_password_hash, generate_password_hash
from werkzeug.utils import secure_filename


BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
INSTANCE_DIR = os.path.join(BASE_DIR, "instance")
os.makedirs(INSTANCE_DIR, exist_ok=True)
DB_PATH = os.environ.get("WEAVE_DB_PATH", os.path.join(BASE_DIR, "weave.db"))
STATIC_DIR = os.path.join(BASE_DIR, "static")
UPLOAD_DIR = os.path.join(BASE_DIR, "uploads")
LOG_DIR = os.path.join(BASE_DIR, "logs")
os.makedirs(UPLOAD_DIR, exist_ok=True)
os.makedirs(LOG_DIR, exist_ok=True)
WEAVE_ENV = os.environ.get("WEAVE_ENV", "development").lower()
DEFAULT_ADMIN_PASSWORD = "Weave!2026"
ROLE_ORDER = {
    "GENERAL": 1,
    "MEMBER": 2,
    "EXECUTIVE": 3,
    "VICE_LEADER": 4,
    "LEADER": 5,
    "ADMIN": 6,
}
LEGACY_ROLE_MAP = {
    "member": "MEMBER",
    "staff": "EXECUTIVE",
    "admin": "ADMIN",
    "general": "GENERAL",
    "executive": "EXECUTIVE",
    "leader": "LEADER",
    "vice_leader": "VICE_LEADER",
    "operator": "ADMIN",
    "ADMIN": "ADMIN",
    "MEMBER": "MEMBER",
    "EXECUTIVE": "EXECUTIVE",
    "LEADER": "LEADER",
    "VICE_LEADER": "VICE_LEADER",
    "GENERAL": "GENERAL",
}
KST = timezone(timedelta(hours=9))
DATABASE_URL = os.environ.get("DATABASE_URL", f"sqlite:///{DB_PATH}")

LOGIN_RATE_LIMIT_COUNT = 10
LOGIN_RATE_LIMIT_WINDOW = timedelta(minutes=5)
LOGIN_RATE_LIMIT_BLOCK = timedelta(minutes=5)
LOGIN_ATTEMPTS = {}

SMTP_HOST = os.environ.get("SMTP_HOST", "")
SMTP_PORT = int(os.environ.get("SMTP_PORT", "587"))
SMTP_USER = os.environ.get("SMTP_USER", "")
SMTP_PASSWORD = os.environ.get("SMTP_PASSWORD", "")
SMTP_FROM = os.environ.get("SMTP_FROM", SMTP_USER or "no-reply@weave.local")
SMTP_TLS = os.environ.get("SMTP_TLS", "true").lower() == "true"

MAX_UPLOAD_MB = int(os.environ.get("MAX_UPLOAD_MB", "5"))
MAX_UPLOAD_BYTES = MAX_UPLOAD_MB * 1024 * 1024
ALLOWED_UPLOAD_EXT = {".jpg", ".jpeg", ".png", ".webp", ".gif", ".pdf"}
ALLOWED_UPLOAD_MIME = {
    "image/jpeg",
    "image/png",
    "image/webp",
    "image/gif",
    "application/pdf",
}

logger = logging.getLogger("weave")
logger.setLevel(logging.INFO)
if not logger.handlers:
    file_handler = logging.FileHandler(
        os.path.join(LOG_DIR, "app.log"), encoding="utf-8"
    )
    formatter = logging.Formatter("%(asctime)s | %(levelname)s | %(message)s")
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)

APP_STARTED_AT = time.time()
APP_METRICS = {"total_requests": 0, "error_count": 0}
CACHE_TTL_SECONDS = 60
APP_CACHE = {}
APP_CACHE_LOCK = threading.Lock()

from weave.authz import (
    active_member_required,
    admin_required,
    get_current_user_row,
    login_required,
    normalize_role,
    role_at_least,
    role_required,
    role_to_icon,
    role_to_label,
    roles_allowed,
    roles_required,
)
from weave.files import (
    compute_file_sha256_from_filestorage,
    delete_file_if_unreferenced,
    make_thumbnail_like,
    remove_file_safely,
    save_uploaded_file,
    upload_url_to_path,
)
from weave.responses import (
    author_payload_from_user,
    error_response,
    is_api_request,
    success_response,
    success_response_legacy,
    user_row_to_dict,
)
from weave.time_utils import activity_start_date_local, now_iso, parse_iso_datetime
from weave.validators import (
    normalize_contact,
    to_list_text,
    validate_nickname,
    validate_password_policy,
    validate_signup_payload,
)


def get_client_ip():
    forwarded = request.headers.get("X-Forwarded-For", "")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.remote_addr or "unknown"


def get_user_agent():
    return request.headers.get("User-Agent", "")[:500]


def parse_rate_limit_bucket(ip):
    now = datetime.now()
    bucket = LOGIN_ATTEMPTS.get(ip, {"fails": [], "blocked_until": None})
    bucket["fails"] = [
        ts for ts in bucket.get("fails", []) if (now - ts) <= LOGIN_RATE_LIMIT_WINDOW
    ]
    blocked_until = bucket.get("blocked_until")
    if blocked_until and blocked_until <= now:
        bucket["blocked_until"] = None
    LOGIN_ATTEMPTS[ip] = bucket
    return bucket


def get_rate_limit_key(action, username_hint=""):
    return f"{action}:{get_client_ip()}:{str(username_hint or '').strip().lower()}"


def is_rate_limited(action, username_hint=""):
    if WEAVE_ENV != "production":
        return False, None
    key = get_rate_limit_key(action, username_hint)
    blocked, blocked_until = is_ip_blocked(key)
    return blocked, blocked_until


def mark_rate_limit_failure(action, username_hint=""):
    if WEAVE_ENV != "production":
        return None
    key = get_rate_limit_key(action, username_hint)
    return register_login_failure(key)


def clear_rate_limit(action, username_hint=""):
    if WEAVE_ENV != "production":
        return
    key = get_rate_limit_key(action, username_hint)
    reset_login_failures_by_ip(key)


def is_ip_blocked(ip):
    bucket = parse_rate_limit_bucket(ip)
    blocked_until = bucket.get("blocked_until")
    if blocked_until and blocked_until > datetime.now():
        return True, blocked_until
    return False, None


def register_login_failure(ip):
    bucket = parse_rate_limit_bucket(ip)
    now = datetime.now()
    bucket["fails"].append(now)
    if len(bucket["fails"]) >= LOGIN_RATE_LIMIT_COUNT:
        bucket["blocked_until"] = now + LOGIN_RATE_LIMIT_BLOCK
        bucket["fails"] = []
    LOGIN_ATTEMPTS[ip] = bucket
    return bucket.get("blocked_until")


def reset_login_failures_by_ip(ip):
    if ip in LOGIN_ATTEMPTS:
        LOGIN_ATTEMPTS.pop(ip, None)


def write_app_log(level, action, user_id=None, extra=None):
    from weave import core_audit

    return core_audit.write_app_log(level, action, user_id=user_id, extra=extra)


def send_email(to_email, subject, body):
    from weave import core_mail

    return core_mail.send_email(to_email, subject, body)


def current_user_id():
    return session.get("user_id")


def get_db_connection():
    from weave import core_db

    return core_db.get_db_connection()


def db_write_retry(func):
    from weave import core_db

    return core_db.db_write_retry(func)


def _cache_now():
    return time.time()


def get_cache(key):
    with APP_CACHE_LOCK:
        cached = APP_CACHE.get(key)
        if not cached:
            return None
        if cached["expires_at"] <= _cache_now():
            APP_CACHE.pop(key, None)
            return None
        return cached["value"]


def set_cache(key, value, ttl_seconds=CACHE_TTL_SECONDS):
    with APP_CACHE_LOCK:
        APP_CACHE[key] = {"value": value, "expires_at": _cache_now() + int(ttl_seconds)}


def invalidate_cache(prefix):
    with APP_CACHE_LOCK:
        keys = [key for key in APP_CACHE.keys() if str(key).startswith(str(prefix))]
        for key in keys:
            APP_CACHE.pop(key, None)


def log_audit(*args, **kwargs):
    from weave import core_audit

    return core_audit.log_audit(*args, **kwargs)


def notification_already_sent(conn, notification_type, target_type, target_id):
    row = conn.execute(
        """
        SELECT id FROM notification_history
        WHERE notification_type = ? AND target_type = ? AND target_id = ?
        LIMIT 1
        """,
        (notification_type, target_type, str(target_id)),
    ).fetchone()
    return bool(row)


def mark_notification_sent(conn, notification_type, target_type, target_id, recipient):
    conn.execute(
        """
        INSERT INTO notification_history (notification_type, target_type, target_id, recipient, sent_at)
        VALUES (?, ?, ?, ?, ?)
        """,
        (notification_type, target_type, str(target_id), recipient, now_iso()),
    )


def ensure_users_migration(cur):
    existing_cols = {
        row["name"] for row in cur.execute("PRAGMA table_info(users)").fetchall()
    }
    migrations = [
        ("role", "TEXT NOT NULL DEFAULT 'GENERAL'"),
        ("is_admin", "INTEGER NOT NULL DEFAULT 0"),
        ("status", "TEXT NOT NULL DEFAULT 'active'"),
        ("generation", "TEXT DEFAULT ''"),
        ("interests", "TEXT DEFAULT ''"),
        ("certificates", "TEXT DEFAULT ''"),
        ("availability", "TEXT DEFAULT ''"),
        ("failed_login_count", "INTEGER NOT NULL DEFAULT 0"),
        ("locked_until", "TEXT"),
        ("approved_at", "TEXT"),
        ("approved_by", "INTEGER"),
        ("retention_until", "TEXT"),
        ("deleted_at", "TEXT"),
        ("nickname", "TEXT"),
        ("nickname_updated_at", "TEXT"),
        ("last_active_at", "TEXT"),
    ]
    for column_name, column_type in migrations:
        if column_name not in existing_cols:
            cur.execute(f"ALTER TABLE users ADD COLUMN {column_name} {column_type}")

    cur.execute("UPDATE users SET role = 'MEMBER' WHERE role = 'member'")
    cur.execute("UPDATE users SET role = 'EXECUTIVE' WHERE role = 'staff'")
    cur.execute(
        "UPDATE users SET role = 'ADMIN' WHERE role IN ('admin', 'operator', 'OPERATOR')"
    )
    cur.execute(
        "UPDATE users SET role = 'GENERAL' WHERE role IS NULL OR TRIM(role) = ''"
    )
    cur.execute(
        "UPDATE users SET status = 'active' WHERE status IS NULL OR TRIM(status) = ''"
    )
    cur.execute(
        "UPDATE users SET status = 'deleted' WHERE status IN ('withdrawn', 'WITHDRAWN')"
    )
    cur.execute(
        "UPDATE users SET status = 'suspended' WHERE status IN ('locked', 'LOCKED')"
    )
    cur.execute("UPDATE users SET is_admin = 1 WHERE role = 'ADMIN'")
    cur.execute(
        "UPDATE users SET nickname = username WHERE nickname IS NULL OR TRIM(nickname) = ''"
    )
    cur.execute(
        "UPDATE users SET nickname_updated_at = COALESCE(nickname_updated_at, join_date, datetime('now'))"
    )
    cur.execute(
        "UPDATE users SET last_active_at = COALESCE(last_active_at, join_date, datetime('now'))"
    )


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


def ensure_table_indexes(cur):
    cur.execute("CREATE INDEX IF NOT EXISTS idx_users_status ON users(status)")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_users_role ON users(role)")


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


def init_db():
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
            admin_row["password_hash"], DEFAULT_ADMIN_PASSWORD
        )
        password_hash_value = (
            generate_password_hash(DEFAULT_ADMIN_PASSWORD)
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
                generate_password_hash(DEFAULT_ADMIN_PASSWORD),
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

    conn.commit()

    conn.close()


def try_unlock_expired_user(conn, row):
    if not row:
        return
    if row["status"] != "suspended":
        return
    locked_until = parse_iso_datetime(row["locked_until"])
    if locked_until and locked_until <= datetime.now():
        next_status = "active" if row["approved_at"] else "pending"
        conn.execute(
            "UPDATE users SET status = ?, locked_until = NULL, failed_login_count = 0 WHERE id = ?",
            (next_status, row["id"]),
        )
        conn.commit()


def increase_login_failure(conn, row):
    attempts = int(row["failed_login_count"] or 0) + 1
    lock_limit = int(os.environ.get("WEAVE_LOGIN_FAIL_LIMIT", "5"))
    lock_minutes = int(os.environ.get("WEAVE_LOGIN_LOCK_MINUTES", "15"))

    if attempts >= lock_limit:
        lock_until = (datetime.now() + timedelta(minutes=lock_minutes)).isoformat()
        conn.execute(
            "UPDATE users SET failed_login_count = ?, status = 'suspended', locked_until = ? WHERE id = ?",
            (attempts, lock_until, row["id"]),
        )
        conn.commit()
        return True, lock_until

    conn.execute(
        "UPDATE users SET failed_login_count = ? WHERE id = ?",
        (attempts, row["id"]),
    )
    conn.commit()
    return False, None


def reset_login_failures(conn, row_id):
    conn.execute(
        "UPDATE users SET failed_login_count = 0, locked_until = NULL WHERE id = ?",
        (row_id,),
    )
    conn.commit()


def touch_user_activity(user_id):
    if not user_id:
        return
    try:
        conn = get_db_connection()
        conn.execute(
            "UPDATE users SET last_active_at = ? WHERE id = ?", (now_iso(), user_id)
        )
        conn.commit()
        conn.close()
    except Exception:
        pass


def record_user_activity(
    conn, user_id, activity_type, target_type="", target_id=None, metadata=None
):
    if not user_id:
        return
    conn.execute(
        """
        INSERT INTO user_activity (user_id, activity_type, target_type, target_id, metadata_json, created_at)
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        (
            int(user_id),
            str(activity_type or "").strip(),
            str(target_type or "").strip(),
            int(target_id) if target_id else None,
            json.dumps(metadata or {}, ensure_ascii=False),
            now_iso(),
        ),
    )


def mark_dormant_users(reference_time=None):
    ref = reference_time or datetime.now()
    threshold = (ref - timedelta(days=365)).isoformat()
    conn = get_db_connection()
    rows = conn.execute(
        "SELECT id FROM users WHERE status = 'active' AND COALESCE(last_active_at, join_date) < ?",
        (threshold,),
    ).fetchall()
    if rows:
        ids = [row["id"] for row in rows]
        placeholders = ",".join(["?"] * len(ids))
        conn.execute(
            f"UPDATE users SET status = 'dormant' WHERE id IN ({placeholders})", ids
        )
        conn.commit()
    conn.close()
    return len(rows)


def serialize_activity_row(row):
    return {
        "id": row["id"],
        "title": row["title"],
        "description": row["description"],
        "startAt": row["start_at"],
        "endAt": row["end_at"],
        "place": row["place"],
        "supplies": row["supplies"],
        "gatherTime": row["gather_time"],
        "manager": row["manager_name"],
        "recruitmentLimit": row["recruitment_limit"],
        "recurrenceGroupId": row["recurrence_group_id"],
        "isCancelled": bool(row["is_cancelled"]),
    }


def calculate_activity_hours(activity):
    start_dt = parse_iso_datetime(activity["start_at"])
    end_dt = parse_iso_datetime(activity["end_at"])
    if start_dt and end_dt and end_dt > start_dt:
        return max(round((end_dt - start_dt).total_seconds() / 3600, 2), 0.5)
    return 2.0


def build_annual_report(conn, year):
    start = f"{year}-01-01"
    end = f"{year}-12-31"
    total_activities = conn.execute(
        "SELECT COUNT(*) AS c FROM activities WHERE date(start_at) BETWEEN ? AND ?",
        (start, end),
    ).fetchone()["c"]
    total_hours = conn.execute(
        """
        SELECT COALESCE(SUM(ap.hours), 0) AS h
        FROM activity_applications ap
        JOIN activities a ON a.id = ap.activity_id
        WHERE ap.attendance_status = 'present' AND date(a.start_at) BETWEEN ? AND ?
        """,
        (start, end),
    ).fetchone()["h"]
    total_participants = conn.execute(
        """
        SELECT COUNT(DISTINCT ap.user_id) AS c
        FROM activity_applications ap
        JOIN activities a ON a.id = ap.activity_id
        WHERE ap.status IN ('confirmed', 'waiting', 'cancelled', 'noshow')
          AND date(a.start_at) BETWEEN ? AND ?
        """,
        (start, end),
    ).fetchone()["c"]

    impact_metric = (
        f"활동 {total_activities}건, 누적 {round(float(total_hours or 0), 1)}시간"
    )
    return {
        "year": year,
        "totalActivities": int(total_activities or 0),
        "totalHours": round(float(total_hours or 0), 2),
        "totalParticipants": int(total_participants or 0),
        "impact": impact_metric,
    }


def csv_response(filename, headers, rows):
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(headers)
    for row in rows:
        writer.writerow(row)
    response = Response(output.getvalue(), mimetype="text/csv; charset=utf-8")
    response.headers["Content-Disposition"] = f"attachment; filename={filename}"
    return response


def send_event_change_notifications(conn, event_id, title):
    users = conn.execute(
        """
        SELECT u.email, u.id
        FROM participants p
        JOIN users u ON u.id = p.user_id
        WHERE p.event_id = ? AND p.status = 'registered'
        """,
        (event_id,),
    ).fetchall()
    sent = 0
    for user in users:
        key_target = f"{event_id}:{user['id']}"
        if notification_already_sent(conn, "event_changed", "event_user", key_target):
            continue
        if send_email(
            user["email"], "[Weave] 일정 변경 안내", f"일정이 변경되었습니다: {title}"
        ):
            mark_notification_sent(
                conn, "event_changed", "event_user", key_target, user["email"]
            )
            sent += 1
    return sent


def send_due_event_reminders(reference_time=None):
    return send_event_reminders(reference_time)


def send_event_reminders(reference_time=None):
    now = reference_time or datetime.now()
    start = now.isoformat()
    end = (now + timedelta(hours=24)).isoformat()
    conn = get_db_connection()
    events = conn.execute(
        "SELECT id, title, event_date FROM events WHERE event_date >= ? AND event_date <= ?",
        (start, end),
    ).fetchall()
    sent_count = 0
    for event in events:
        recipients = conn.execute(
            """
            SELECT u.id, u.email
            FROM participants p
            JOIN users u ON u.id = p.user_id
            WHERE p.event_id = ? AND p.status = 'registered'
            """,
            (event["id"],),
        ).fetchall()
        for user in recipients:
            already_sent = conn.execute(
                "SELECT id FROM email_notifications WHERE user_id = ? AND event_id = ? AND type = 'event_reminder_24h'",
                (user["id"], event["id"]),
            ).fetchone()
            if already_sent:
                continue
            if send_email(
                user["email"],
                "[Weave] 활동 리마인더",
                f"내일 예정된 일정 안내: {event['title']} ({event['event_date']})",
            ):
                conn.execute(
                    "INSERT OR IGNORE INTO email_notifications (user_id, event_id, type, sent_at) VALUES (?, ?, 'event_reminder_24h', ?)",
                    (user["id"], event["id"], now_iso()),
                )
                sent_count += 1
            else:
                logger.error(
                    json.dumps(
                        {
                            "action": "send_event_reminder_failed",
                            "user_id": user["id"],
                            "event_id": event["id"],
                        },
                        ensure_ascii=False,
                    )
                )
    conn.commit()
    conn.close()
    return sent_count


def _update_nickname_common(conn, me, nickname, bypass_window=False):
    exists = conn.execute(
        "SELECT id FROM users WHERE nickname = ? AND id != ?",
        (nickname, me["id"]),
    ).fetchone()
    if exists:
        return None, error_response("이미 사용 중인 닉네임입니다.", 409)

    if not bypass_window:
        last_updated = (
            parse_iso_datetime(me["nickname_updated_at"])
            if "nickname_updated_at" in me.keys()
            else None
        )
        if last_updated:
            next_allowed = last_updated + timedelta(days=180)
            if next_allowed > datetime.now():
                return None, error_response(
                    "닉네임은 180일에 1회만 변경할 수 있습니다.",
                    403,
                    {"next_allowed_at": next_allowed.isoformat()},
                )

    try:
        conn.execute(
            "UPDATE users SET nickname = ?, nickname_updated_at = ? WHERE id = ?",
            (nickname, now_iso(), me["id"]),
        )
    except sqlite3.IntegrityError:
        return None, error_response("이미 사용 중인 닉네임입니다.", 409)
    return conn.execute(
        "SELECT * FROM users WHERE id = ?", (me["id"],)
    ).fetchone(), None


def post_visibility_status(publish_at):
    publish_dt = parse_iso_datetime(publish_at)
    now_dt = (
        datetime.now(publish_dt.tzinfo)
        if publish_dt and publish_dt.tzinfo
        else datetime.now()
    )
    if publish_dt and publish_dt > now_dt:
        return "scheduled"
    return "published"


def should_expose_post(publish_at):
    publish_dt = parse_iso_datetime(publish_at)
    now_dt = (
        datetime.now(publish_dt.tzinfo)
        if publish_dt and publish_dt.tzinfo
        else datetime.now()
    )
    return not publish_dt or publish_dt <= now_dt


