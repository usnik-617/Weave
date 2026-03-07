"""Legacy monolithic handlers (reference-only).

This module is retained for historical compatibility and migration reference.
Active runtime routes and hooks are implemented in split modules under `weave/`.
Prefer editing those active modules for behavior changes.
"""

LEGACY_HANDLERS_RUNTIME_DISABLED = True

import os
import re
import sqlite3
import uuid
import csv
import io
import json
import logging
import smtplib
import time
import shutil
import threading
from functools import wraps
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


def success_response(data=None, status_code=200):
    return jsonify({"success": True, "data": data}), status_code


def error_response(message, code=400, details=None):
    body = {"success": False, "error": str(message)}
    if details is not None:
        body["details"] = details
    return jsonify(body), code


def is_api_request():
    return request.path.startswith("/api")


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


def normalize_role(role):
    text = str(role or "GENERAL").strip()
    if text in ROLE_ORDER:
        return text
    mapped = LEGACY_ROLE_MAP.get(text.lower())
    return mapped or "GENERAL"


def role_to_label(role):
    labels = {
        "GENERAL": "일반",
        "MEMBER": "단원",
        "EXECUTIVE": "임원",
        "LEADER": "단장",
        "VICE_LEADER": "부단장",
        "ADMIN": "운영자",
    }
    return labels.get(normalize_role(role), "일반")


def role_to_icon(role):
    icons = {
        "ADMIN": "🛡️",
        "LEADER": "👑",
        "VICE_LEADER": "⭐",
        "MEMBER": "🙋",
        "EXECUTIVE": "🎯",
    }
    return icons.get(normalize_role(role), "")


def author_payload_from_user(user_row):
    if not user_row:
        return None
    role_value = normalize_role(user_row["role"])
    nickname = (
        user_row["nickname"]
        if "nickname" in user_row.keys() and user_row["nickname"]
        else user_row["username"]
    )
    return {
        "id": user_row["id"],
        "nickname": nickname,
        "role": role_value,
        "role_label": role_to_label(role_value),
        "role_icon": role_to_icon(role_value),
    }


def validate_nickname(nickname):
    text = str(nickname or "").strip()
    if not (2 <= len(text) <= 12):
        return False, "닉네임은 2~12자여야 합니다."
    if not re.fullmatch(r"[가-힣A-Za-z0-9]+", text):
        return False, "닉네임은 한글/영문/숫자만 사용할 수 있습니다."
    return True, ""


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
    payload = {
        "action": action,
        "ip": get_client_ip() if request else "unknown",
        "user_id": user_id,
        "user_agent": get_user_agent() if request else "",
    }
    if extra:
        payload.update(extra)
    line = json.dumps(payload, ensure_ascii=False)
    if level == "warning":
        logger.warning(line)
    elif level == "error":
        logger.error(line)
    else:
        logger.info(line)


def send_email(to_email, subject, body):
    if not SMTP_HOST or not to_email:
        return False
    try:
        message = EmailMessage()
        message["From"] = SMTP_FROM
        message["To"] = to_email
        message["Subject"] = subject
        message.set_content(body)

        with smtplib.SMTP(SMTP_HOST, SMTP_PORT, timeout=10) as server:
            if SMTP_TLS:
                server.starttls()
            if SMTP_USER:
                server.login(SMTP_USER, SMTP_PASSWORD)
            server.send_message(message)
        return True
    except Exception as exc:
        logger.error(f"email_send_failed: {exc}")
        return False


def current_user_id():
    return session.get("user_id")


def save_uploaded_file(file_storage):
    if not file_storage:
        return None, "파일이 없습니다."
    if not file_storage.filename:
        return None, "파일명이 없습니다."
    raw_name = str(file_storage.filename)
    if "/" in raw_name or "\\" in raw_name:
        return None, "파일명에 경로 구분자를 사용할 수 없습니다."

    original_name = secure_filename(raw_name)
    if not original_name:
        return None, "유효하지 않은 파일명입니다."
    extension = Path(original_name).suffix.lower()
    if extension not in ALLOWED_UPLOAD_EXT:
        return None, "허용되지 않은 파일 확장자입니다."

    mime_type = (file_storage.mimetype or "").lower()
    if mime_type not in ALLOWED_UPLOAD_MIME:
        return None, "허용되지 않은 파일 형식입니다."

    file_storage.stream.seek(0, os.SEEK_END)
    size = file_storage.stream.tell()
    file_storage.stream.seek(0)
    if size > MAX_UPLOAD_BYTES:
        return None, f"파일 크기는 최대 {MAX_UPLOAD_MB}MB까지 허용됩니다."

    stored_name = f"{uuid.uuid4().hex}{extension}"
    now = datetime.now()
    subdir = os.path.join(UPLOAD_DIR, f"{now.year:04d}", f"{now.month:02d}")
    os.makedirs(subdir, exist_ok=True)
    stored_path = os.path.join(subdir, stored_name)
    file_storage.save(stored_path)
    return {
        "original_name": original_name,
        "stored_name": stored_name,
        "stored_path": stored_path,
        "mime_type": mime_type,
        "size": size,
    }, None


def remove_file_safely(path):
    if not path:
        return
    try:
        target = os.path.abspath(path)
        root = os.path.abspath(UPLOAD_DIR)
        if not target.startswith(root):
            logger.warning(
                json.dumps(
                    {
                        "action": "skip_file_delete",
                        "reason": "outside_upload_root",
                        "path": target,
                    },
                    ensure_ascii=False,
                )
            )
            return
        if os.path.exists(target):
            os.remove(target)
    except Exception as exc:
        logger.error(
            json.dumps(
                {"action": "file_delete_failed", "path": str(path), "error": str(exc)},
                ensure_ascii=False,
            )
        )


def upload_url_to_path(upload_url):
    text = str(upload_url or "").strip()
    if not text.startswith("/uploads/"):
        return None
    rel = text[len("/uploads/") :]
    rel = os.path.normpath(rel).replace("\\", "/")
    if rel.startswith(".."):
        return None
    return os.path.abspath(os.path.join(UPLOAD_DIR, rel))


def get_db_connection():
    conn = sqlite3.connect(DB_PATH, timeout=10)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA busy_timeout = 10000")
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def db_write_retry(func):
    @wraps(func)
    def wrapper(*args, **kwargs):
        last_error = None
        for attempt in range(3):
            try:
                return func(*args, **kwargs)
            except sqlite3.OperationalError as exc:
                if "database is locked" not in str(exc).lower():
                    raise
                last_error = exc
                time.sleep(0.1 * (attempt + 1))
        if last_error:
            raise last_error

    return wrapper


def parse_iso_datetime(value):
    if not value:
        return None
    try:
        normalized = str(value).strip()
        if normalized.endswith("Z"):
            normalized = normalized[:-1] + "+00:00"
        return datetime.fromisoformat(normalized)
    except Exception:
        return None


def activity_start_date_local(value):
    dt = parse_iso_datetime(value)
    if not dt:
        return None
    if dt.tzinfo is not None:
        dt = dt.astimezone(KST)
    return dt.date()


def now_iso():
    return datetime.now().isoformat()


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


def normalize_contact(value):
    return str(value or "").replace("-", "").strip().lower()


def to_list_text(value):
    if isinstance(value, list):
        return ", ".join([str(item).strip() for item in value if str(item).strip()])
    return str(value or "").strip()


def role_at_least(role, minimum):
    current = normalize_role(role)
    required = normalize_role(minimum)
    return ROLE_ORDER.get(current, 0) >= ROLE_ORDER.get(required, 0)


def get_current_user_row(conn=None):
    user_id = session.get("user_id")
    if not user_id:
        return None

    owned = False
    if conn is None:
        conn = get_db_connection()
        owned = True

    row = conn.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()
    if owned:
        conn.close()
    return row


def login_required(func):
    @wraps(func)
    def wrapper(*args, **kwargs):
        user = get_current_user_row()
        if not user:
            return error_response("Unauthorized", 401)
        if user["status"] in ("suspended", "deleted"):
            return error_response("계정 상태로 인해 요청을 처리할 수 없습니다.", 403)
        return func(*args, **kwargs)

    return wrapper


def admin_required(func):
    @wraps(func)
    def wrapper(*args, **kwargs):
        user = get_current_user_row()
        if not user:
            return error_response("Unauthorized", 401)
        if not roles_allowed(user, {"ADMIN", "LEADER", "VICE_LEADER"}):
            return error_response("Forbidden", 403)
        return func(*args, **kwargs)

    return wrapper


def role_required(min_role):
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            user = get_current_user_row()
            if not user:
                return error_response("Unauthorized", 401)
            if not role_at_least(user["role"], min_role):
                return error_response("Forbidden", 403)
            return func(*args, **kwargs)

        return wrapper

    return decorator


def roles_required(allowed_roles):
    allowed = {normalize_role(role) for role in allowed_roles}

    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            user = get_current_user_row()
            if not user:
                return error_response("Unauthorized", 401)
            user_role = normalize_role(user["role"])
            if user_role not in allowed:
                return error_response("권한이 없습니다.", 403)
            return func(*args, **kwargs)

        return wrapper

    return decorator


def roles_allowed(user_row, allowed_roles):
    if not user_row:
        return False
    return normalize_role(user_row["role"]) in {
        normalize_role(role) for role in allowed_roles
    }


def active_member_required(func):
    @wraps(func)
    def wrapper(*args, **kwargs):
        user = get_current_user_row()
        if not user:
            return error_response("Unauthorized", 401)
        if user["status"] != "active":
            return error_response("승인된 정식 단원만 이용할 수 있습니다.", 403)
        return func(*args, **kwargs)

    return wrapper


def user_row_to_dict(row):
    if not row:
        return None
    role_value = normalize_role(row["role"])
    nickname_value = (
        row["nickname"]
        if "nickname" in row.keys() and row["nickname"]
        else row["username"]
    )
    is_admin_value = bool(row["is_admin"]) if "is_admin" in row.keys() else False
    if role_value == "ADMIN":
        is_admin_value = True
    return {
        "id": row["id"],
        "name": row["name"],
        "username": row["username"],
        "nickname": nickname_value,
        "nicknameUpdatedAt": (
            row["nickname_updated_at"] if "nickname_updated_at" in row.keys() else None
        ),
        "email": row["email"],
        "phone": row["phone"],
        "birthDate": row["birth_date"],
        "joinDate": row["join_date"],
        "role": role_value,
        "roleLabel": f"[{role_to_label(role_value)}]",
        "roleIcon": role_to_icon(role_value),
        "status": row["status"],
        "generation": row["generation"],
        "interests": row["interests"],
        "certificates": row["certificates"],
        "availability": row["availability"],
        "isAdmin": is_admin_value,
        "is_admin": is_admin_value,
        "failedLoginCount": row["failed_login_count"],
        "lockedUntil": row["locked_until"],
    }


def log_audit(*args, **kwargs):
    conn = None
    if args and isinstance(args[0], sqlite3.Connection):
        _, action, target_type, target_id, actor_user_id, metadata = (
            list(args) + [None] * 6
        )[0:6]
    else:
        actor_user_id = args[0] if len(args) > 0 else kwargs.get("actor_user_id")
        action = args[1] if len(args) > 1 else kwargs.get("action")
        target_type = args[2] if len(args) > 2 else kwargs.get("target_type")
        target_id = args[3] if len(args) > 3 else kwargs.get("target_id")
        metadata = args[4] if len(args) > 4 else kwargs.get("metadata")

    actor = actor_user_id if actor_user_id is not None else current_user_id()
    sql = (
        "INSERT INTO audit_logs (actor_user_id, action, target_type, target_id, metadata_json, created_at) "
        "VALUES (?, ?, ?, ?, ?, ?)"
    )
    values = (
        actor,
        str(action or "").strip(),
        str(target_type or "").strip(),
        int(target_id) if target_id is not None else None,
        json.dumps(metadata or {}, ensure_ascii=False),
        now_iso(),
    )

    try:
        conn = get_db_connection()
        conn.execute(sql, values)
        conn.commit()
    except Exception as exc:
        logger.error(
            json.dumps(
                {"action": "audit_log_failed", "error": str(exc)}, ensure_ascii=False
            )
        )
    finally:
        if conn:
            conn.close()


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
        ("volunteer_start_date", "TEXT"),
        ("volunteer_end_date", "TEXT"),
    ]
    for column_name, column_type in migrations:
        if column_name not in existing_cols:
            cur.execute(f"ALTER TABLE posts ADD COLUMN {column_name} {column_type}")


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


