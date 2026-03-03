import os
import re
import sqlite3
import uuid
import csv
import io
from functools import wraps
from datetime import datetime, timedelta, timezone

from flask import Flask, Response, jsonify, request, send_from_directory, session
from werkzeug.middleware.proxy_fix import ProxyFix
from werkzeug.security import check_password_hash, generate_password_hash


BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, "weave.db")
WEAVE_ENV = os.environ.get("WEAVE_ENV", "development").lower()
DEFAULT_ADMIN_PASSWORD = "Weave!2026"
ROLE_ORDER = {"member": 1, "staff": 2, "admin": 3}
KST = timezone(timedelta(hours=9))

app = Flask(__name__, static_folder=BASE_DIR, static_url_path="")
app.config["SECRET_KEY"] = os.environ.get("WEAVE_SECRET_KEY", "weave-local-dev-secret-key")
app.config["MAX_CONTENT_LENGTH"] = int(os.environ.get("WEAVE_MAX_CONTENT_LENGTH", 1024 * 1024))
app.config["SESSION_COOKIE_HTTPONLY"] = True
app.config["SESSION_COOKIE_SAMESITE"] = os.environ.get("WEAVE_SESSION_SAMESITE", "Lax")
app.config["SESSION_COOKIE_SECURE"] = WEAVE_ENV == "production"
app.config["PERMANENT_SESSION_LIFETIME"] = timedelta(
    seconds=int(os.environ.get("WEAVE_SESSION_LIFETIME_SEC", 60 * 60 * 24 * 7))
)

if WEAVE_ENV == "production" and app.config["SECRET_KEY"] == "weave-local-dev-secret-key":
    raise RuntimeError("WEAVE_SECRET_KEY 환경변수가 필요합니다.")

trusted_hosts = [item.strip() for item in os.environ.get("WEAVE_TRUSTED_HOSTS", "").split(",") if item.strip()]
if trusted_hosts:
    app.config["TRUSTED_HOSTS"] = trusted_hosts

proxy_hops = int(os.environ.get("WEAVE_PROXY_HOPS", "1"))
app.wsgi_app = ProxyFix(app.wsgi_app, x_for=proxy_hops, x_proto=proxy_hops, x_host=proxy_hops, x_port=proxy_hops)


def get_db_connection():
    conn = sqlite3.connect(DB_PATH, timeout=10)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA busy_timeout = 10000")
    return conn


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


def normalize_contact(value):
    return str(value or "").replace("-", "").strip().lower()


def to_list_text(value):
    if isinstance(value, list):
        return ", ".join([str(item).strip() for item in value if str(item).strip()])
    return str(value or "").strip()


def role_at_least(role, minimum):
    return ROLE_ORDER.get(role or "member", 0) >= ROLE_ORDER.get(minimum, 0)


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
            return jsonify({"ok": False, "message": "로그인이 필요합니다."}), 401
        return func(*args, **kwargs)

    return wrapper


def role_required(min_role):
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            user = get_current_user_row()
            if not user:
                return jsonify({"ok": False, "message": "로그인이 필요합니다."}), 401
            if not role_at_least(user["role"], min_role):
                return jsonify({"ok": False, "message": "권한이 없습니다."}), 403
            return func(*args, **kwargs)

        return wrapper

    return decorator


def active_member_required(func):
    @wraps(func)
    def wrapper(*args, **kwargs):
        user = get_current_user_row()
        if not user:
            return jsonify({"ok": False, "message": "로그인이 필요합니다."}), 401
        if user["status"] != "active":
            return jsonify({"ok": False, "message": "승인된 정식 단원만 이용할 수 있습니다."}), 403
        return func(*args, **kwargs)

    return wrapper


def user_row_to_dict(row):
    if not row:
        return None
    return {
        "id": row["id"],
        "name": row["name"],
        "username": row["username"],
        "email": row["email"],
        "phone": row["phone"],
        "birthDate": row["birth_date"],
        "joinDate": row["join_date"],
        "role": row["role"],
        "status": row["status"],
        "generation": row["generation"],
        "interests": row["interests"],
        "certificates": row["certificates"],
        "availability": row["availability"],
        "isAdmin": role_at_least(row["role"], "admin"),
        "failedLoginCount": row["failed_login_count"],
        "lockedUntil": row["locked_until"],
    }


