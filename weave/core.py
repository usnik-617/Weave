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

MAX_UPLOAD_MB = int(os.environ.get("MAX_UPLOAD_MB", "25"))
MAX_UPLOAD_BYTES = MAX_UPLOAD_MB * 1024 * 1024
POST_TOTAL_UPLOAD_MB = int(os.environ.get("POST_TOTAL_UPLOAD_MB", "300"))
POST_TOTAL_UPLOAD_BYTES = POST_TOTAL_UPLOAD_MB * 1024 * 1024
UPLOAD_RATE_LIMIT_COUNT = int(os.environ.get("UPLOAD_RATE_LIMIT_COUNT", "240"))
UPLOAD_RATE_LIMIT_WINDOW_SEC = int(os.environ.get("UPLOAD_RATE_LIMIT_WINDOW_SEC", "60"))
UPLOAD_BATCH_MAX_FILES = int(os.environ.get("UPLOAD_BATCH_MAX_FILES", "12"))
UPLOAD_GALLERY_THUMBNAIL_MODE = (
    str(os.environ.get("UPLOAD_GALLERY_THUMBNAIL_MODE", "cover_only")).strip().lower()
)
MEDIA_QUEUE_BACKEND = str(os.environ.get("WEAVE_MEDIA_QUEUE_BACKEND", "rq")).strip().lower()
MEDIA_WORKER_COUNT = int(os.environ.get("WEAVE_MEDIA_WORKER_COUNT", "2"))
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
from weave.time_utils import (
    activity_start_date_local,
    now_iso,
    parse_iso_datetime,
    post_visibility_status,
    should_expose_post,
)
from weave.validators import (
    normalize_contact,
    to_list_text,
    validate_nickname,
    validate_password_policy,
    validate_signup_payload,
)


def get_client_ip():
    from weave import core_utils

    return core_utils.get_client_ip()


def get_user_agent():
    from weave import core_utils

    return core_utils.get_user_agent()


def parse_rate_limit_bucket(ip):
    from weave import core_state

    return core_state.parse_rate_limit_bucket(ip)


def get_rate_limit_key(action, username_hint=""):
    from weave import core_state

    return core_state.get_rate_limit_key(action, username_hint)


def is_rate_limited(action, username_hint=""):
    from weave import core_state

    return core_state.is_rate_limited(action, username_hint)


def mark_rate_limit_failure(action, username_hint=""):
    from weave import core_state

    return core_state.mark_rate_limit_failure(action, username_hint)


def clear_rate_limit(action, username_hint=""):
    from weave import core_state

    return core_state.clear_rate_limit(action, username_hint)


def is_ip_blocked(ip):
    from weave import core_state

    return core_state.is_ip_blocked(ip)


def register_login_failure(ip):
    from weave import core_state

    return core_state.register_login_failure(ip)


def reset_login_failures_by_ip(ip):
    from weave import core_state

    return core_state.reset_login_failures_by_ip(ip)


def clear_all_rate_limit_state():
    from weave import core_state

    return core_state.clear_all_rate_limit_state()


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


def transaction(conn):
    from weave import core_db

    return core_db.transaction(conn)


def _cache_now():
    from weave import core_state

    return core_state._cache_now()


def get_cache(key):
    from weave import core_state

    return core_state.get_cache(key)


def set_cache(key, value, ttl_seconds=CACHE_TTL_SECONDS):
    from weave import core_state

    return core_state.set_cache(key, value, ttl_seconds)


def invalidate_cache(prefix):
    from weave import core_state

    return core_state.invalidate_cache(prefix)


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


def ensure_posts_migration(cur):
    from weave import core_db_bootstrap

    return core_db_bootstrap.ensure_posts_migration(cur)


def ensure_activities_migration(cur):
    from weave import core_db_bootstrap

    return core_db_bootstrap.ensure_activities_migration(cur)


def ensure_activity_indexes(cur):
    from weave import core_db_bootstrap

    return core_db_bootstrap.ensure_activity_indexes(cur)


def ensure_events_migration(cur):
    from weave import core_db_bootstrap

    return core_db_bootstrap.ensure_events_migration(cur)


def ensure_post_files_migration(cur):
    from weave import core_db_bootstrap

    return core_db_bootstrap.ensure_post_files_migration(cur)


def ensure_attendance_migration(cur):
    from weave import core_db_bootstrap

    return core_db_bootstrap.ensure_attendance_migration(cur)


def init_db():
    from weave import core_db_bootstrap

    if str(DATABASE_URL).strip().lower().startswith("postgres"):
        logger.info("postgres_runtime_mode enabled: skip sqlite bootstrap on startup")
        return None
    return core_db_bootstrap.init_db(DEFAULT_ADMIN_PASSWORD)


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
    from weave import core_user_state_service

    return core_user_state_service.mark_dormant_users(reference_time)


def serialize_activity_row(row):
    from weave import core_response_helpers

    return core_response_helpers.serialize_activity_row(row)


def calculate_activity_hours(activity):
    from weave import core_time_helpers

    return core_time_helpers.calculate_activity_hours(activity)


def build_annual_report(conn, year):
    from weave import core_response_helpers

    return core_response_helpers.build_annual_report(conn, year)


def csv_response(filename, headers, rows):
    from weave import core_response_helpers

    return core_response_helpers.csv_response(filename, headers, rows)


def send_event_change_notifications(conn, event_id, title):
    from weave import core_notification_service

    return core_notification_service.send_event_change_notifications(conn, event_id, title)


def send_due_event_reminders(reference_time=None):
    from weave import core_notification_service

    return core_notification_service.send_due_event_reminders(reference_time)


def send_event_reminders(reference_time=None):
    from weave import core_notification_service

    return core_notification_service.send_event_reminders(reference_time)


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