def init_db():
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("PRAGMA journal_mode=WAL")
    cur.execute("PRAGMA synchronous=NORMAL")
    cur.execute("""
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
        """)
    ensure_users_migration(cur)
    ensure_table_indexes(cur)

    cur.execute("""
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
        """)
    ensure_activities_migration(cur)
    ensure_activity_indexes(cur)

    cur.execute("""
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
        """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS attendance_qr_tokens (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            activity_id INTEGER NOT NULL,
            token TEXT NOT NULL UNIQUE,
            expires_at TEXT NOT NULL,
            created_by INTEGER,
            created_at TEXT NOT NULL
        )
        """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS gallery_albums (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            activity_id INTEGER,
            visibility TEXT NOT NULL DEFAULT 'internal',
            portrait_consent INTEGER NOT NULL DEFAULT 0,
            created_by INTEGER,
            created_at TEXT NOT NULL
        )
        """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS gallery_photos (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            album_id INTEGER NOT NULL,
            title TEXT DEFAULT '',
            image_url TEXT NOT NULL,
            thumbnail_url TEXT NOT NULL,
            created_at TEXT NOT NULL
        )
        """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS rules_versions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            version_tag TEXT NOT NULL,
            effective_date TEXT NOT NULL,
            summary TEXT NOT NULL,
            content TEXT DEFAULT '',
            created_at TEXT NOT NULL
        )
        """)

    cur.execute("""
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
        """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS scheduled_notices (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            publish_at TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'pending',
            created_at TEXT NOT NULL
        )
        """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS qna_posts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            answer TEXT DEFAULT '',
            created_at TEXT NOT NULL
        )
        """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS expenses (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            due_date TEXT NOT NULL,
            settled INTEGER NOT NULL DEFAULT 0,
            created_at TEXT NOT NULL
        )
        """)

    cur.execute("""
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
        """)
    ensure_events_migration(cur)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS participants (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            event_id INTEGER NOT NULL,
            user_id INTEGER NOT NULL,
            status TEXT NOT NULL DEFAULT 'registered',
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            UNIQUE(event_id, user_id)
        )
        """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS event_participants (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            event_id INTEGER NOT NULL,
            user_id INTEGER NOT NULL,
            status TEXT NOT NULL DEFAULT 'registered',
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            UNIQUE(event_id, user_id)
        )
        """)
    cur.execute("""
        INSERT OR IGNORE INTO event_participants (event_id, user_id, status, created_at, updated_at)
        SELECT event_id, user_id, status, created_at, updated_at
        FROM participants
        """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS user_activity (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            activity_type TEXT NOT NULL,
            target_type TEXT DEFAULT '',
            target_id INTEGER,
            metadata_json TEXT DEFAULT '{}',
            created_at TEXT NOT NULL
        )
        """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS posts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            category TEXT NOT NULL,
            title TEXT NOT NULL,
            content TEXT DEFAULT '',
            is_pinned INTEGER NOT NULL DEFAULT 0,
            is_important INTEGER NOT NULL DEFAULT 0,
            publish_at TEXT,
            image_url TEXT DEFAULT '',
            volunteer_start_date TEXT,
            volunteer_end_date TEXT,
            author_id INTEGER,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        )
        """)
    ensure_posts_migration(cur)

    cur.execute("""
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
        """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS comments (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            post_id INTEGER NOT NULL,
            user_id INTEGER NOT NULL,
            content TEXT NOT NULL,
            parent_id INTEGER,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        )
        """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS recommends (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            post_id INTEGER NOT NULL,
            user_id INTEGER NOT NULL,
            created_at TEXT NOT NULL,
            UNIQUE(post_id, user_id)
        )
        """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS event_votes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            event_id INTEGER NOT NULL,
            user_id INTEGER NOT NULL,
            vote_status TEXT NOT NULL,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            UNIQUE(event_id, user_id)
        )
        """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS post_files (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            post_id INTEGER NOT NULL,
            original_name TEXT NOT NULL,
            stored_path TEXT NOT NULL,
            mime_type TEXT NOT NULL,
            size INTEGER NOT NULL,
            uploaded_at TEXT NOT NULL
        )
        """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS audit_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            actor_user_id INTEGER,
            action TEXT NOT NULL,
            target_type TEXT DEFAULT '',
            target_id INTEGER,
            metadata_json TEXT DEFAULT '{}',
            created_at TEXT NOT NULL
        )
        """)
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

    cur.execute("""
        CREATE TABLE IF NOT EXISTS notification_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            notification_type TEXT NOT NULL,
            target_type TEXT NOT NULL,
            target_id TEXT NOT NULL,
            recipient TEXT NOT NULL,
            sent_at TEXT NOT NULL,
            UNIQUE(notification_type, target_type, target_id, recipient)
        )
        """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS email_notifications (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            event_id INTEGER,
            type TEXT NOT NULL,
            sent_at TEXT NOT NULL,
            UNIQUE(user_id, event_id, type)
        )
        """)

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
    cur.execute("CREATE INDEX IF NOT EXISTS idx_posts_important ON posts(is_important)")
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


def validate_password_policy(password):
    if len(password or "") < 8:
        return False, "비밀번호는 8자 이상이어야 합니다."
    if not re.search(r"[A-Z]", password or ""):
        return False, "비밀번호에 대문자 1개 이상이 필요합니다."
    if not re.search(r"[^A-Za-z0-9]", password or ""):
        return False, "비밀번호에 특수문자 1개 이상이 필요합니다."
    return True, ""


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


def validate_signup_payload(payload):
    required_fields = [
        "name",
        "nickname",
        "email",
        "birthDate",
        "phone",
        "username",
        "password",
    ]
    for field in required_fields:
        if not str(payload.get(field, "")).strip():
            return False, f"{field} 값이 필요합니다."

    password_ok, password_message = validate_password_policy(
        str(payload.get("password", ""))
    )
    if not password_ok:
        return False, password_message

    nickname_ok, nickname_message = validate_nickname(payload.get("nickname", ""))
    if not nickname_ok:
        return False, nickname_message

    return True, ""


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


def begin_request_context():
    g.request_started = time.time()
    g.request_id = uuid.uuid4().hex


def set_security_headers(response):
    APP_METRICS["total_requests"] += 1
    if int(response.status_code) >= 400:
        APP_METRICS["error_count"] += 1

    duration_ms = int((time.time() - getattr(g, "request_started", time.time())) * 1000)
    user_id = session.get("user_id")
    response.headers.setdefault("X-Request-ID", getattr(g, "request_id", ""))
    response.headers.setdefault("X-Content-Type-Options", "nosniff")
    response.headers.setdefault("X-Frame-Options", "SAMEORIGIN")
    response.headers.setdefault("Referrer-Policy", "strict-origin-when-cross-origin")
    response.headers.setdefault(
        "Permissions-Policy", "camera=(), microphone=(), geolocation=()"
    )
    response.headers.setdefault("Cache-Control", "no-store")

    logger.info(
        json.dumps(
            {
                "timestamp": now_iso(),
                "request_id": getattr(g, "request_id", ""),
                "user_id": user_id,
                "path": request.path,
                "status_code": int(response.status_code),
                "duration_ms": duration_ms,
            },
            ensure_ascii=False,
        )
    )
    if user_id:
        touch_user_activity(user_id)
    return response


def metrics():
    active_users_last_hour = 0
    total_posts = 0
    total_comments = 0
    try:
        conn = get_db_connection()
        one_hour_ago = (datetime.now() - timedelta(hours=1)).isoformat()
        active_users_last_hour = int(
            conn.execute(
                "SELECT COUNT(*) AS c FROM users WHERE status = 'active' AND last_active_at >= ?",
                (one_hour_ago,),
            ).fetchone()["c"]
            or 0
        )
        total_posts = int(
            conn.execute("SELECT COUNT(*) AS c FROM posts").fetchone()["c"] or 0
        )
        total_comments = int(
            conn.execute("SELECT COUNT(*) AS c FROM comments").fetchone()["c"] or 0
        )
        conn.close()
    except Exception:
        active_users_last_hour = 0
        total_posts = 0
        total_comments = 0
    return jsonify(
        {
            "uptime_seconds": int(time.time() - APP_STARTED_AT),
            "total_requests": int(APP_METRICS["total_requests"]),
            "error_count": int(APP_METRICS["error_count"]),
            "active_users_last_hour": active_users_last_hour,
            "total_posts": total_posts,
            "total_comments": total_comments,
        }
    )


def root():
    return send_from_directory(STATIC_DIR, "index.html")


def healthz():
    try:
        conn = get_db_connection()
        conn.execute("SELECT 1")
        conn.close()
        disk_free_mb = int(shutil.disk_usage(BASE_DIR).free / (1024 * 1024))
        return success_response(
            {
                "status": "healthy",
                "database": "ok",
                "disk_space_mb": disk_free_mb,
                "uptime_seconds": int(time.time() - APP_STARTED_AT),
            },
            200,
        )
    except Exception as exc:
        return error_response("DB connectivity check failed", 500, {"reason": str(exc)})


def auth_me():
    row = get_current_user_row()
    if not row:
        return success_response({"user": None})
    data = {"user": user_row_to_dict(row)}
    return jsonify({"success": True, "data": data, "user": data["user"]})


@db_write_retry
def auth_signup():
    payload = request.get_json(silent=True) or {}
    blocked, blocked_until = is_rate_limited("signup", payload.get("username", ""))
    if blocked:
        blocked_until_text = blocked_until.isoformat() if blocked_until else now_iso()
        return error_response(
            "요청이 너무 많습니다. 잠시 후 다시 시도해주세요.",
            429,
            {"blocked_until": blocked_until_text},
        )

    valid, message = validate_signup_payload(payload)
    if not valid:
        mark_rate_limit_failure("signup", payload.get("username", ""))
        return error_response(message, 400)

    conn = get_db_connection()
    cur = conn.cursor()
    exists_email = cur.execute(
        "SELECT id FROM users WHERE email = ?", (payload["email"],)
    ).fetchone()
    if exists_email:
        conn.close()
        return error_response("이미 등록된 이메일입니다.", 409)

    exists_username = cur.execute(
        "SELECT id FROM users WHERE username = ?", (payload["username"],)
    ).fetchone()
    if exists_username:
        conn.close()
        mark_rate_limit_failure("signup", payload.get("username", ""))
        return error_response("이미 사용 중인 아이디입니다.", 409)

    exists_nickname = cur.execute(
        "SELECT id FROM users WHERE nickname = ?", (payload["nickname"],)
    ).fetchone()
    if exists_nickname:
        conn.close()
        mark_rate_limit_failure("signup", payload.get("username", ""))
        return error_response("이미 사용 중인 닉네임입니다.", 409)

    cur.execute(
        """
        INSERT INTO users (
            name, username, email, phone, birth_date, password_hash, join_date,
            role, status, generation, interests, certificates, availability, nickname, nickname_updated_at
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            payload["name"].strip(),
            payload["username"].strip(),
            payload["email"].strip(),
            payload["phone"].strip(),
            payload["birthDate"].strip(),
            generate_password_hash(payload["password"]),
            now_iso(),
            "GENERAL",
            "active",
            str(payload.get("generation", "")).strip(),
            to_list_text(payload.get("interests", "")),
            to_list_text(payload.get("certificates", "")),
            str(payload.get("availability", "")).strip(),
            str(payload.get("nickname", "")).strip(),
            now_iso(),
        ),
    )
    user_id = cur.lastrowid
    log_audit(conn, "signup", "user", user_id, user_id)
    conn.commit()
    row = cur.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()
    conn.close()

    write_app_log("info", "signup", user_id=user_id)
    clear_rate_limit("signup", payload.get("username", ""))

    session["user_id"] = user_id
    user_data = user_row_to_dict(row)
    payload = {
        "message": "회원가입이 완료되었습니다.",
        "user": user_data,
    }
    return jsonify({"success": True, "data": payload, "ok": True, **payload})


def auth_login():
    payload = request.get_json(silent=True) or {}
    username = str(payload.get("username", "")).strip()
    password = str(payload.get("password", ""))
    client_ip = get_client_ip()

    blocked, blocked_until = is_rate_limited("login", username)
    if blocked:
        blocked_until_text = blocked_until.isoformat() if blocked_until else now_iso()
        write_app_log(
            "warning", "login_rate_limited", extra={"blocked_until": blocked_until_text}
        )
        return error_response(
            f"로그인 시도가 너무 많습니다. {blocked_until_text} 이후 다시 시도하세요.",
            429,
            {"blocked_until": blocked_until_text},
        )

    if not username or not password:
        return error_response("아이디와 비밀번호를 입력해주세요.", 400)

    conn = get_db_connection()
    row = conn.execute("SELECT * FROM users WHERE username = ?", (username,)).fetchone()

    if not row:
        conn.close()
        mark_rate_limit_failure("login", username)
        write_app_log(
            "warning", "login_failed_unknown_user", extra={"username": username}
        )
        return error_response("아이디 또는 비밀번호가 틀렸습니다.", 401)

    try_unlock_expired_user(conn, row)
    row = conn.execute("SELECT * FROM users WHERE id = ?", (row["id"],)).fetchone()

    if row["status"] in ("withdrawn", "deleted"):
        conn.close()
        write_app_log("warning", "login_withdrawn", user_id=row["id"])
        return error_response("탈퇴 처리된 계정입니다.", 403)

    if row["status"] == "suspended":
        conn.close()
        write_app_log("warning", "login_suspended", user_id=row["id"])
        return error_response("정지된 계정입니다. 관리자에게 문의하세요.", 403)

    if not check_password_hash(row["password_hash"], password):
        locked, _ = increase_login_failure(conn, row)
        conn.close()
        mark_rate_limit_failure("login", username)
        write_app_log("warning", "login_failed", user_id=row["id"])
        if locked:
            return error_response("로그인 5회 실패로 계정이 잠금되었습니다.", 423)
        return error_response("아이디 또는 비밀번호가 틀렸습니다.", 401)

    reset_login_failures(conn, row["id"])
    row = conn.execute("SELECT * FROM users WHERE id = ?", (row["id"],)).fetchone()
    log_audit(conn, "login", "user", row["id"], row["id"])
    conn.close()
    clear_rate_limit("login", username)
    write_app_log("info", "login_success", user_id=row["id"])

    session["user_id"] = row["id"]
    touch_user_activity(row["id"])
    if row["status"] == "pending":
        payload = {
            "pending": True,
            "message": "가입 승인 대기 중입니다. 승인 후 정식 단원 기능을 사용할 수 있습니다.",
            "user": user_row_to_dict(row),
        }
        return jsonify({"success": True, "data": payload, "ok": True, **payload})

    payload = {"user": user_row_to_dict(row)}
    return jsonify({"success": True, "data": payload, "ok": True, **payload})


def auth_logout():
    user_id = session.get("user_id")
    conn = get_db_connection()
    if user_id:
        log_audit(conn, "logout", "user", user_id, user_id)
        write_app_log("info", "logout", user_id=user_id)
    conn.commit()
    conn.close()
    session.pop("user_id", None)
    return success_response({"ok": True})


def auth_find_username():
    payload = request.get_json(silent=True) or {}
    contact = str(payload.get("contact", "")).strip()
    if not contact:
        return error_response("연락처 또는 이메일을 입력하세요.", 400)

    normalized = contact.replace("-", "").lower()
    conn = get_db_connection()
    row = conn.execute("SELECT username, email, phone, status FROM users").fetchall()
    conn.close()

    for item in row:
        if item["status"] == "withdrawn":
            continue
        email_key = (item["email"] or "").replace("-", "").lower()
        phone_key = (item["phone"] or "").replace("-", "").lower()
        if normalized in (email_key, phone_key):
            return success_response({"username": item["username"], "ok": True})

    return error_response("일치하는 계정을 찾지 못했습니다.", 404)