def ensure_users_migration(cur):
    existing_cols = {
        row["name"] for row in cur.execute("PRAGMA table_info(users)").fetchall()
    }
    migrations = [
        ("role", "TEXT NOT NULL DEFAULT 'member'"),
        ("status", "TEXT NOT NULL DEFAULT 'pending'"),
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
    ]
    for column_name, column_type in migrations:
        if column_name not in existing_cols:
            cur.execute(f"ALTER TABLE users ADD COLUMN {column_name} {column_type}")


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
            cur.execute(f"ALTER TABLE activities ADD COLUMN {column_name} {column_type}")


def ensure_activity_indexes(cur):
    cur.execute("CREATE INDEX IF NOT EXISTS idx_activities_start ON activities(start_at)")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_activities_group ON activities(recurrence_group_id)")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_activities_cancelled ON activities(is_cancelled)")


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
        CREATE TABLE IF NOT EXISTS expenses (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            due_date TEXT NOT NULL,
            settled INTEGER NOT NULL DEFAULT 0,
            created_at TEXT NOT NULL
        )
        """
    )
    conn.commit()

    admin_email = "admin@weave.com"
    admin_defaults = {
        "name": "관리자",
        "username": "admin",
        "email": admin_email,
        "phone": "010-0000-0000",
        "birth_date": "1990.01.01",
        "role": "admin",
        "status": "active",
        "generation": "운영",
        "interests": "운영 총괄",
        "certificates": "CPR",
        "availability": "상시",
    }
    admin_now = now_iso()
    admin_row = cur.execute("SELECT * FROM users WHERE username = ?", (admin_defaults["username"],)).fetchone()
    if not admin_row:
        admin_row = cur.execute("SELECT * FROM users WHERE email = ?", (admin_defaults["email"],)).fetchone()

    if admin_row:
        needs_password_reset = not check_password_hash(admin_row["password_hash"], DEFAULT_ADMIN_PASSWORD)
        password_hash_value = generate_password_hash(DEFAULT_ADMIN_PASSWORD) if needs_password_reset else admin_row["password_hash"]
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
                role, status, approved_at, generation, interests, certificates, availability
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
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
                admin_defaults["status"],
                admin_now,
                admin_defaults["generation"],
                admin_defaults["interests"],
                admin_defaults["certificates"],
                admin_defaults["availability"],
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
    if row["status"] != "locked":
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
            "UPDATE users SET failed_login_count = ?, status = 'locked', locked_until = ? WHERE id = ?",
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
        "email",
        "birthDate",
        "phone",
        "username",
        "password",
    ]
    for field in required_fields:
        if not str(payload.get(field, "")).strip():
            return False, f"{field} 값이 필요합니다."

    password_ok, password_message = validate_password_policy(str(payload.get("password", "")))
    if not password_ok:
        return False, password_message

    return True, ""


@app.after_request
def set_security_headers(response):
    response.headers.setdefault("X-Content-Type-Options", "nosniff")
    response.headers.setdefault("X-Frame-Options", "SAMEORIGIN")
    response.headers.setdefault("Referrer-Policy", "strict-origin-when-cross-origin")
    response.headers.setdefault("Permissions-Policy", "camera=(), microphone=(), geolocation=()")
    response.headers.setdefault("Cache-Control", "no-store")
    return response


@app.route("/")
def root():
    return send_from_directory(BASE_DIR, "index.html")


@app.route("/healthz", methods=["GET"])
def healthz():
    conn = get_db_connection()
    conn.execute("SELECT 1")
    conn.close()
    return jsonify({"ok": True, "status": "healthy"}), 200


@app.route("/api/auth/me", methods=["GET"])
def auth_me():
    row = get_current_user_row()
    if not row:
        return jsonify({"user": None})
    return jsonify({"user": user_row_to_dict(row)})


@app.route("/api/auth/signup", methods=["POST"])
def auth_signup():
    payload = request.get_json(silent=True) or {}
    valid, message = validate_signup_payload(payload)
    if not valid:
        return jsonify({"ok": False, "message": message}), 400

    conn = get_db_connection()
    cur = conn.cursor()
    exists_email = cur.execute("SELECT id FROM users WHERE email = ?", (payload["email"],)).fetchone()
    if exists_email:
        conn.close()
        return jsonify({"ok": False, "message": "이미 등록된 이메일입니다."}), 409

    exists_username = cur.execute("SELECT id FROM users WHERE username = ?", (payload["username"],)).fetchone()
    if exists_username:
        conn.close()
        return jsonify({"ok": False, "message": "이미 사용 중인 아이디입니다."}), 409

    cur.execute(
        """
        INSERT INTO users (
            name, username, email, phone, birth_date, password_hash, join_date,
            role, status, generation, interests, certificates, availability
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            payload["name"].strip(),
            payload["username"].strip(),
            payload["email"].strip(),
            payload["phone"].strip(),
            payload["birthDate"].strip(),
            generate_password_hash(payload["password"]),
            now_iso(),
            "member",
            "pending",
            str(payload.get("generation", "")).strip(),
            to_list_text(payload.get("interests", "")),
            to_list_text(payload.get("certificates", "")),
            str(payload.get("availability", "")).strip(),
        ),
    )
    user_id = cur.lastrowid
    conn.commit()
    row = cur.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()
    conn.close()

    session["user_id"] = user_id
    return jsonify(
        {
            "ok": True,
            "message": "가입 신청이 완료되었습니다. 운영진 승인 후 정식 단원으로 전환됩니다.",
            "user": user_row_to_dict(row),
        }
    )


@app.route("/api/auth/login", methods=["POST"])
def auth_login():
    payload = request.get_json(silent=True) or {}
    username = str(payload.get("username", "")).strip()
    password = str(payload.get("password", ""))

    if not username or not password:
        return jsonify({"ok": False, "message": "아이디와 비밀번호를 입력해주세요."}), 400

    conn = get_db_connection()
    row = conn.execute("SELECT * FROM users WHERE username = ?", (username,)).fetchone()

    if not row:
        conn.close()
        return jsonify({"ok": False, "message": "아이디 또는 비밀번호가 틀렸습니다."}), 401

    try_unlock_expired_user(conn, row)
    row = conn.execute("SELECT * FROM users WHERE id = ?", (row["id"],)).fetchone()

    if row["status"] == "withdrawn":
        conn.close()
        return jsonify({"ok": False, "message": "탈퇴 처리된 계정입니다."}), 403

    if row["status"] == "locked":
        conn.close()
        return jsonify({"ok": False, "message": "로그인 5회 실패로 잠금되었습니다. 휴대폰/이메일 인증으로 해제하세요."}), 423

    if not check_password_hash(row["password_hash"], password):
        locked, _ = increase_login_failure(conn, row)
        conn.close()
        if locked:
            return jsonify({"ok": False, "message": "로그인 5회 실패로 계정이 잠금되었습니다."}), 423
        return jsonify({"ok": False, "message": "아이디 또는 비밀번호가 틀렸습니다."}), 401

    reset_login_failures(conn, row["id"])
    row = conn.execute("SELECT * FROM users WHERE id = ?", (row["id"],)).fetchone()
    conn.close()

    session["user_id"] = row["id"]
    if row["status"] == "pending":
        return jsonify(
            {
                "ok": True,
                "pending": True,
                "message": "가입 승인 대기 중입니다. 승인 후 정식 단원 기능을 사용할 수 있습니다.",
                "user": user_row_to_dict(row),
            }
        )

    return jsonify({"ok": True, "user": user_row_to_dict(row)})


@app.route("/api/auth/logout", methods=["POST"])
def auth_logout():
    session.pop("user_id", None)
    return jsonify({"ok": True})