def auth_reset_password():
    payload = request.get_json(silent=True) or {}
    username = str(payload.get("username", "")).strip()
    contact = str(payload.get("contact", "")).strip()
    new_password = str(payload.get("newPassword", ""))

    blocked, blocked_until = is_rate_limited("reset-password", username)
    if blocked:
        blocked_until_text = blocked_until.isoformat() if blocked_until else now_iso()
        return error_response(
            "요청이 너무 많습니다. 잠시 후 다시 시도해주세요.",
            429,
            {"blocked_until": blocked_until_text},
        )

    if not username or not contact or not new_password:
        mark_rate_limit_failure("reset-password", username)
        return error_response("필수 값을 입력해주세요.", 400)

    valid_password, password_message = validate_password_policy(new_password)
    if not valid_password:
        mark_rate_limit_failure("reset-password", username)
        return error_response(password_message, 400)

    normalized_contact = contact.replace("-", "").lower()

    conn = get_db_connection()
    row = conn.execute(
        "SELECT * FROM users WHERE username = ?",
        (username,),
    ).fetchone()

    if not row:
        conn.close()
        mark_rate_limit_failure("reset-password", username)
        return error_response("일치하는 계정을 찾지 못했습니다.", 404)

    email_key = (row["email"] or "").replace("-", "").lower()
    phone_key = (row["phone"] or "").replace("-", "").lower()
    if normalized_contact not in (email_key, phone_key):
        conn.close()
        mark_rate_limit_failure("reset-password", username)
        return error_response("일치하는 계정을 찾지 못했습니다.", 404)

    conn.execute(
        "UPDATE users SET password_hash = ?, failed_login_count = 0, locked_until = NULL, status = CASE WHEN status='suspended' THEN COALESCE(CASE WHEN approved_at IS NOT NULL THEN 'active' END, 'pending') ELSE status END WHERE id = ?",
        (generate_password_hash(new_password), row["id"]),
    )
    log_audit(conn, "password_reset", "user", row["id"], row["id"])
    send_email(
        row["email"],
        "[Weave] 비밀번호 재설정 안내",
        "비밀번호가 재설정되었습니다. 본인이 요청하지 않았다면 즉시 운영진에 문의하세요.",
    )
    conn.commit()
    conn.close()
    clear_rate_limit("reset-password", username)
    write_app_log("info", "password_reset", user_id=row["id"])
    payload = {"ok": True, "message": "비밀번호가 재설정되었습니다."}
    return jsonify({"success": True, "data": payload, **payload})


def auth_unlock_account():
    payload = request.get_json(silent=True) or {}
    username = str(payload.get("username", "")).strip()
    contact = normalize_contact(payload.get("contact", ""))

    if not username or not contact:
        return (
            jsonify({"ok": False, "message": "아이디와 휴대폰/이메일이 필요합니다."}),
            400,
        )

    conn = get_db_connection()
    row = conn.execute("SELECT * FROM users WHERE username = ?", (username,)).fetchone()
    if not row:
        conn.close()
        return (
            jsonify({"ok": False, "message": "일치하는 계정을 찾지 못했습니다."}),
            404,
        )

    if contact not in (
        normalize_contact(row["email"]),
        normalize_contact(row["phone"]),
    ):
        conn.close()
        return jsonify({"ok": False, "message": "인증 정보가 일치하지 않습니다."}), 403

    next_status = "active" if row["approved_at"] else "pending"
    conn.execute(
        "UPDATE users SET status = ?, failed_login_count = 0, locked_until = NULL WHERE id = ?",
        (next_status, row["id"]),
    )
    conn.commit()
    conn.close()
    return jsonify({"ok": True, "message": "계정 잠금이 해제되었습니다."})


@login_required
def auth_withdraw():
    payload = request.get_json(silent=True) or {}
    contact = normalize_contact(payload.get("contact", ""))
    password = str(payload.get("password", ""))
    reason = str(payload.get("reason", "")).strip()

    conn = get_db_connection()
    me = get_current_user_row(conn)
    if not me:
        conn.close()
        return error_response("Unauthorized", 401)

    if contact not in (normalize_contact(me["email"]), normalize_contact(me["phone"])):
        conn.close()
        return error_response("연락처/이메일 인증이 필요합니다.", 403)

    if not check_password_hash(me["password_hash"], password):
        conn.close()
        return error_response("비밀번호가 올바르지 않습니다.", 403)

    retention_days = int(os.environ.get("WEAVE_RETENTION_DAYS", "30"))
    retention_until = (datetime.now() + timedelta(days=retention_days)).isoformat()
    deleted_at = now_iso()
    anonymized = f"withdrawn-{me['id']}-{int(datetime.now().timestamp())}"

    conn.execute(
        """
        UPDATE users
        SET status = 'deleted',
            deleted_at = ?,
            retention_until = ?,
            name = '탈퇴회원',
            email = ?,
            phone = '000-0000-0000',
            username = ?,
            interests = ?,
            certificates = ?,
            availability = ?,
            generation = ?
        WHERE id = ?
        """,
        (
            deleted_at,
            retention_until,
            f"{anonymized}@withdrawn.local",
            anonymized,
            f"탈퇴사유:{reason}" if reason else "탈퇴",
            "",
            "",
            "",
            me["id"],
        ),
    )
    log_audit(conn, "delete_user", "user", me["id"], me["id"])
    conn.commit()
    conn.close()
    session.pop("user_id", None)
    write_app_log("info", "user_withdraw", user_id=me["id"])
    return success_response(
        {
            "ok": True,
            "message": f"탈퇴 완료. 데이터는 {retention_days}일 보관 후 파기됩니다.",
        }
    )