@app.route("/api/auth/find-username", methods=["POST"])
def auth_find_username():
    payload = request.get_json(silent=True) or {}
    contact = str(payload.get("contact", "")).strip()
    if not contact:
        return jsonify({"ok": False, "message": "연락처 또는 이메일을 입력하세요."}), 400

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
            return jsonify({"ok": True, "username": item["username"]})

    return jsonify({"ok": False, "message": "일치하는 계정을 찾지 못했습니다."}), 404


@app.route("/api/auth/reset-password", methods=["POST"])
def auth_reset_password():
    payload = request.get_json(silent=True) or {}
    username = str(payload.get("username", "")).strip()
    contact = str(payload.get("contact", "")).strip()
    new_password = str(payload.get("newPassword", ""))

    if not username or not contact or not new_password:
        return jsonify({"ok": False, "message": "필수 값을 입력해주세요."}), 400

    valid_password, password_message = validate_password_policy(new_password)
    if not valid_password:
        return jsonify({"ok": False, "message": password_message}), 400

    normalized_contact = contact.replace("-", "").lower()

    conn = get_db_connection()
    row = conn.execute(
        "SELECT * FROM users WHERE username = ?",
        (username,),
    ).fetchone()

    if not row:
        conn.close()
        return jsonify({"ok": False, "message": "일치하는 계정을 찾지 못했습니다."}), 404

    email_key = (row["email"] or "").replace("-", "").lower()
    phone_key = (row["phone"] or "").replace("-", "").lower()
    if normalized_contact not in (email_key, phone_key):
        conn.close()
        return jsonify({"ok": False, "message": "일치하는 계정을 찾지 못했습니다."}), 404

    conn.execute(
        "UPDATE users SET password_hash = ?, failed_login_count = 0, locked_until = NULL, status = CASE WHEN status='locked' THEN COALESCE(CASE WHEN approved_at IS NOT NULL THEN 'active' END, 'pending') ELSE status END WHERE id = ?",
        (generate_password_hash(new_password), row["id"]),
    )
    conn.commit()
    conn.close()
    return jsonify({"ok": True, "message": "비밀번호가 재설정되었습니다."})


@app.route("/api/auth/unlock-account", methods=["POST"])
def auth_unlock_account():
    payload = request.get_json(silent=True) or {}
    username = str(payload.get("username", "")).strip()
    contact = normalize_contact(payload.get("contact", ""))

    if not username or not contact:
        return jsonify({"ok": False, "message": "아이디와 휴대폰/이메일이 필요합니다."}), 400

    conn = get_db_connection()
    row = conn.execute("SELECT * FROM users WHERE username = ?", (username,)).fetchone()
    if not row:
        conn.close()
        return jsonify({"ok": False, "message": "일치하는 계정을 찾지 못했습니다."}), 404

    if contact not in (normalize_contact(row["email"]), normalize_contact(row["phone"])):
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


@app.route("/api/auth/withdraw", methods=["POST"])
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
        return jsonify({"ok": False, "message": "로그인이 필요합니다."}), 401

    if contact not in (normalize_contact(me["email"]), normalize_contact(me["phone"])):
        conn.close()
        return jsonify({"ok": False, "message": "연락처/이메일 인증이 필요합니다."}), 403

    if not check_password_hash(me["password_hash"], password):
        conn.close()
        return jsonify({"ok": False, "message": "비밀번호가 올바르지 않습니다."}), 403

    retention_days = int(os.environ.get("WEAVE_RETENTION_DAYS", "30"))
    retention_until = (datetime.now() + timedelta(days=retention_days)).isoformat()
    deleted_at = now_iso()
    anonymized = f"withdrawn-{me['id']}-{int(datetime.now().timestamp())}"

    conn.execute(
        """
        UPDATE users
        SET status = 'withdrawn',
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
    conn.commit()
    conn.close()
    session.pop("user_id", None)
    return jsonify({"ok": True, "message": f"탈퇴 완료. 데이터는 {retention_days}일 보관 후 파기됩니다."})


@app.route("/api/admin/pending-users", methods=["GET"])
@role_required("staff")
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


@app.route("/api/admin/users/<int:user_id>/approve", methods=["POST"])
@role_required("staff")
def admin_approve_user(user_id):
    payload = request.get_json(silent=True) or {}
    role = str(payload.get("role", "member")).strip().lower()
    if role not in ("member", "staff", "admin"):
        return jsonify({"ok": False, "message": "유효하지 않은 역할입니다."}), 400

    conn = get_db_connection()
    target = conn.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()
    if not target:
        conn.close()
        return jsonify({"ok": False, "message": "대상을 찾을 수 없습니다."}), 404

    me = get_current_user_row(conn)
    if not me:
        conn.close()
        return jsonify({"ok": False, "message": "로그인이 필요합니다."}), 401
    if role == "admin" and not role_at_least(me["role"], "admin"):
        conn.close()
        return jsonify({"ok": False, "message": "관리자 승격 권한이 없습니다."}), 403

    conn.execute(
        "UPDATE users SET status = 'active', role = ?, approved_at = ?, approved_by = ? WHERE id = ?",
        (role, now_iso(), me["id"], user_id),
    )
    conn.commit()
    row = conn.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()
    conn.close()
    return jsonify({"ok": True, "message": "가입이 승인되었습니다.", "user": user_row_to_dict(row)})


@app.route("/api/admin/users/<int:user_id>/reject", methods=["POST"])
@role_required("staff")
def admin_reject_user(user_id):
    conn = get_db_connection()
    target = conn.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()
    if not target:
        conn.close()
        return jsonify({"ok": False, "message": "대상을 찾을 수 없습니다."}), 404

    conn.execute("UPDATE users SET status = 'withdrawn', deleted_at = ? WHERE id = ?", (now_iso(), user_id))
    conn.commit()
    conn.close()
    return jsonify({"ok": True, "message": "가입 신청이 반려되었습니다."})


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


@app.route("/api/activities", methods=["GET"])
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


@app.route("/api/activities", methods=["POST"])
@role_required("staff")
def create_activity():
    payload = request.get_json(silent=True) or {}
    required = ["title", "startAt", "endAt"]
    for field in required:
        if not str(payload.get(field, "")).strip():
            return jsonify({"ok": False, "message": f"{field} 값이 필요합니다."}), 400

    title = str(payload.get("title", "")).strip()
    if len(title) > 120:
        return jsonify({"ok": False, "message": "활동 제목은 120자 이하여야 합니다."}), 400

    start_at = str(payload.get("startAt", "")).strip()
    end_at = str(payload.get("endAt", "")).strip()
    start_dt = parse_iso_datetime(start_at)
    end_dt = parse_iso_datetime(end_at)
    if not start_dt or not end_dt:
        return jsonify({"ok": False, "message": "시작/종료 시간 형식이 올바르지 않습니다."}), 400
    if end_dt <= start_dt:
        return jsonify({"ok": False, "message": "종료 시간은 시작 시간보다 늦어야 합니다."}), 400

    recruitment_limit = int(payload.get("recruitmentLimit", 0) or 0)
    if recruitment_limit < 0 or recruitment_limit > 1000:
        return jsonify({"ok": False, "message": "모집 인원은 0~1000 범위여야 합니다."}), 400

    recurrence_group_id = str(payload.get("recurrenceGroupId", "")).strip()
    if recurrence_group_id and (len(recurrence_group_id) > 64 or not re.fullmatch(r"[A-Za-z0-9_-]+", recurrence_group_id)):
        return jsonify({"ok": False, "message": "반복 그룹 ID 형식이 올바르지 않습니다."}), 400

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
    row = conn.execute("SELECT * FROM activities WHERE id = ?", (activity_id,)).fetchone()
    conn.close()
    return jsonify({"ok": True, "activity": serialize_activity_row(row)})


@app.route("/api/activities/<int:activity_id>/apply", methods=["POST"])
@active_member_required
def apply_activity(activity_id):
    conn = get_db_connection()
    me = get_current_user_row(conn)
    if not me:
        conn.close()
        return jsonify({"ok": False, "message": "로그인이 필요합니다."}), 401
    activity = conn.execute("SELECT * FROM activities WHERE id = ?", (activity_id,)).fetchone()
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
    next_status = "confirmed" if limit_count <= 0 or confirmed_count < limit_count else "waiting"

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


@app.route("/api/activities/recurrence/<group_id>/cancel", methods=["POST"])
@role_required("staff")
def cancel_recurrence_group(group_id):
    group_id = str(group_id or "").strip()
    if not group_id or len(group_id) > 64 or not re.fullmatch(r"[A-Za-z0-9_-]+", group_id):
        return jsonify({"ok": False, "message": "유효하지 않은 반복 그룹 ID입니다."}), 400

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
    return jsonify({"ok": True, "message": "반복 그룹 일정이 일괄 취소되었습니다.", "count": len(activity_ids)})


@app.route("/api/activities/recurrence/<group_id>/impact", methods=["GET"])
@role_required("staff")
def recurrence_group_impact(group_id):
    group_id = str(group_id or "").strip()
    if not group_id or len(group_id) > 64 or not re.fullmatch(r"[A-Za-z0-9_-]+", group_id):
        return jsonify({"ok": False, "message": "유효하지 않은 반복 그룹 ID입니다."}), 400

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


@app.route("/api/activities/<int:activity_id>/cancel", methods=["POST"])
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


@app.route("/api/activities/<int:activity_id>/attendance/qr-token", methods=["POST"])
@role_required("staff")
def create_attendance_qr_token(activity_id):
    conn = get_db_connection()
    me = get_current_user_row(conn)
    if not me:
        conn.close()
        return jsonify({"ok": False, "message": "로그인이 필요합니다."}), 401
    activity = conn.execute("SELECT id FROM activities WHERE id = ?", (activity_id,)).fetchone()
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


@app.route("/api/activities/<int:activity_id>/attendance/qr-check", methods=["POST"])
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

    activity = conn.execute("SELECT * FROM activities WHERE id = ?", (activity_id,)).fetchone()
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


@app.route("/api/activities/<int:activity_id>/attendance/bulk", methods=["POST"])
@role_required("staff")
def bulk_attendance(activity_id):
    payload = request.get_json(silent=True) or {}
    entries = payload.get("entries", [])
    if not isinstance(entries, list) or not entries:
        return jsonify({"ok": False, "message": "entries 배열이 필요합니다."}), 400

    conn = get_db_connection()
    activity = conn.execute("SELECT * FROM activities WHERE id = ?", (activity_id,)).fetchone()
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
            (final_status, status, final_hours, final_points, penalty, now_iso(), app_row["id"]),
        )
        updated += 1

    conn.commit()
    conn.close()
    return jsonify({"ok": True, "updated": updated})


@app.route("/api/me/history", methods=["GET"])
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
    total_points = sum(int(row["points"] or 0) for row in rows) - sum(int(row["penalty_points"] or 0) for row in rows)
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


@app.route("/api/me/certificate.csv", methods=["GET"])
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
    writer.writerow(["이름", "아이디", "활동명", "시작", "종료", "장소", "출석상태", "봉사시간"])
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
    response.headers["Content-Disposition"] = "attachment; filename=my_activity_certificate.csv"
    return response


def make_thumbnail_like(url):
    if not url:
        return ""
    return url


@app.route("/api/gallery/albums", methods=["GET"])
def list_gallery_albums():
    conn = get_db_connection()
    rows = conn.execute(
        "SELECT * FROM gallery_albums ORDER BY id DESC"
    ).fetchall()
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


@app.route("/api/gallery/albums", methods=["POST"])
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
        (title, payload.get("activityId"), visibility, 1 if portrait_consent else 0, me["id"], now_iso()),
    )
    album_id = cur.lastrowid
    conn.commit()
    conn.close()
    return jsonify({"ok": True, "albumId": album_id})


@app.route("/api/gallery/albums/<int:album_id>/photos", methods=["POST"])
@role_required("staff")
def add_gallery_photos(album_id):
    payload = request.get_json(silent=True) or {}
    photos = payload.get("photos", [])
    if not isinstance(photos, list) or not photos:
        return jsonify({"ok": False, "message": "photos 배열이 필요합니다."}), 400

    conn = get_db_connection()
    album = conn.execute("SELECT id FROM gallery_albums WHERE id = ?", (album_id,)).fetchone()
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


@app.route("/api/press-kit", methods=["GET"])
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


@app.route("/api/rules/versions", methods=["GET"])
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


@app.route("/api/rules/versions", methods=["POST"])
@role_required("staff")
def create_rules_version():
    payload = request.get_json(silent=True) or {}
    version = str(payload.get("version", "")).strip()
    effective_date = str(payload.get("effectiveDate", "")).strip()
    summary = str(payload.get("summary", "")).strip()
    content = str(payload.get("content", "")).strip()

    if not version or not effective_date or not summary:
        return jsonify({"ok": False, "message": "version/effectiveDate/summary는 필수입니다."}), 400

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

    impact_metric = f"활동 {total_activities}건, 누적 {round(float(total_hours or 0), 1)}시간"
    return {
        "year": year,
        "totalActivities": int(total_activities or 0),
        "totalHours": round(float(total_hours or 0), 2),
        "totalParticipants": int(total_participants or 0),
        "impact": impact_metric,
    }


@app.route("/api/reports/annual/<int:year>", methods=["GET"])
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


@app.route("/api/admin/dashboard", methods=["GET"])
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


@app.route("/api/admin/export/participants.csv", methods=["GET"])
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
        [[row["id"], row["name"], row["username"], row["email"], row["phone"], row["role"], row["status"], row["generation"]] for row in rows],
    )


@app.route("/api/admin/export/attendance.csv", methods=["GET"])
@role_required("staff")
def export_attendance_csv():
    conn = get_db_connection()
    rows = conn.execute(
        """
        SELECT a.title, a.start_at, u.name, u.username, ap.status, ap.attendance_status, ap.hours
        FROM activity_applications ap
        JOIN activities a ON a.id = ap.activity_id
        JOIN users u ON u.id = ap.user_id
        ORDER BY a.start_at DESC, u.username ASC
        """
    ).fetchall()
    conn.close()
    return csv_response(
        "attendance.csv",
        ["activity", "start_at", "name", "username", "apply_status", "attendance_status", "hours"],
        [[row["title"], row["start_at"], row["name"], row["username"], row["status"], row["attendance_status"], row["hours"]] for row in rows],
    )


@app.route("/api/admin/export/hours.csv", methods=["GET"])
@role_required("staff")
def export_hours_csv():
    conn = get_db_connection()
    rows = conn.execute(
        """
        SELECT u.name, u.username,
               COALESCE(SUM(ap.hours),0) AS total_hours,
               COALESCE(SUM(ap.points),0) AS total_points,
               COALESCE(SUM(ap.penalty_points),0) AS penalty_points
        FROM users u
        LEFT JOIN activity_applications ap ON ap.user_id = u.id
        GROUP BY u.id, u.name, u.username
        ORDER BY total_hours DESC
        """
    ).fetchall()
    conn.close()
    return csv_response(
        "hours_summary.csv",
        ["name", "username", "total_hours", "total_points", "penalty_points"],
        [[row["name"], row["username"], row["total_hours"], row["total_points"], row["penalty_points"]] for row in rows],
    )


@app.route("/api/templates", methods=["GET"])
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


@app.route("/api/templates/generate", methods=["POST"])
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


@app.route("/<path:path>")
def static_proxy(path):
    return send_from_directory(BASE_DIR, path)


init_db()


if __name__ == "__main__":
    app.run(host="127.0.0.1", port=5000, debug=False, threaded=True)