@role_required("EXECUTIVE")
def admin_pending_users():
    page = int(request.args.get("page", "1") or 1)
    page_size = int(request.args.get("pageSize", "10") or 10)
    page = max(page, 1)
    page_size = min(max(page_size, 1), 100)
    offset = (page - 1) * page_size

    conn = get_db_connection()
    total = conn.execute(
        "SELECT COUNT(*) AS c FROM users WHERE status = 'pending'"
    ).fetchone()["c"]
    rows = conn.execute(
        "SELECT * FROM users WHERE status = 'pending' ORDER BY id DESC LIMIT ? OFFSET ?",
        (page_size, offset),
    ).fetchall()
    conn.close()
    total_pages = max((int(total or 0) + page_size - 1) // page_size, 1)
    return jsonify(
        {
            "ok": True,
            "items": [user_row_to_dict(row) for row in rows],
            "pagination": {
                "total": int(total or 0),
                "page": page,
                "pageSize": page_size,
                "totalPages": total_pages,
                "hasPrev": page > 1,
                "hasNext": page < total_pages,
            },
        }
    )


@role_required("EXECUTIVE")
@db_write_retry
def admin_approve_user(user_id):
    payload = request.get_json(silent=True) or {}
    role = normalize_role(payload.get("role", "MEMBER"))
    if role not in ("GENERAL", "MEMBER", "EXECUTIVE", "VICE_LEADER", "LEADER", "ADMIN"):
        return error_response("유효하지 않은 역할입니다.", 400)

    conn = get_db_connection()
    target = conn.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()
    if not target:
        conn.close()
        return error_response("대상을 찾을 수 없습니다.", 404)

    me = get_current_user_row(conn)
    if not me:
        conn.close()
        return error_response("Unauthorized", 401)
    if role == "ADMIN" and not role_at_least(me["role"], "ADMIN"):
        conn.close()
        return error_response("관리자 승격 권한이 없습니다.", 403)

    conn.execute(
        "UPDATE users SET status = 'active', role = ?, is_admin = CASE WHEN ? = 'ADMIN' THEN 1 ELSE is_admin END, approved_at = ?, approved_by = ? WHERE id = ?",
        (role, role, now_iso(), me["id"], user_id),
    )
    audit_action = (
        "approve_member"
        if role == "MEMBER"
        else ("approve_executive" if role == "EXECUTIVE" else "role_change")
    )
    log_audit(me["id"], audit_action, "user", user_id, {"role": role})
    if role == "ADMIN":
        log_audit(me["id"], "assign_admin_role", "user", user_id, {"role": role})
    conn.commit()
    row = conn.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()
    if role == "MEMBER":
        send_email(
            row["email"], "[Weave] 단원 승인 안내", "단원 승인이 완료되었습니다."
        )
    elif role == "EXECUTIVE":
        send_email(
            row["email"], "[Weave] 임원 승인 안내", "임원 승인이 완료되었습니다."
        )
    else:
        send_email(
            row["email"],
            "[Weave] 가입 승인 안내",
            f"가입이 승인되었습니다. 현재 권한: {role}",
        )
    conn.close()
    write_app_log(
        "info",
        "admin_approve_user",
        user_id=me["id"],
        extra={"target_user_id": user_id, "role": role},
    )
    payload = {
        "ok": True,
        "message": "가입이 승인되었습니다.",
        "user": user_row_to_dict(row),
    }
    return jsonify({"success": True, "data": payload, **payload})


@role_required("EXECUTIVE")
@db_write_retry
def admin_reject_user(user_id):
    conn = get_db_connection()
    me = get_current_user_row(conn)
    target = conn.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()
    if not target:
        conn.close()
        return error_response("대상을 찾을 수 없습니다.", 404)

    conn.execute(
        "UPDATE users SET status = 'deleted', deleted_at = ? WHERE id = ?",
        (now_iso(), user_id),
    )
    log_audit(me["id"] if me else None, "delete_user", "user", user_id)
    conn.commit()
    conn.close()
    write_app_log(
        "warning",
        "admin_reject_user",
        user_id=me["id"] if me else None,
        extra={"target_user_id": user_id},
    )
    return success_response({"ok": True, "message": "가입 신청이 반려되었습니다."})


@admin_required
@db_write_retry
def admin_suspend_user(user_id):
    conn = get_db_connection()
    me = get_current_user_row(conn)
    if not me:
        conn.close()
        return error_response("Unauthorized", 401)
    target = conn.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()
    if not target:
        conn.close()
        return error_response("대상을 찾을 수 없습니다.", 404)
    conn.execute("UPDATE users SET status = 'suspended' WHERE id = ?", (user_id,))
    conn.commit()
    conn.close()
    log_audit(me["id"], "suspend_user", "user", user_id)
    return success_response({"ok": True, "message": "사용자가 정지되었습니다."})


@admin_required
@db_write_retry
def admin_activate_user(user_id):
    conn = get_db_connection()
    me = get_current_user_row(conn)
    if not me:
        conn.close()
        return error_response("Unauthorized", 401)
    target = conn.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()
    if not target:
        conn.close()
        return error_response("대상을 찾을 수 없습니다.", 404)
    conn.execute("UPDATE users SET status = 'active' WHERE id = ?", (user_id,))
    conn.commit()
    conn.close()
    log_audit(me["id"], "activate_user", "user", user_id)
    return success_response({"ok": True, "message": "사용자가 활성화되었습니다."})


@login_required
@db_write_retry
def delete_my_account():
    conn = get_db_connection()
    me = get_current_user_row(conn)
    if not me:
        conn.close()
        return error_response("Unauthorized", 401)

    deleted_at = now_iso()
    anonymized = f"deleted-{me['id']}-{int(datetime.now().timestamp())}"
    conn.execute(
        """
        UPDATE users
        SET status = 'deleted',
            deleted_at = ?,
            name = '삭제회원',
            email = ?,
            phone = '000-0000-0000',
            username = ?
        WHERE id = ?
        """,
        (deleted_at, f"{anonymized}@deleted.local", anonymized, me["id"]),
    )
    conn.commit()
    conn.close()
    session.pop("user_id", None)
    log_audit(me["id"], "delete_account", "user", me["id"])
    return success_response({"ok": True, "message": "계정이 삭제 처리되었습니다."})


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


def list_activities():
    date_value = str(request.args.get("date", "")).strip()
    view = str(request.args.get("view", "month")).strip().lower()
    if view not in ("month", "week"):
        view = "month"

    if not date_value:
        base_date = datetime.now().date()
    else:
        try:
            base_date = datetime.fromisoformat(date_value).date()
        except Exception:
            base_date = datetime.now().date()

    if view == "week":
        start_date = base_date - timedelta(days=base_date.weekday())
        end_date = start_date + timedelta(days=6)
    else:
        start_date = base_date.replace(day=1)
        next_month = (start_date.replace(day=28) + timedelta(days=4)).replace(day=1)
        end_date = next_month - timedelta(days=1)

    conn = get_db_connection()
    rows = conn.execute(
        """
        SELECT * FROM activities
        WHERE is_cancelled = 0
        ORDER BY start_at ASC
        """,
    ).fetchall()
    conn.close()
    filtered_rows = []
    for row in rows:
        activity_date = activity_start_date_local(row["start_at"])
        if activity_date and start_date <= activity_date <= end_date:
            filtered_rows.append(row)
    return jsonify(
        {
            "ok": True,
            "view": view,
            "range": {"start": start_date.isoformat(), "end": end_date.isoformat()},
            "items": [serialize_activity_row(row) for row in filtered_rows],
        }
    )


@role_required("staff")
def create_activity():
    payload = request.get_json(silent=True) or {}
    required = ["title", "startAt", "endAt"]
    for field in required:
        if not str(payload.get(field, "")).strip():
            return jsonify({"ok": False, "message": f"{field} 값이 필요합니다."}), 400

    title = str(payload.get("title", "")).strip()
    if len(title) > 120:
        return (
            jsonify({"ok": False, "message": "활동 제목은 120자 이하여야 합니다."}),
            400,
        )

    start_at = str(payload.get("startAt", "")).strip()
    end_at = str(payload.get("endAt", "")).strip()
    start_dt = parse_iso_datetime(start_at)
    end_dt = parse_iso_datetime(end_at)
    if not start_dt or not end_dt:
        return (
            jsonify(
                {"ok": False, "message": "시작/종료 시간 형식이 올바르지 않습니다."}
            ),
            400,
        )
    if end_dt <= start_dt:
        return (
            jsonify(
                {"ok": False, "message": "종료 시간은 시작 시간보다 늦어야 합니다."}
            ),
            400,
        )

    recruitment_limit = int(payload.get("recruitmentLimit", 0) or 0)
    if recruitment_limit < 0 or recruitment_limit > 1000:
        return (
            jsonify({"ok": False, "message": "모집 인원은 0~1000 범위여야 합니다."}),
            400,
        )

    recurrence_group_id = str(payload.get("recurrenceGroupId", "")).strip()
    if recurrence_group_id and (
        len(recurrence_group_id) > 64
        or not re.fullmatch(r"[A-Za-z0-9_-]+", recurrence_group_id)
    ):
        return (
            jsonify({"ok": False, "message": "반복 그룹 ID 형식이 올바르지 않습니다."}),
            400,
        )

    conn = get_db_connection()
    me = get_current_user_row(conn)
    if not me:
        conn.close()
        return jsonify({"ok": False, "message": "로그인이 필요합니다."}), 401
    cur = conn.cursor()
    cur.execute(
        """
        INSERT INTO activities (
            title, description, start_at, end_at, place, supplies, gather_time,
            manager_name, recruitment_limit, recurrence_group_id, created_by, created_at
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            title,
            str(payload.get("description", "")).strip(),
            start_at,
            end_at,
            str(payload.get("place", "")).strip(),
            str(payload.get("supplies", "")).strip(),
            str(payload.get("gatherTime", "")).strip(),
            str(payload.get("manager", me["name"])).strip(),
            recruitment_limit,
            recurrence_group_id,
            me["id"],
            now_iso(),
        ),
    )
    activity_id = cur.lastrowid
    conn.commit()
    row = conn.execute(
        "SELECT * FROM activities WHERE id = ?", (activity_id,)
    ).fetchone()
    conn.close()
    return jsonify({"ok": True, "activity": serialize_activity_row(row)})


@active_member_required
def apply_activity(activity_id):
    conn = get_db_connection()
    me = get_current_user_row(conn)
    if not me:
        conn.close()
        return jsonify({"ok": False, "message": "로그인이 필요합니다."}), 401
    activity = conn.execute(
        "SELECT * FROM activities WHERE id = ?", (activity_id,)
    ).fetchone()
    if not activity:
        conn.close()
        return jsonify({"ok": False, "message": "활동을 찾을 수 없습니다."}), 404

    existing = conn.execute(
        "SELECT * FROM activity_applications WHERE activity_id = ? AND user_id = ?",
        (activity_id, me["id"]),
    ).fetchone()

    if existing and existing["status"] not in ("cancelled", "noshow"):
        conn.close()
        return jsonify({"ok": False, "message": "이미 신청한 활동입니다."}), 409

    confirmed_count = conn.execute(
        "SELECT COUNT(*) AS count FROM activity_applications WHERE activity_id = ? AND status = 'confirmed'",
        (activity_id,),
    ).fetchone()["count"]

    limit_count = int(activity["recruitment_limit"] or 0)
    next_status = (
        "confirmed" if limit_count <= 0 or confirmed_count < limit_count else "waiting"
    )

    if existing:
        conn.execute(
            """
            UPDATE activity_applications
            SET status = ?, attendance_status = 'pending', attendance_method = '',
                updated_at = ?, hours = 0, points = 0, penalty_points = 0
            WHERE id = ?
            """,
            (next_status, now_iso(), existing["id"]),
        )
    else:
        conn.execute(
            """
            INSERT INTO activity_applications (
                activity_id, user_id, status, attendance_status, attendance_method,
                hours, points, penalty_points, applied_at, updated_at
            )
            VALUES (?, ?, ?, 'pending', '', 0, 0, 0, ?, ?)
            """,
            (activity_id, me["id"], next_status, now_iso(), now_iso()),
        )
    conn.commit()
    conn.close()
    return jsonify({"ok": True, "status": next_status})


@role_required("staff")
def cancel_recurrence_group(group_id):
    group_id = str(group_id or "").strip()
    if (
        not group_id
        or len(group_id) > 64
        or not re.fullmatch(r"[A-Za-z0-9_-]+", group_id)
    ):
        return (
            jsonify({"ok": False, "message": "유효하지 않은 반복 그룹 ID입니다."}),
            400,
        )

    conn = get_db_connection()
    activities = conn.execute(
        "SELECT id FROM activities WHERE recurrence_group_id = ? AND is_cancelled = 0",
        (group_id,),
    ).fetchall()
    if not activities:
        conn.close()
        return jsonify({"ok": False, "message": "취소할 반복 그룹이 없습니다."}), 404

    activity_ids = [row["id"] for row in activities]
    placeholders = ",".join(["?"] * len(activity_ids))

    conn.execute(
        f"UPDATE activities SET is_cancelled = 1, cancelled_at = ? WHERE id IN ({placeholders})",
        [now_iso(), *activity_ids],
    )
    conn.execute(
        f"""
        UPDATE activity_applications
        SET status = 'cancelled', updated_at = ?
        WHERE activity_id IN ({placeholders})
          AND status IN ('waiting', 'confirmed')
        """,
        [now_iso(), *activity_ids],
    )
    conn.commit()
    conn.close()
    return jsonify(
        {
            "ok": True,
            "message": "반복 그룹 일정이 일괄 취소되었습니다.",
            "count": len(activity_ids),
        }
    )


@role_required("staff")
def recurrence_group_impact(group_id):
    group_id = str(group_id or "").strip()
    if (
        not group_id
        or len(group_id) > 64
        or not re.fullmatch(r"[A-Za-z0-9_-]+", group_id)
    ):
        return (
            jsonify({"ok": False, "message": "유효하지 않은 반복 그룹 ID입니다."}),
            400,
        )

    conn = get_db_connection()
    activity_count = conn.execute(
        "SELECT COUNT(*) AS c FROM activities WHERE recurrence_group_id = ? AND is_cancelled = 0",
        (group_id,),
    ).fetchone()["c"]
    application_count = conn.execute(
        """
        SELECT COUNT(*) AS c
        FROM activity_applications ap
        JOIN activities a ON a.id = ap.activity_id
        WHERE a.recurrence_group_id = ?
          AND a.is_cancelled = 0
          AND ap.status IN ('waiting', 'confirmed')
        """,
        (group_id,),
    ).fetchone()["c"]

    preview_rows = conn.execute(
        """
        SELECT
            a.id,
            a.title,
            a.start_at,
            a.end_at,
            a.place,
            (
                SELECT COUNT(*)
                FROM activity_applications ap
                WHERE ap.activity_id = a.id
                  AND ap.status IN ('waiting', 'confirmed')
            ) AS active_applications
        FROM activities a
        WHERE a.recurrence_group_id = ?
          AND a.is_cancelled = 0
        ORDER BY a.start_at ASC
        LIMIT 5
        """,
        (group_id,),
    ).fetchall()
    conn.close()

    return jsonify(
        {
            "ok": True,
            "groupId": group_id,
            "impact": {
                "activityCount": int(activity_count or 0),
                "applicationCount": int(application_count or 0),
                "previewItems": [
                    {
                        "id": row["id"],
                        "title": row["title"],
                        "startAt": row["start_at"],
                        "endAt": row["end_at"],
                        "place": row["place"],
                        "applicationCount": int(row["active_applications"] or 0),
                    }
                    for row in preview_rows
                ],
            },
        }
    )


@active_member_required
def cancel_activity(activity_id):
    conn = get_db_connection()
    me = get_current_user_row(conn)
    if not me:
        conn.close()
        return jsonify({"ok": False, "message": "로그인이 필요합니다."}), 401
    target = conn.execute(
        "SELECT * FROM activity_applications WHERE activity_id = ? AND user_id = ?",
        (activity_id, me["id"]),
    ).fetchone()
    if not target:
        conn.close()
        return jsonify({"ok": False, "message": "신청 내역이 없습니다."}), 404

    conn.execute(
        "UPDATE activity_applications SET status = 'cancelled', updated_at = ? WHERE id = ?",
        (now_iso(), target["id"]),
    )
    conn.commit()
    conn.close()
    return jsonify({"ok": True, "message": "신청이 취소되었습니다."})


@role_required("staff")
def create_attendance_qr_token(activity_id):
    conn = get_db_connection()
    me = get_current_user_row(conn)
    if not me:
        conn.close()
        return jsonify({"ok": False, "message": "로그인이 필요합니다."}), 401
    activity = conn.execute(
        "SELECT id FROM activities WHERE id = ?", (activity_id,)
    ).fetchone()
    if not activity:
        conn.close()
        return jsonify({"ok": False, "message": "활동을 찾을 수 없습니다."}), 404

    token = uuid.uuid4().hex
    expires = (datetime.now() + timedelta(hours=2)).isoformat()
    conn.execute(
        "INSERT INTO attendance_qr_tokens (activity_id, token, expires_at, created_by, created_at) VALUES (?, ?, ?, ?, ?)",
        (activity_id, token, expires, me["id"], now_iso()),
    )
    conn.commit()
    conn.close()
    return jsonify({"ok": True, "token": token, "expiresAt": expires})


def calculate_activity_hours(activity):
    start_dt = parse_iso_datetime(activity["start_at"])
    end_dt = parse_iso_datetime(activity["end_at"])
    if start_dt and end_dt and end_dt > start_dt:
        return max(round((end_dt - start_dt).total_seconds() / 3600, 2), 0.5)
    return 2.0


@active_member_required
def qr_check_attendance(activity_id):
    payload = request.get_json(silent=True) or {}
    token = str(payload.get("token", "")).strip()
    if not token:
        return jsonify({"ok": False, "message": "토큰이 필요합니다."}), 400

    conn = get_db_connection()
    me = get_current_user_row(conn)
    if not me:
        conn.close()
        return jsonify({"ok": False, "message": "로그인이 필요합니다."}), 401
    qr = conn.execute(
        "SELECT * FROM attendance_qr_tokens WHERE activity_id = ? AND token = ?",
        (activity_id, token),
    ).fetchone()
    if not qr:
        conn.close()
        return jsonify({"ok": False, "message": "유효하지 않은 토큰입니다."}), 404

    expires = parse_iso_datetime(qr["expires_at"])
    if not expires or expires < datetime.now():
        conn.close()
        return jsonify({"ok": False, "message": "만료된 토큰입니다."}), 410

    app_row = conn.execute(
        "SELECT * FROM activity_applications WHERE activity_id = ? AND user_id = ?",
        (activity_id, me["id"]),
    ).fetchone()
    if not app_row:
        conn.close()
        return jsonify({"ok": False, "message": "신청 내역이 없습니다."}), 404

    activity = conn.execute(
        "SELECT * FROM activities WHERE id = ?", (activity_id,)
    ).fetchone()
    hours = calculate_activity_hours(activity)
    points = int(hours * 10)
    conn.execute(
        """
        UPDATE activity_applications
        SET status = 'confirmed', attendance_status = 'present', attendance_method = 'qr',
            hours = ?, points = ?, penalty_points = 0, updated_at = ?
        WHERE id = ?
        """,
        (hours, points, now_iso(), app_row["id"]),
    )
    conn.commit()
    conn.close()
    return jsonify({"ok": True, "hours": hours, "points": points})


@role_required("staff")
def bulk_attendance(activity_id):
    payload = request.get_json(silent=True) or {}
    entries = payload.get("entries", [])
    if not isinstance(entries, list) or not entries:
        return jsonify({"ok": False, "message": "entries 배열이 필요합니다."}), 400

    conn = get_db_connection()
    activity = conn.execute(
        "SELECT * FROM activities WHERE id = ?", (activity_id,)
    ).fetchone()
    if not activity:
        conn.close()
        return jsonify({"ok": False, "message": "활동을 찾을 수 없습니다."}), 404

    hours = calculate_activity_hours(activity)
    points = int(hours * 10)
    no_show_penalty = int(os.environ.get("WEAVE_NOSHOW_PENALTY", "2"))

    updated = 0
    for item in entries:
        user_id = int(item.get("userId", 0) or 0)
        status = str(item.get("status", "pending")).strip().lower()
        if user_id <= 0 or status not in ("present", "absent", "noshow"):
            continue

        app_row = conn.execute(
            "SELECT * FROM activity_applications WHERE activity_id = ? AND user_id = ?",
            (activity_id, user_id),
        ).fetchone()
        if not app_row:
            continue

        final_status = "confirmed" if status == "present" else app_row["status"]
        final_hours = hours if status == "present" else 0
        final_points = points if status == "present" else 0
        penalty = no_show_penalty if status == "noshow" else 0

        conn.execute(
            """
            UPDATE activity_applications
            SET status = ?, attendance_status = ?, attendance_method = 'bulk',
                hours = ?, points = ?, penalty_points = ?, updated_at = ?
            WHERE id = ?
            """,
            (
                final_status,
                status,
                final_hours,
                final_points,
                penalty,
                now_iso(),
                app_row["id"],
            ),
        )
        updated += 1

    conn.commit()
    conn.close()
    return jsonify({"ok": True, "updated": updated})


@active_member_required
def my_activity_history():
    conn = get_db_connection()
    me = get_current_user_row(conn)
    if not me:
        conn.close()
        return jsonify({"ok": False, "message": "로그인이 필요합니다."}), 401
    rows = conn.execute(
        """
        SELECT a.id AS activity_id, a.title, a.start_at, a.end_at, a.place,
               ap.status, ap.attendance_status, ap.hours, ap.points, ap.penalty_points
        FROM activity_applications ap
        JOIN activities a ON a.id = ap.activity_id
        WHERE ap.user_id = ?
        ORDER BY a.start_at DESC
        """,
        (me["id"],),
    ).fetchall()

    total_hours = sum(float(row["hours"] or 0) for row in rows)
    total_points = sum(int(row["points"] or 0) for row in rows) - sum(
        int(row["penalty_points"] or 0) for row in rows
    )
    items = [
        {
            "activityId": row["activity_id"],
            "title": row["title"],
            "startAt": row["start_at"],
            "endAt": row["end_at"],
            "place": row["place"],
            "status": row["status"],
            "attendanceStatus": row["attendance_status"],
            "hours": row["hours"],
            "points": row["points"],
            "penaltyPoints": row["penalty_points"],
        }
        for row in rows
    ]
    conn.close()
    return jsonify(
        {
            "ok": True,
            "summary": {
                "totalHours": round(total_hours, 2),
                "totalPoints": total_points,
                "certificateDownloadUrl": "/api/me/certificate.csv",
            },
            "items": items,
        }
    )


@active_member_required
def my_certificate_csv():
    conn = get_db_connection()
    me = get_current_user_row(conn)
    if not me:
        conn.close()
        return jsonify({"ok": False, "message": "로그인이 필요합니다."}), 401
    rows = conn.execute(
        """
        SELECT a.title, a.start_at, a.end_at, a.place, ap.hours, ap.attendance_status
        FROM activity_applications ap
        JOIN activities a ON a.id = ap.activity_id
        WHERE ap.user_id = ?
        ORDER BY a.start_at ASC
        """,
        (me["id"],),
    ).fetchall()
    conn.close()

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(
        ["이름", "아이디", "활동명", "시작", "종료", "장소", "출석상태", "봉사시간"]
    )
    for row in rows:
        writer.writerow(
            [
                me["name"],
                me["username"],
                row["title"],
                row["start_at"],
                row["end_at"],
                row["place"],
                row["attendance_status"],
                row["hours"],
            ]
        )

    response = Response(output.getvalue(), mimetype="text/csv; charset=utf-8")
    response.headers["Content-Disposition"] = (
        "attachment; filename=my_activity_certificate.csv"
    )
    return response


def make_thumbnail_like(url):
    if not url:
        return ""
    return url


def list_gallery_albums():
    conn = get_db_connection()
    rows = conn.execute("SELECT * FROM gallery_albums ORDER BY id DESC").fetchall()
    conn.close()
    return jsonify(
        {
            "ok": True,
            "items": [
                {
                    "id": row["id"],
                    "title": row["title"],
                    "activityId": row["activity_id"],
                    "visibility": row["visibility"],
                    "portraitConsent": bool(row["portrait_consent"]),
                    "createdAt": row["created_at"],
                }
                for row in rows
            ],
        }
    )


@role_required("staff")
def create_gallery_album():
    payload = request.get_json(silent=True) or {}
    title = str(payload.get("title", "")).strip()
    visibility = str(payload.get("visibility", "internal")).strip().lower()
    portrait_consent = bool(payload.get("portraitConsent", False))
    if not title:
        return jsonify({"ok": False, "message": "앨범 제목이 필요합니다."}), 400
    if visibility not in ("public", "private", "internal"):
        return jsonify({"ok": False, "message": "공개 범위가 올바르지 않습니다."}), 400
    if not portrait_consent:
        return jsonify({"ok": False, "message": "초상권 동의가 필요합니다."}), 400

    conn = get_db_connection()
    me = get_current_user_row(conn)
    if not me:
        conn.close()
        return jsonify({"ok": False, "message": "로그인이 필요합니다."}), 401
    cur = conn.cursor()
    cur.execute(
        "INSERT INTO gallery_albums (title, activity_id, visibility, portrait_consent, created_by, created_at) VALUES (?, ?, ?, ?, ?, ?)",
        (
            title,
            payload.get("activityId"),
            visibility,
            1 if portrait_consent else 0,
            me["id"],
            now_iso(),
        ),
    )
    album_id = cur.lastrowid
    conn.commit()
    conn.close()
    return jsonify({"ok": True, "albumId": album_id})


@role_required("staff")
def add_gallery_photos(album_id):
    payload = request.get_json(silent=True) or {}
    photos = payload.get("photos", [])
    if not isinstance(photos, list) or not photos:
        return jsonify({"ok": False, "message": "photos 배열이 필요합니다."}), 400

    conn = get_db_connection()
    album = conn.execute(
        "SELECT id FROM gallery_albums WHERE id = ?", (album_id,)
    ).fetchone()
    if not album:
        conn.close()
        return jsonify({"ok": False, "message": "앨범을 찾을 수 없습니다."}), 404

    created = 0
    for photo in photos:
        image_url = str(photo.get("imageUrl", "")).strip()
        if not image_url:
            continue
        title = str(photo.get("title", "")).strip()
        thumb = make_thumbnail_like(image_url)
        conn.execute(
            "INSERT INTO gallery_photos (album_id, title, image_url, thumbnail_url, created_at) VALUES (?, ?, ?, ?, ?)",
            (album_id, title, image_url, thumb, now_iso()),
        )
        created += 1

    conn.commit()
    conn.close()
    return jsonify({"ok": True, "created": created})


@admin_required
@db_write_retry
def delete_gallery_photo(photo_id):
    conn = get_db_connection()
    me = get_current_user_row(conn)
    if not me:
        conn.close()
        return error_response("Unauthorized", 401)

    row = conn.execute(
        "SELECT * FROM gallery_photos WHERE id = ?", (photo_id,)
    ).fetchone()
    if not row:
        conn.close()
        return error_response("사진을 찾을 수 없습니다.", 404)

    remove_file_safely(upload_url_to_path(row["image_url"]))
    remove_file_safely(upload_url_to_path(row["thumbnail_url"]))

    conn.execute("DELETE FROM gallery_photos WHERE id = ?", (photo_id,))
    conn.commit()
    conn.close()
    log_audit(me["id"], "delete_gallery_photo", "gallery_photo", photo_id)
    return success_response({"ok": True})


def get_press_kit():
    return jsonify(
        {
            "ok": True,
            "logoGuide": "로고는 원본 비율을 유지하고, 주변 여백을 확보해 사용하세요.",
            "officialIntro": "남양주청년봉사단 위브는 지역과 청년을 연결해 지속 가능한 변화를 만드는 청년 봉사 커뮤니티입니다.",
            "downloads": [
                {"label": "공식 로고", "url": "/logo.png"},
                {"label": "기관 소개문구", "url": "/api/press-kit"},
            ],
        }
    )


def list_rules_versions():
    conn = get_db_connection()
    rows = conn.execute(
        "SELECT id, version_tag, effective_date, summary, content, created_at FROM rules_versions ORDER BY id DESC"
    ).fetchall()
    conn.close()
    return jsonify(
        {
            "ok": True,
            "items": [
                {
                    "id": row["id"],
                    "version": row["version_tag"],
                    "effectiveDate": row["effective_date"],
                    "summary": row["summary"],
                    "content": row["content"],
                    "createdAt": row["created_at"],
                }
                for row in rows
            ],
        }
    )


@role_required("staff")
def create_rules_version():
    payload = request.get_json(silent=True) or {}
    version = str(payload.get("version", "")).strip()
    effective_date = str(payload.get("effectiveDate", "")).strip()
    summary = str(payload.get("summary", "")).strip()
    content = str(payload.get("content", "")).strip()

    if not version or not effective_date or not summary:
        return (
            jsonify(
                {"ok": False, "message": "version/effectiveDate/summary는 필수입니다."}
            ),
            400,
        )

    conn = get_db_connection()
    conn.execute(
        "INSERT INTO rules_versions (version_tag, effective_date, summary, content, created_at) VALUES (?, ?, ?, ?, ?)",
        (version, effective_date, summary, content, now_iso()),
    )
    conn.commit()
    conn.close()
    return jsonify({"ok": True, "message": "개정 이력이 등록되었습니다."})


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


def get_annual_report(year):
    conn = get_db_connection()
    data = build_annual_report(conn, year)
    conn.execute(
        """
        INSERT INTO annual_reports (report_year, total_activities, total_hours, total_participants, impact_metric, created_at, updated_at)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(report_year) DO UPDATE SET
            total_activities = excluded.total_activities,
            total_hours = excluded.total_hours,
            total_participants = excluded.total_participants,
            impact_metric = excluded.impact_metric,
            updated_at = excluded.updated_at
        """,
        (
            year,
            data["totalActivities"],
            data["totalHours"],
            data["totalParticipants"],
            data["impact"],
            now_iso(),
            now_iso(),
        ),
    )
    conn.commit()
    conn.close()
    return jsonify({"ok": True, "report": data})


@role_required("staff")
def admin_dashboard():
    today = datetime.now().date().isoformat()
    month_prefix = datetime.now().strftime("%Y-%m")

    conn = get_db_connection()
    today_schedule = conn.execute(
        "SELECT COUNT(*) AS c FROM activities WHERE date(start_at) = ?", (today,)
    ).fetchone()["c"]
    pending_users = conn.execute(
        "SELECT COUNT(*) AS c FROM users WHERE status = 'pending'"
    ).fetchone()["c"]
    waiting_apps = conn.execute(
        "SELECT COUNT(*) AS c FROM activity_applications WHERE status = 'waiting'"
    ).fetchone()["c"]
    noshows = conn.execute(
        "SELECT COUNT(*) AS c FROM activity_applications WHERE attendance_status = 'noshow'"
    ).fetchone()["c"]
    scheduled_notices = conn.execute(
        "SELECT COUNT(*) AS c FROM scheduled_notices WHERE status = 'pending'"
    ).fetchone()["c"]
    qna_unanswered = conn.execute(
        "SELECT COUNT(*) AS c FROM qna_posts WHERE TRIM(COALESCE(answer,'')) = ''"
    ).fetchone()["c"]
    expense_alerts = conn.execute(
        "SELECT COUNT(*) AS c FROM expenses WHERE settled = 0 AND substr(due_date,1,7) = ?",
        (month_prefix,),
    ).fetchone()["c"]
    conn.close()

    return jsonify(
        {
            "ok": True,
            "dashboard": {
                "todaySchedule": int(today_schedule or 0),
                "pendingApprovals": int(pending_users or 0),
                "waitingApplications": int(waiting_apps or 0),
                "noshowCount": int(noshows or 0),
                "scheduledNotices": int(scheduled_notices or 0),
                "qnaUnanswered": int(qna_unanswered or 0),
                "expenseAlerts": int(expense_alerts or 0),
            },
        }
    )


def csv_response(filename, headers, rows):
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(headers)
    for row in rows:
        writer.writerow(row)
    response = Response(output.getvalue(), mimetype="text/csv; charset=utf-8")
    response.headers["Content-Disposition"] = f"attachment; filename={filename}"
    return response


@role_required("staff")
def export_participants_csv():
    conn = get_db_connection()
    rows = conn.execute(
        "SELECT id, name, username, email, phone, role, status, generation FROM users ORDER BY id ASC"
    ).fetchall()
    conn.close()
    return csv_response(
        "participants.csv",
        ["id", "name", "username", "email", "phone", "role", "status", "generation"],
        [
            [
                row["id"],
                row["name"],
                row["username"],
                row["email"],
                row["phone"],
                row["role"],
                row["status"],
                row["generation"],
            ]
            for row in rows
        ],
    )


@role_required("staff")
def export_attendance_csv():
    conn = get_db_connection()
    rows = conn.execute("""
        SELECT a.title, a.start_at, u.name, u.username, ap.status, ap.attendance_status, ap.hours
        FROM activity_applications ap
        JOIN activities a ON a.id = ap.activity_id
        JOIN users u ON u.id = ap.user_id
        ORDER BY a.start_at DESC, u.username ASC
        """).fetchall()
    conn.close()
    return csv_response(
        "attendance.csv",
        [
            "activity",
            "start_at",
            "name",
            "username",
            "apply_status",
            "attendance_status",
            "hours",
        ],
        [
            [
                row["title"],
                row["start_at"],
                row["name"],
                row["username"],
                row["status"],
                row["attendance_status"],
                row["hours"],
            ]
            for row in rows
        ],
    )


@role_required("staff")
def export_hours_csv():
    conn = get_db_connection()
    rows = conn.execute("""
        SELECT u.name, u.username,
               COALESCE(SUM(ap.hours),0) AS total_hours,
               COALESCE(SUM(ap.points),0) AS total_points,
               COALESCE(SUM(ap.penalty_points),0) AS penalty_points
        FROM users u
        LEFT JOIN activity_applications ap ON ap.user_id = u.id
        GROUP BY u.id, u.name, u.username
        ORDER BY total_hours DESC
        """).fetchall()
    conn.close()
    return csv_response(
        "hours_summary.csv",
        ["name", "username", "total_hours", "total_points", "penalty_points"],
        [
            [
                row["name"],
                row["username"],
                row["total_hours"],
                row["total_points"],
                row["penalty_points"],
            ]
            for row in rows
        ],
    )


def get_templates():
    return jsonify(
        {
            "ok": True,
            "items": [
                {"type": "notice", "label": "공지 템플릿"},
                {"type": "review", "label": "활동 후기 템플릿"},
                {"type": "minutes", "label": "회의록 템플릿"},
            ],
        }
    )


def generate_template():
    payload = request.get_json(silent=True) or {}
    template_type = str(payload.get("type", "")).strip().lower()
    title = str(payload.get("title", "제목"))

    templates = {
        "notice": f"[공지] {title}\n\n1) 일정\n2) 장소\n3) 준비물\n4) 유의사항",
        "review": f"[활동후기] {title}\n\n- 활동 개요\n- 참여 소감\n- 다음 개선점",
        "minutes": f"[회의록] {title}\n\n- 참석자\n- 논의 안건\n- 결정 사항\n- 액션 아이템",
    }

    content = templates.get(template_type)
    if not content:
        return jsonify({"ok": False, "message": "지원하지 않는 템플릿입니다."}), 400
    return jsonify({"ok": True, "content": content})


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


@login_required
def list_events():
    page = max(1, int(request.args.get("page", "1") or 1))
    page_size = min(100, max(1, int(request.args.get("pageSize", "10") or 10)))
    offset = (page - 1) * page_size
    conn = get_db_connection()
    me = get_current_user_row(conn)
    if not me:
        conn.close()
        return error_response("Unauthorized", 401)
    if not role_at_least(me["role"], "MEMBER"):
        conn.close()
        return error_response("단원 이상만 이벤트를 확인할 수 있습니다.", 403)
    cache_key = f"events:list:{me['id']}:{page}:{page_size}"
    cached = get_cache(cache_key)
    if cached is not None:
        conn.close()
        return success_response(cached)

    total = conn.execute("SELECT COUNT(*) AS c FROM events").fetchone()["c"]
    rows = conn.execute(
        """
        SELECT e.*, u.username AS author_username,
               (SELECT COUNT(*) FROM event_participants p WHERE p.event_id = e.id AND p.status='registered') AS participant_count,
               (SELECT status FROM event_participants p2 WHERE p2.event_id = e.id AND p2.user_id = ? LIMIT 1) AS my_status
        FROM events e
        LEFT JOIN users u ON u.id = e.created_by
        ORDER BY COALESCE(e.start_datetime, e.event_date) ASC
        LIMIT ? OFFSET ?
        """,
        (me["id"], page_size, offset),
    ).fetchall()
    conn.close()
    data = {
        "items": [
            {
                "id": row["id"],
                "title": row["title"],
                "description": row["description"],
                "location": row["location"],
                "supplies": row["supplies"],
                "noticePostId": row["notice_post_id"],
                "startDatetime": row["start_datetime"] or row["event_date"],
                "endDatetime": row["end_datetime"]
                or row["start_datetime"]
                or row["event_date"],
                "capacity": int(row["capacity"] or row["max_participants"] or 0),
                "eventDate": row["event_date"],
                "maxParticipants": row["max_participants"],
                "participantCount": row["participant_count"],
                "createdBy": row["created_by"],
                "createdByUsername": row["author_username"],
                "createdAt": row["created_at"],
                "myStatus": row["my_status"],
            }
            for row in rows
        ],
        "pagination": {
            "total": int(total or 0),
            "page": page,
            "pageSize": page_size,
            "totalPages": max(1, (int(total or 0) + page_size - 1) // page_size),
        },
    }
    set_cache(cache_key, data)
    return success_response(data)


@role_required("EXECUTIVE")
@db_write_retry
def create_event():
    payload = request.get_json(silent=True) or {}
    title = str(payload.get("title", "")).strip()
    start_datetime = str(
        payload.get("start_datetime", payload.get("event_date", ""))
    ).strip()
    end_datetime = str(payload.get("end_datetime", start_datetime)).strip()
    if not title or not start_datetime:
        return error_response("title/start_datetime은 필수입니다.", 400)
    if not parse_iso_datetime(start_datetime) or not parse_iso_datetime(end_datetime):
        return error_response(
            "start_datetime/end_datetime은 ISO 형식이어야 합니다.", 400
        )

    conn = get_db_connection()
    me = get_current_user_row(conn)
    if not me:
        conn.close()
        return error_response("Unauthorized", 401)
    cur = conn.cursor()
    cur.execute(
        """
        INSERT INTO events (
            title, description, location, event_date, start_datetime, end_datetime,
            max_participants, capacity, supplies, notice_post_id, created_by, created_at, updated_at
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            title,
            str(payload.get("description", "")).strip(),
            str(payload.get("location", "")).strip(),
            start_datetime,
            start_datetime,
            end_datetime,
            int(payload.get("max_participants", payload.get("capacity", 0)) or 0),
            int(payload.get("capacity", payload.get("max_participants", 0)) or 0),
            str(payload.get("supplies", "")).strip(),
            payload.get("notice_post_id"),
            me["id"],
            now_iso(),
            now_iso(),
        ),
    )
    event_id = cur.lastrowid
    log_audit(conn, "create_event", "event", event_id, me["id"])
    record_user_activity(
        conn, me["id"], "event_create", "event", event_id, {"title": title}
    )
    conn.commit()
    conn.close()
    invalidate_cache("events:list:")
    write_app_log(
        "info", "create_event", user_id=me["id"], extra={"event_id": event_id}
    )
    return success_response({"event_id": event_id}, 201)


@role_required("EXECUTIVE")
def update_event(event_id):
    payload = request.get_json(silent=True) or {}
    conn = get_db_connection()
    me = get_current_user_row(conn)
    if not me:
        conn.close()
        return error_response("Unauthorized", 401)
    target = conn.execute("SELECT * FROM events WHERE id = ?", (event_id,)).fetchone()
    if not target:
        conn.close()
        return error_response("이벤트를 찾을 수 없습니다.", 404)

    title = str(payload.get("title", target["title"])).strip()
    description = str(payload.get("description", target["description"])).strip()
    location = str(payload.get("location", target["location"])).strip()
    supplies = str(payload.get("supplies", target["supplies"])).strip()
    notice_post_id = payload.get("notice_post_id", target["notice_post_id"])
    start_datetime = str(
        payload.get(
            "start_datetime",
            payload.get("event_date", target["start_datetime"] or target["event_date"]),
        )
    ).strip()
    end_datetime = str(
        payload.get("end_datetime", target["end_datetime"] or start_datetime)
    ).strip()
    capacity = int(
        payload.get(
            "capacity",
            payload.get(
                "max_participants", target["capacity"] or target["max_participants"]
            ),
        )
        or 0
    )
    if not parse_iso_datetime(start_datetime) or not parse_iso_datetime(end_datetime):
        conn.close()
        return error_response(
            "start_datetime/end_datetime은 ISO 형식이어야 합니다.", 400
        )

    conn.execute(
        """
        UPDATE events
        SET title = ?, description = ?, location = ?, supplies = ?, notice_post_id = ?,
            event_date = ?, start_datetime = ?, end_datetime = ?, max_participants = ?, capacity = ?, updated_at = ?
        WHERE id = ?
        """,
        (
            title,
            description,
            location,
            supplies,
            notice_post_id,
            start_datetime,
            start_datetime,
            end_datetime,
            capacity,
            capacity,
            now_iso(),
            event_id,
        ),
    )
    notified = send_event_change_notifications(conn, event_id, title)
    log_audit(conn, "update_event", "event", event_id, me["id"])
    conn.commit()
    conn.close()
    invalidate_cache("events:list:")
    write_app_log(
        "info",
        "update_event",
        user_id=me["id"],
        extra={"event_id": event_id, "notified": notified},
    )
    return success_response({"event_id": event_id, "notified": notified})


@login_required
def get_event_detail(event_id):
    conn = get_db_connection()
    me = get_current_user_row(conn)
    if not me:
        conn.close()
        return error_response("Unauthorized", 401)
    if not role_at_least(me["role"], "MEMBER"):
        conn.close()
        return error_response("단원 이상만 이벤트를 확인할 수 있습니다.", 403)

    row = conn.execute(
        """
        SELECT e.*, u.username AS author_username,
               (SELECT COUNT(*) FROM event_participants p WHERE p.event_id = e.id AND p.status = 'registered') AS participant_count,
               (SELECT status FROM event_participants p2 WHERE p2.event_id = e.id AND p2.user_id = ? LIMIT 1) AS my_status
        FROM events e
        LEFT JOIN users u ON u.id = e.created_by
        WHERE e.id = ?
        """,
        (me["id"], event_id),
    ).fetchone()
    if not row:
        conn.close()
        return error_response("이벤트를 찾을 수 없습니다.", 404)

    participants = conn.execute(
        """
        SELECT ep.user_id, ep.status, ep.created_at,
               u.username, u.nickname, u.role
        FROM event_participants ep
        JOIN users u ON u.id = ep.user_id
        WHERE ep.event_id = ? AND ep.status = 'registered'
        ORDER BY ep.created_at ASC
        """,
        (event_id,),
    ).fetchall()
    conn.close()

    return success_response(
        {
            "id": row["id"],
            "title": row["title"],
            "description": row["description"],
            "location": row["location"],
            "supplies": row["supplies"],
            "noticePostId": row["notice_post_id"],
            "startDatetime": row["start_datetime"] or row["event_date"],
            "endDatetime": row["end_datetime"]
            or row["start_datetime"]
            or row["event_date"],
            "capacity": int(row["capacity"] or row["max_participants"] or 0),
            "participantCount": int(row["participant_count"] or 0),
            "myStatus": row["my_status"],
            "createdBy": row["created_by"],
            "createdByUsername": row["author_username"],
            "createdAt": row["created_at"],
            "participants": [
                {
                    "userId": p["user_id"],
                    "status": p["status"],
                    "joinedAt": p["created_at"],
                    "nickname": p["nickname"] or p["username"],
                    "role": normalize_role(p["role"]),
                }
                for p in participants
            ],
        }
    )


@login_required
def list_event_participants(event_id):
    conn = get_db_connection()
    me = get_current_user_row(conn)
    if not me:
        conn.close()
        return error_response("Unauthorized", 401)
    if not role_at_least(me["role"], "MEMBER"):
        conn.close()
        return error_response("단원 이상만 참여자 목록을 확인할 수 있습니다.", 403)
    event = conn.execute("SELECT id FROM events WHERE id = ?", (event_id,)).fetchone()
    if not event:
        conn.close()
        return error_response("이벤트를 찾을 수 없습니다.", 404)
    rows = conn.execute(
        """
        SELECT ep.user_id, ep.status, ep.created_at,
               u.username, u.nickname, u.role
        FROM event_participants ep
        JOIN users u ON u.id = ep.user_id
        WHERE ep.event_id = ? AND ep.status = 'registered'
        ORDER BY ep.created_at ASC
        """,
        (event_id,),
    ).fetchall()
    conn.close()
    return success_response(
        {
            "items": [
                {
                    "userId": row["user_id"],
                    "status": row["status"],
                    "joinedAt": row["created_at"],
                    "nickname": row["nickname"] or row["username"],
                    "role": normalize_role(row["role"]),
                }
                for row in rows
            ]
        }
    )


@login_required
def join_event(event_id):
    conn = get_db_connection()
    me = get_current_user_row(conn)
    if not me:
        conn.close()
        return error_response("Unauthorized", 401)
    if not role_at_least(me["role"], "MEMBER"):
        conn.close()
        return error_response("단원 이상만 참여 신청할 수 있습니다.", 403)
    event = conn.execute("SELECT * FROM events WHERE id = ?", (event_id,)).fetchone()
    if not event:
        conn.close()
        return error_response("이벤트를 찾을 수 없습니다.", 404)

    active_count = conn.execute(
        "SELECT COUNT(*) AS c FROM event_participants WHERE event_id = ? AND status = 'registered'",
        (event_id,),
    ).fetchone()["c"]
    limit_count = int(event["capacity"] or event["max_participants"] or 0)
    if limit_count > 0 and active_count >= limit_count:
        conn.close()
        return error_response("모집 정원이 마감되었습니다.", 409)

    existing = conn.execute(
        "SELECT * FROM event_participants WHERE event_id = ? AND user_id = ?",
        (event_id, me["id"]),
    ).fetchone()

    if existing:
        conn.execute(
            "UPDATE event_participants SET status = 'registered', updated_at = ? WHERE id = ?",
            (now_iso(), existing["id"]),
        )
    else:
        conn.execute(
            "INSERT INTO event_participants (event_id, user_id, status, created_at, updated_at) VALUES (?, ?, 'registered', ?, ?)",
            (event_id, me["id"], now_iso(), now_iso()),
        )

    log_audit(conn, "join_event", "event", event_id, me["id"])
    record_user_activity(conn, me["id"], "event_join", "event", event_id)
    conn.commit()
    conn.close()
    invalidate_cache("events:list:")
    return success_response({"event_id": event_id, "status": "registered"})


@login_required
def cancel_event_participation(event_id):
    conn = get_db_connection()
    me = get_current_user_row(conn)
    if not me:
        conn.close()
        return error_response("Unauthorized", 401)
    if not role_at_least(me["role"], "MEMBER"):
        conn.close()
        return error_response("단원 이상만 참여 취소할 수 있습니다.", 403)
    existing = conn.execute(
        "SELECT * FROM event_participants WHERE event_id = ? AND user_id = ?",
        (event_id, me["id"]),
    ).fetchone()
    if not existing:
        conn.close()
        return error_response("참가 신청 이력이 없습니다.", 404)

    conn.execute(
        "UPDATE event_participants SET status = 'cancelled', updated_at = ? WHERE id = ?",
        (now_iso(), existing["id"]),
    )
    log_audit(conn, "cancel_event", "event", event_id, me["id"])
    record_user_activity(conn, me["id"], "event_cancel", "event", event_id)
    conn.commit()
    conn.close()
    invalidate_cache("events:list:")
    return success_response({"event_id": event_id, "status": "cancelled"})


@login_required
def list_posts():
    page = max(1, int(request.args.get("page", "1") or 1))
    page_size = min(100, max(1, int(request.args.get("pageSize", "10") or 10)))
    offset = (page - 1) * page_size
    category = (
        str(request.args.get("type", request.args.get("category", ""))).strip().lower()
    )
    keyword = str(request.args.get("query", request.args.get("q", ""))).strip()

    conn = get_db_connection()
    me = get_current_user_row(conn)
    is_staff = role_at_least(me["role"], "EXECUTIVE") if me else False

    where = ["1=1"]
    params = []
    if category in ("notice", "faq", "qna", "gallery", "review", "recruit"):
        mapped = "review" if category == "faq" else category
        where.append("p.category = ?")
        params.append(mapped)
    if keyword:
        where.append("(p.title LIKE ? OR p.content LIKE ?)")
        params.extend([f"%{keyword}%", f"%{keyword}%"])
    if not is_staff:
        where.append("(p.publish_at IS NULL OR p.publish_at <= ?)")
        params.append(now_iso())

    where_sql = " AND ".join(where)
    should_cache = category in ("notice", "gallery") and not keyword
    cache_key = f"posts:list:{category}:{page}:{page_size}:{int(bool(is_staff))}"
    if should_cache:
        cached = get_cache(cache_key)
        if cached is not None:
            conn.close()
            return success_response(cached)

    total = conn.execute(
        f"SELECT COUNT(*) AS c FROM posts p WHERE {where_sql}", params
    ).fetchone()["c"]
    rows = conn.execute(
        f"""
         SELECT p.*, u.username AS author_username, u.nickname AS author_nickname, u.role AS author_role,
               (SELECT COUNT(*) FROM post_files pf WHERE pf.post_id = p.id) AS file_count
        FROM posts p
        LEFT JOIN users u ON u.id = p.author_id
        WHERE {where_sql}
         ORDER BY CASE WHEN p.category = 'notice' THEN p.is_important ELSE 0 END DESC,
               CASE WHEN p.category = 'notice' THEN p.is_pinned ELSE 0 END DESC,
                 COALESCE(p.publish_at, p.created_at) DESC,
                 p.id DESC
        LIMIT ? OFFSET ?
        """,
        [*params, page_size, offset],
    ).fetchall()
    conn.close()

    items = [
        {
            "id": row["id"],
            "category": row["category"],
            "type": row["category"],
            "title": row["title"],
            "content": row["content"],
            "is_pinned": bool(row["is_pinned"]),
            "is_important": bool(row["is_important"]),
            "publish_at": row["publish_at"],
            "image_url": row["image_url"],
            "volunteerStartDate": row["volunteer_start_date"],
            "volunteerEndDate": row["volunteer_end_date"],
            "author_id": row["author_id"],
            "author_name": row["author_username"],
            "author": {
                "nickname": row["author_nickname"] or row["author_username"],
                "role": normalize_role(row["author_role"]),
                "role_label": role_to_label(row["author_role"]),
                "role_icon": role_to_icon(row["author_role"]),
            },
            "created_at": row["created_at"],
            "updated_at": row["updated_at"],
            "file_count": row["file_count"],
        }
        for row in rows
    ]
    data = {
        "items": items,
        "pagination": {
            "total": int(total or 0),
            "page": page,
            "pageSize": page_size,
            "totalPages": max(1, (int(total or 0) + page_size - 1) // page_size),
        },
    }
    if should_cache:
        set_cache(cache_key, data)
    return success_response(data)


@login_required
@db_write_retry
def create_post():
    payload = request.get_json(silent=True) or {}
    category = str(payload.get("category", "")).strip().lower()
    if category not in ("notice", "review", "recruit", "qna", "gallery"):
        return error_response(
            "type(category)는 notice|review|recruit|qna|gallery만 허용됩니다.", 400
        )
    title = str(payload.get("title", "")).strip()
    if not title:
        return error_response("title은 필수입니다.", 400)
    publish_at = str(payload.get("publish_at", "")).strip() or None
    if publish_at and not parse_iso_datetime(publish_at):
        return error_response("publish_at은 ISO 형식이어야 합니다.", 400)

    conn = get_db_connection()
    me = get_current_user_row(conn)
    if not me:
        conn.close()
        return error_response("Unauthorized", 401)
    if me["status"] == "suspended":
        conn.close()
        return error_response("정지된 계정은 게시글을 작성할 수 없습니다.", 403)

    if category in ("notice", "gallery") and not role_at_least(me["role"], "EXECUTIVE"):
        conn.close()
        return error_response("공지/갤러리 작성은 임원 이상만 가능합니다.", 403)

    if category == "qna" and not role_at_least(me["role"], "GENERAL"):
        conn.close()
        return error_response("Q&A 작성 권한이 없습니다.", 403)

    volunteer_start = str(payload.get("volunteerStartDate", "")).strip() or None
    volunteer_end = str(payload.get("volunteerEndDate", "")).strip() or volunteer_start

    cur = conn.cursor()
    cur.execute(
        """
        INSERT INTO posts (
            category, title, content, is_pinned, is_important, publish_at, image_url,
            volunteer_start_date, volunteer_end_date, author_id, created_at, updated_at
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            category,
            title,
            str(payload.get("content", "")),
            1 if bool(payload.get("is_pinned", False)) else 0,
            1 if bool(payload.get("is_important", False)) else 0,
            publish_at,
            str(payload.get("image_url", "")).strip(),
            volunteer_start,
            volunteer_end,
            me["id"],
            now_iso(),
            now_iso(),
        ),
    )
    post_id = cur.lastrowid

    if category == "notice" and volunteer_start:
        activity_start = f"{volunteer_start}T09:00:00"
        activity_end = f"{(volunteer_end or volunteer_start)}T18:00:00"
        conn.execute(
            """
            INSERT INTO activities (
                title, description, start_at, end_at, place, supplies, gather_time,
                manager_name, recruitment_limit, created_by, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                title,
                str(payload.get("content", ""))[:300],
                activity_start,
                activity_end,
                str(payload.get("place", "")).strip(),
                str(payload.get("supplies", "")).strip(),
                "",
                (
                    me["nickname"]
                    if "nickname" in me.keys() and me["nickname"]
                    else me["username"]
                ),
                int(payload.get("recruitment_limit", 0) or 0),
                me["id"],
                now_iso(),
            ),
        )

    log_audit(conn, "create_post", "post", post_id, me["id"], {"category": category})
    record_user_activity(
        conn, me["id"], "post_create", "post", post_id, {"category": category}
    )
    conn.commit()
    conn.close()
    invalidate_cache("posts:list:notice:")
    invalidate_cache("posts:list:gallery:")
    return success_response({"post_id": post_id}, 201)


@login_required
def get_post(post_id):
    conn = get_db_connection()
    me = get_current_user_row(conn)
    row = conn.execute(
        """
        SELECT p.*, u.username AS author_username, u.nickname AS author_nickname, u.role AS author_role
        FROM posts p
        LEFT JOIN users u ON u.id = p.author_id
        WHERE p.id = ?
        """,
        (post_id,),
    ).fetchone()
    if not row:
        conn.close()
        return error_response("게시글을 찾을 수 없습니다.", 404)

    is_staff = role_at_least(me["role"], "EXECUTIVE") if me else False
    publish_at_dt = parse_iso_datetime(row["publish_at"]) if row["publish_at"] else None
    if not is_staff and publish_at_dt and publish_at_dt > datetime.now():
        conn.close()
        return error_response("게시글을 찾을 수 없습니다.", 404)

    comments = conn.execute(
        """
        SELECT c.*, u.nickname, u.username, u.role
        FROM comments c
        JOIN users u ON u.id = c.user_id
        WHERE c.post_id = ?
        ORDER BY c.created_at ASC
        """,
        (post_id,),
    ).fetchall()
    recommend_count = conn.execute(
        "SELECT COUNT(*) AS c FROM recommends WHERE post_id = ?", (post_id,)
    ).fetchone()["c"]
    files = conn.execute(
        "SELECT id, original_name, mime_type, size, uploaded_at FROM post_files WHERE post_id = ? ORDER BY id DESC",
        (post_id,),
    ).fetchall()
    conn.close()

    return success_response(
        {
            "id": row["id"],
            "type": row["category"],
            "title": row["title"],
            "content": row["content"],
            "is_pinned": bool(row["is_pinned"]),
            "is_important": bool(row["is_important"]),
            "publish_at": row["publish_at"],
            "image_url": row["image_url"],
            "volunteerStartDate": row["volunteer_start_date"],
            "volunteerEndDate": row["volunteer_end_date"],
            "author": {
                "nickname": row["author_nickname"] or row["author_username"],
                "role": normalize_role(row["author_role"]),
                "role_label": role_to_label(row["author_role"]),
                "role_icon": role_to_icon(row["author_role"]),
            },
            "recommend_count": int(recommend_count or 0),
            "comments": [
                {
                    "id": c["id"],
                    "content": c["content"],
                    "parent_id": c["parent_id"],
                    "created_at": c["created_at"],
                    "author": {
                        "nickname": c["nickname"] or c["username"],
                        "role": normalize_role(c["role"]),
                        "role_label": role_to_label(c["role"]),
                        "role_icon": role_to_icon(c["role"]),
                    },
                }
                for c in comments
            ],
            "files": [dict(f) for f in files],
        }
    )


@role_required("staff")
def update_post(post_id):
    payload = request.get_json(silent=True) or {}
    conn = get_db_connection()
    me = get_current_user_row(conn)
    if not me:
        conn.close()
        return error_response("Unauthorized", 401)
    post = conn.execute("SELECT * FROM posts WHERE id = ?", (post_id,)).fetchone()
    if not post:
        conn.close()
        return error_response("게시글을 찾을 수 없습니다.", 404)
    category = str(payload.get("category", post["category"]))
    if category not in ("notice", "review", "recruit"):
        conn.close()
        return error_response("category는 notice|review|recruit만 허용됩니다.", 400)
    publish_at = (
        str(payload.get("publish_at", post["publish_at"] or "")).strip() or None
    )
    if publish_at and not parse_iso_datetime(publish_at):
        conn.close()
        return error_response("publish_at은 ISO 형식이어야 합니다.", 400)

    conn.execute(
        """
        UPDATE posts
        SET category = ?, title = ?, content = ?, is_pinned = ?, publish_at = ?, updated_at = ?
        WHERE id = ?
        """,
        (
            category,
            str(payload.get("title", post["title"])).strip(),
            str(payload.get("content", post["content"])),
            1 if bool(payload.get("is_pinned", bool(post["is_pinned"]))) else 0,
            publish_at,
            now_iso(),
            post_id,
        ),
    )
    log_audit(conn, "update_post", "post", post_id, me["id"])
    conn.commit()
    conn.close()
    invalidate_cache("posts:list:notice:")
    invalidate_cache("posts:list:gallery:")
    return success_response({"post_id": post_id})


@login_required
@db_write_retry
def delete_post(post_id):
    conn = get_db_connection()
    me = get_current_user_row(conn)
    if not me:
        conn.close()
        return error_response("Unauthorized", 401)
    post = conn.execute("SELECT * FROM posts WHERE id = ?", (post_id,)).fetchone()
    if not post:
        conn.close()
        return error_response("게시글을 찾을 수 없습니다.", 404)
    if not (
        role_at_least(me["role"], "EXECUTIVE")
        or int(post["author_id"] or 0) == int(me["id"])
    ):
        conn.close()
        return error_response("작성자 또는 운영권한이 필요합니다.", 403)
    files = conn.execute(
        "SELECT * FROM post_files WHERE post_id = ?", (post_id,)
    ).fetchall()
    for file_row in files:
        remove_file_safely(file_row["stored_path"])
    conn.execute("DELETE FROM post_files WHERE post_id = ?", (post_id,))
    conn.execute("DELETE FROM posts WHERE id = ?", (post_id,))
    log_audit(
        conn, "delete_post", "post", post_id, me["id"], {"category": post["category"]}
    )
    conn.commit()
    conn.close()
    invalidate_cache("posts:list:notice:")
    invalidate_cache("posts:list:gallery:")
    return success_response({"deleted": True})


@login_required
@db_write_retry
def create_post_comment(post_id):
    payload = request.get_json(silent=True) or {}
    content = str(payload.get("content", "")).strip()
    if not content:
        return error_response("댓글 내용을 입력해주세요.", 400)

    conn = get_db_connection()
    me = get_current_user_row(conn)
    if not me:
        conn.close()
        return error_response("Unauthorized", 401)
    if me["status"] == "suspended":
        conn.close()
        return error_response("정지된 계정은 댓글을 작성할 수 없습니다.", 403)
    post = conn.execute(
        "SELECT id, category FROM posts WHERE id = ?", (post_id,)
    ).fetchone()
    if not post:
        conn.close()
        return error_response("게시글을 찾을 수 없습니다.", 404)
    if post["category"] in ("notice", "gallery") and not role_at_least(
        me["role"], "MEMBER"
    ):
        conn.close()
        return error_response("공지/갤러리 댓글은 단원 이상만 가능합니다.", 403)

    cur = conn.cursor()
    cur.execute(
        """
        INSERT INTO comments (post_id, user_id, content, parent_id, created_at, updated_at)
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        (
            post_id,
            me["id"],
            content,
            payload.get("parent_id"),
            now_iso(),
            now_iso(),
        ),
    )
    comment_id = cur.lastrowid
    log_audit(conn, "create_comment", "post", post_id, me["id"])
    record_user_activity(
        conn, me["id"], "comment_create", "comment", comment_id, {"post_id": post_id}
    )
    conn.commit()
    conn.close()
    return success_response({"ok": True}, 201)


@login_required
def recommend_post(post_id):
    conn = get_db_connection()
    me = get_current_user_row(conn)
    if not me:
        conn.close()
        return error_response("Unauthorized", 401)
    post = conn.execute("SELECT id FROM posts WHERE id = ?", (post_id,)).fetchone()
    if not post:
        conn.close()
        return error_response("게시글을 찾을 수 없습니다.", 404)

    existing = conn.execute(
        "SELECT id FROM recommends WHERE post_id = ? AND user_id = ?",
        (post_id, me["id"]),
    ).fetchone()
    if existing:
        conn.close()
        return error_response("이미 추천하셨습니다.", 409)

    conn.execute(
        "INSERT INTO recommends (post_id, user_id, created_at) VALUES (?, ?, ?)",
        (post_id, me["id"], now_iso()),
    )
    log_audit(conn, "recommend_post", "post", post_id, me["id"])
    conn.commit()
    count = conn.execute(
        "SELECT COUNT(*) AS c FROM recommends WHERE post_id = ?", (post_id,)
    ).fetchone()["c"]
    conn.close()
    return success_response({"recommend_count": int(count or 0)})


@login_required
def important_notices():
    conn = get_db_connection()
    rows = conn.execute(
        """
        SELECT id, title, publish_at, created_at
        FROM posts
        WHERE category = 'notice' AND is_important = 1
          AND (publish_at IS NULL OR publish_at <= ?)
        ORDER BY is_pinned DESC, COALESCE(publish_at, created_at) DESC
        LIMIT 3
        """,
        (now_iso(),),
    ).fetchall()
    conn.close()
    return success_response({"items": [dict(row) for row in rows]})


@role_required("staff")
@db_write_retry
def upload_post_file(post_id):
    conn = get_db_connection()
    me = get_current_user_row(conn)
    if not me:
        conn.close()
        return error_response("Unauthorized", 401)
    post = conn.execute(
        "SELECT id, category FROM posts WHERE id = ?", (post_id,)
    ).fetchone()
    if not post:
        conn.close()
        return error_response("게시글을 찾을 수 없습니다.", 404)

    file_storage = request.files.get("file")
    file_info, err = save_uploaded_file(file_storage)
    if err:
        conn.close()
        return error_response(err, 400)
    if not file_info:
        conn.close()
        return error_response("파일 처리에 실패했습니다.", 400)

    cur = conn.cursor()
    cur.execute(
        """
        INSERT INTO post_files (post_id, original_name, stored_path, mime_type, size, uploaded_at)
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        (
            post_id,
            file_info["original_name"],
            file_info["stored_path"],
            file_info["mime_type"],
            int(file_info["size"]),
            now_iso(),
        ),
    )
    file_id = cur.lastrowid
    if post["category"] == "gallery":
        relative_path = os.path.relpath(file_info["stored_path"], UPLOAD_DIR).replace(
            "\\", "/"
        )
        conn.execute(
            "UPDATE posts SET image_url = ? WHERE id = ?",
            (f"/uploads/{relative_path}", post_id),
        )
    log_audit(conn, "upload_post_file", "post", post_id, me["id"])
    conn.commit()
    conn.close()
    return success_response({"file_id": file_id}, 201)


@login_required
def list_post_files(post_id):
    conn = get_db_connection()
    rows = conn.execute(
        "SELECT id, original_name, mime_type, size, uploaded_at FROM post_files WHERE post_id = ? ORDER BY id DESC",
        (post_id,),
    ).fetchall()
    conn.close()
    return success_response({"items": [dict(row) for row in rows]})


@login_required
def download_post_file(file_id):
    conn = get_db_connection()
    row = conn.execute("SELECT * FROM post_files WHERE id = ?", (file_id,)).fetchone()
    conn.close()
    if not row:
        return error_response("파일을 찾을 수 없습니다.", 404)
    if not os.path.exists(row["stored_path"]):
        return error_response("저장된 파일이 없습니다.", 404)
    return send_file(
        row["stored_path"], as_attachment=True, download_name=row["original_name"]
    )


@admin_required
def admin_stats():
    conn = get_db_connection()
    total_users = conn.execute("SELECT COUNT(*) AS c FROM users").fetchone()["c"]
    total_events = conn.execute("SELECT COUNT(*) AS c FROM events").fetchone()["c"]
    total_participants = conn.execute(
        "SELECT COUNT(*) AS c FROM participants WHERE status='registered'"
    ).fetchone()["c"]
    upcoming_events = conn.execute(
        "SELECT COUNT(*) AS c FROM events WHERE event_date >= ?",
        (datetime.now().isoformat(),),
    ).fetchone()["c"]
    recent_signups_rows = conn.execute(
        "SELECT id, username, email, join_date FROM users ORDER BY join_date DESC LIMIT 10"
    ).fetchall()
    conn.close()
    return success_response(
        {
            "total_users": int(total_users or 0),
            "total_events": int(total_events or 0),
            "total_participants": int(total_participants or 0),
            "upcoming_events": int(upcoming_events or 0),
            "recent_signups": [dict(row) for row in recent_signups_rows],
        }
    )


@admin_required
def get_audit_logs():
    page = max(1, int(request.args.get("page", "1") or 1))
    page_size = min(100, max(1, int(request.args.get("pageSize", "20") or 20)))
    offset = (page - 1) * page_size
    action = str(request.args.get("action", "")).strip()
    target_type = str(request.args.get("target_type", "")).strip()
    actor_user_id = str(
        request.args.get("actor_user_id", request.args.get("user_id", ""))
    ).strip()
    created_from = str(request.args.get("created_from", "")).strip()
    created_to = str(request.args.get("created_to", "")).strip()

    where = ["1=1"]
    params = []
    if action:
        where.append("action = ?")
        params.append(action)
    if target_type:
        where.append("target_type = ?")
        params.append(target_type)
    if actor_user_id:
        where.append("actor_user_id = ?")
        params.append(actor_user_id)
    if created_from:
        where.append("created_at >= ?")
        params.append(created_from)
    if created_to:
        where.append("created_at <= ?")
        params.append(created_to)

    where_sql = " AND ".join(where)
    conn = get_db_connection()
    total = conn.execute(
        f"SELECT COUNT(*) AS c FROM audit_logs WHERE {where_sql}", params
    ).fetchone()["c"]
    rows = conn.execute(
        f"""
        SELECT a.*,
               u.username AS actor_username
        FROM audit_logs a
        LEFT JOIN users u ON u.id = a.actor_user_id
        WHERE {where_sql}
        ORDER BY a.id DESC
        LIMIT ? OFFSET ?
        """,
        [*params, page_size, offset],
    ).fetchall()
    conn.close()

    return success_response(
        {
            "items": [dict(row) for row in rows],
            "pagination": {
                "total": int(total or 0),
                "page": page,
                "pageSize": page_size,
                "totalPages": max(1, (int(total or 0) + page_size - 1) // page_size),
            },
        }
    )


@login_required
def user_profile():
    row = get_current_user_row()
    return success_response({"user": user_row_to_dict(row)})


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

    conn.execute(
        "UPDATE users SET nickname = ?, nickname_updated_at = ? WHERE id = ?",
        (nickname, now_iso(), me["id"]),
    )
    return (
        conn.execute("SELECT * FROM users WHERE id = ?", (me["id"],)).fetchone(),
        None,
    )


@login_required
@db_write_retry
def update_my_nickname():
    payload = request.get_json(silent=True) or {}
    nickname = str(payload.get("nickname", "")).strip()
    valid, message = validate_nickname(nickname)
    if not valid:
        return error_response(message, 400)

    conn = get_db_connection()
    me = get_current_user_row(conn)
    if not me:
        conn.close()
        return error_response("Unauthorized", 401)

    updated, err = _update_nickname_common(conn, me, nickname, bypass_window=False)
    if err:
        conn.close()
        return err
    log_audit(
        conn, "change_nickname", "user", me["id"], me["id"], {"nickname": nickname}
    )
    record_user_activity(
        conn, me["id"], "nickname_change", "user", me["id"], {"nickname": nickname}
    )
    conn.commit()
    conn.close()
    return success_response(
        {"message": "닉네임이 변경되었습니다.", "user": user_row_to_dict(updated)}
    )


@login_required
def list_my_activity():
    conn = get_db_connection()
    me = get_current_user_row(conn)
    if not me:
        conn.close()
        return error_response("Unauthorized", 401)
    rows = conn.execute(
        """
        SELECT activity_type, target_type, target_id, metadata_json, created_at
        FROM user_activity
        WHERE user_id = ?
        ORDER BY id DESC
        LIMIT 50
        """,
        (me["id"],),
    ).fetchall()
    conn.close()
    return success_response(
        {
            "items": [
                {
                    "type": row["activity_type"],
                    "targetType": row["target_type"],
                    "targetId": row["target_id"],
                    "metadata": json.loads(row["metadata_json"] or "{}"),
                    "createdAt": row["created_at"],
                }
                for row in rows
            ]
        }
    )


@admin_required
@db_write_retry
def admin_update_user_nickname(user_id):
    payload = request.get_json(silent=True) or {}
    nickname = str(payload.get("nickname", "")).strip()
    valid, message = validate_nickname(nickname)
    if not valid:
        return error_response(message, 400)

    conn = get_db_connection()
    me = get_current_user_row(conn)
    if not me:
        conn.close()
        return error_response("Unauthorized", 401)
    target = conn.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()
    if not target:
        conn.close()
        return error_response("사용자를 찾을 수 없습니다.", 404)

    updated, err = _update_nickname_common(conn, target, nickname, bypass_window=True)
    if err:
        conn.close()
        return err
    log_audit(
        conn, "admin_change_nickname", "user", user_id, me["id"], {"nickname": nickname}
    )
    conn.commit()
    conn.close()
    return success_response(
        {"message": "닉네임이 변경되었습니다.", "user": user_row_to_dict(updated)}
    )


@login_required
def update_user_nickname_legacy():
    return update_my_nickname()


@login_required
def request_role_change():
    payload = request.get_json(silent=True) or {}
    target = normalize_role(payload.get("to_role", ""))
    return request_role_change_internal(target)


@login_required
def request_member_role():
    request.get_json(silent=True)
    conn = get_db_connection()
    me = get_current_user_row(conn)
    if not me:
        conn.close()
        return error_response("Unauthorized", 401)
    conn.close()
    if normalize_role(me["role"]) != "GENERAL":
        return error_response("일반 회원만 단원 승격을 요청할 수 있습니다.", 400)
    return request_role_change_internal("MEMBER")


@login_required
def request_executive_role():
    request.get_json(silent=True)
    conn = get_db_connection()
    me = get_current_user_row(conn)
    if not me:
        conn.close()
        return error_response("Unauthorized", 401)
    conn.close()
    if normalize_role(me["role"]) != "MEMBER":
        return error_response("단원만 임원 승격을 요청할 수 있습니다.", 400)
    return request_role_change_internal("EXECUTIVE")


def request_role_change_internal(target):
    conn = get_db_connection()
    me = get_current_user_row(conn)
    if not me:
        conn.close()
        return error_response("Unauthorized", 401)

    current = normalize_role(me["role"])
    target = normalize_role(target)
    allowed = {("GENERAL", "MEMBER"), ("MEMBER", "EXECUTIVE")}
    if (current, target) not in allowed:
        conn.close()
        return error_response("요청 가능한 역할 전환이 아닙니다.", 400)

    pending = conn.execute(
        "SELECT id FROM role_requests WHERE user_id = ? AND status = 'PENDING'",
        (me["id"],),
    ).fetchone()
    if pending:
        conn.close()
        return error_response("이미 처리 대기 중인 요청이 있습니다.", 409)

    cur = conn.cursor()
    cur.execute(
        """
        INSERT INTO role_requests (user_id, from_role, to_role, status, created_at)
        VALUES (?, ?, ?, 'PENDING', ?)
        """,
        (me["id"], current, target, now_iso()),
    )
    request_id = cur.lastrowid
    log_audit(
        conn,
        "request_role_change",
        "role_request",
        request_id,
        me["id"],
        {"from": current, "to": target},
    )
    conn.commit()
    conn.close()
    return success_response({"request_id": request_id}, 201)


@roles_required(["ADMIN", "LEADER", "VICE_LEADER"])
def list_role_requests():
    status = str(request.args.get("status", "PENDING")).strip().upper()
    page = max(1, int(request.args.get("page", "1") or 1))
    page_size = min(100, max(1, int(request.args.get("pageSize", "20") or 20)))
    offset = (page - 1) * page_size

    conn = get_db_connection()
    total = conn.execute(
        "SELECT COUNT(*) AS c FROM role_requests WHERE status = ?", (status,)
    ).fetchone()["c"]
    rows = conn.execute(
        """
        SELECT rr.*, u.username, u.nickname
        FROM role_requests rr
        JOIN users u ON u.id = rr.user_id
        WHERE rr.status = ?
        ORDER BY rr.id DESC
        LIMIT ? OFFSET ?
        """,
        (status, page_size, offset),
    ).fetchall()
    conn.close()
    return success_response(
        {
            "items": [dict(row) for row in rows],
            "pagination": {
                "total": int(total or 0),
                "page": page,
                "pageSize": page_size,
                "totalPages": max(1, (int(total or 0) + page_size - 1) // page_size),
            },
        }
    )


@db_write_retry
def _decide_role_request(request_id, approve=True):
    conn = get_db_connection()
    me = get_current_user_row(conn)
    if not me:
        conn.close()
        return error_response("Unauthorized", 401)
    req = conn.execute(
        "SELECT * FROM role_requests WHERE id = ?", (request_id,)
    ).fetchone()
    if not req:
        conn.close()
        return error_response("요청을 찾을 수 없습니다.", 404)
    if req["status"] != "PENDING":
        conn.close()
        return error_response("이미 처리된 요청입니다.", 409)

    next_status = "APPROVED" if approve else "REJECTED"
    conn.execute(
        "UPDATE role_requests SET status = ?, decided_at = ?, decided_by = ? WHERE id = ?",
        (next_status, now_iso(), me["id"], request_id),
    )
    if approve:
        conn.execute(
            "UPDATE users SET role = ?, is_admin = CASE WHEN ? = 'ADMIN' THEN 1 ELSE is_admin END WHERE id = ?",
            (req["to_role"], req["to_role"], req["user_id"]),
        )
    log_audit(
        conn,
        f"role_request_{next_status.lower()}",
        "role_request",
        request_id,
        me["id"],
        {"user_id": req["user_id"]},
    )
    conn.commit()
    conn.close()
    return success_response({"request_id": request_id, "status": next_status})


@roles_required(["ADMIN", "LEADER", "VICE_LEADER"])
def approve_role_request(request_id):
    return _decide_role_request(request_id, True)


@roles_required(["ADMIN", "LEADER", "VICE_LEADER"])
def deny_role_request(request_id):
    return _decide_role_request(request_id, False)


@roles_required(["ADMIN", "LEADER", "VICE_LEADER"])
def list_role_requests_legacy():
    return list_role_requests()


@roles_required(["ADMIN", "LEADER", "VICE_LEADER"])
def approve_role_request_legacy(request_id):
    return _decide_role_request(request_id, True)


@roles_required(["ADMIN", "LEADER", "VICE_LEADER"])
def reject_role_request_legacy(request_id):
    return _decide_role_request(request_id, False)


def serve_uploaded_file(filename):
    safe_rel = os.path.normpath(filename).replace("\\", "/").lstrip("/")
    if safe_rel.startswith("..") or "/../" in safe_rel:
        return error_response("Invalid path", 400)

    full_path = os.path.abspath(os.path.join(UPLOAD_DIR, safe_rel))
    uploads_root = os.path.abspath(UPLOAD_DIR)
    if not full_path.startswith(uploads_root):
        return error_response("Invalid path", 400)
    if not os.path.exists(full_path):
        return error_response("파일을 찾을 수 없습니다.", 404)

    conn = get_db_connection()
    row = conn.execute(
        "SELECT pf.id, p.category FROM post_files pf LEFT JOIN posts p ON p.id = pf.post_id WHERE pf.stored_path = ?",
        (full_path,),
    ).fetchone()

    if row and row["category"] == "gallery":
        conn.close()
        return send_file(full_path)

    me = get_current_user_row(conn)
    if not me:
        conn.close()
        return error_response("Unauthorized", 401)
    if not role_at_least(me["role"], "MEMBER"):
        conn.close()
        return error_response("단원 이상만 접근할 수 있습니다.", 403)
    conn.close()
    return send_file(full_path)


@login_required
def event_detail(event_id):
    conn = get_db_connection()
    me = get_current_user_row(conn)
    if not me:
        conn.close()
        return error_response("Unauthorized", 401)
    if not role_at_least(me["role"], "MEMBER"):
        conn.close()
        return error_response("단원 이상만 접근할 수 있습니다.", 403)

    event = conn.execute("SELECT * FROM events WHERE id = ?", (event_id,)).fetchone()
    if not event:
        conn.close()
        return error_response("이벤트를 찾을 수 없습니다.", 404)
    votes = conn.execute(
        "SELECT vote_status, COUNT(*) AS c FROM event_votes WHERE event_id = ? GROUP BY vote_status",
        (event_id,),
    ).fetchall()
    my_vote = conn.execute(
        "SELECT vote_status FROM event_votes WHERE event_id = ? AND user_id = ?",
        (event_id, me["id"]),
    ).fetchone()
    conn.close()

    summary = {"ATTEND": 0, "ABSENT": 0, "WAITING": 0}
    for row in votes:
        key = str(row["vote_status"] or "").upper()
        if key in summary:
            summary[key] = int(row["c"] or 0)
    return success_response(
        {
            "event": dict(event),
            "summary": summary,
            "my_vote": my_vote["vote_status"] if my_vote else None,
        }
    )


@login_required
def vote_event(event_id):
    payload = request.get_json(silent=True) or {}
    status = str(payload.get("status", "")).strip().upper()
    if status not in ("ATTEND", "ABSENT", "WAITING"):
        return error_response(
            "투표 상태는 ATTEND/ABSENT/WAITING 중 하나여야 합니다.", 400
        )

    conn = get_db_connection()
    me = get_current_user_row(conn)
    if not me:
        conn.close()
        return error_response("Unauthorized", 401)
    if not role_at_least(me["role"], "MEMBER"):
        conn.close()
        return error_response("단원 이상만 투표할 수 있습니다.", 403)

    event = conn.execute("SELECT id FROM events WHERE id = ?", (event_id,)).fetchone()
    if not event:
        conn.close()
        return error_response("이벤트를 찾을 수 없습니다.", 404)

    existing = conn.execute(
        "SELECT id FROM event_votes WHERE event_id = ? AND user_id = ?",
        (event_id, me["id"]),
    ).fetchone()
    if existing:
        conn.execute(
            "UPDATE event_votes SET vote_status = ?, updated_at = ? WHERE id = ?",
            (status, now_iso(), existing["id"]),
        )
    else:
        conn.execute(
            "INSERT INTO event_votes (event_id, user_id, vote_status, created_at, updated_at) VALUES (?, ?, ?, ?, ?)",
            (event_id, me["id"], status, now_iso(), now_iso()),
        )
    log_audit(conn, "vote_event", "event", event_id, me["id"], {"status": status})
    conn.commit()
    conn.close()
    return success_response({"event_id": event_id, "status": status})


def handle_400(error):
    if is_api_request():
        return error_response("Bad Request", 400)
    return error


def handle_401(error):
    if is_api_request():
        return error_response("Unauthorized", 401)
    return error


def handle_403(error):
    if is_api_request():
        return error_response("Forbidden", 403)
    return error


def handle_404(error):
    if is_api_request():
        return error_response("Not Found", 404)
    return send_from_directory(STATIC_DIR, "index.html")


def handle_500(error):
    logger.exception(
        json.dumps(
            {
                "timestamp": now_iso(),
                "request_id": getattr(g, "request_id", ""),
                "user_id": session.get("user_id"),
                "path": request.path if request else "",
                "status_code": 500,
                "error": str(error),
            },
            ensure_ascii=False,
        )
    )
    if is_api_request():
        return error_response("Internal Server Error", 500)
    return error


def is_sensitive_path(path):
    lowered = str(path or "").lower()
    sensitive_suffixes = (".db", ".env", ".py", ".sqlite", ".sqlite3")
    return (
        ".." in lowered
        or lowered.startswith(".")
        or lowered.endswith(sensitive_suffixes)
        or "__pycache__" in lowered
        or lowered.startswith("instance/")
    )


def static_proxy(path):
    normalized = str(path or "").strip().lstrip("/")
    if normalized.startswith("api/"):
        return error_response("Not Found", 404)
    if is_sensitive_path(normalized):
        return error_response("Forbidden", 403)

    candidate = os.path.join(STATIC_DIR, normalized)
    if os.path.isfile(candidate):
        return send_from_directory(STATIC_DIR, normalized)
    return send_from_directory(STATIC_DIR, "index.html")
