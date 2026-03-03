import os
import sqlite3
from datetime import datetime, timedelta

from flask import Flask, jsonify, request, send_from_directory, session
from werkzeug.middleware.proxy_fix import ProxyFix
from werkzeug.security import check_password_hash, generate_password_hash


BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, "weave.db")
WEAVE_ENV = os.environ.get("WEAVE_ENV", "development").lower()

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
        "isAdmin": bool(row["is_admin"]),
    }


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
            is_admin INTEGER NOT NULL DEFAULT 0,
            join_date TEXT NOT NULL
        )
        """
    )
    conn.commit()

    admin_email = "admin@weave.com"
    cur.execute(
        """
        INSERT OR IGNORE INTO users (name, username, email, phone, birth_date, password_hash, is_admin, join_date)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            "관리자",
            "admin",
            admin_email,
            "010-0000-0000",
            "1990.01.01",
            generate_password_hash("Weave!2026"),
            1,
            datetime.now().isoformat(),
        ),
    )
    conn.commit()

    conn.close()


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
    user_id = session.get("user_id")
    if not user_id:
        return jsonify({"user": None})

    conn = get_db_connection()
    row = conn.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()
    conn.close()
    if not row:
        session.pop("user_id", None)
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
        INSERT INTO users (name, username, email, phone, birth_date, password_hash, is_admin, join_date)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            payload["name"].strip(),
            payload["username"].strip(),
            payload["email"].strip(),
            payload["phone"].strip(),
            payload["birthDate"].strip(),
            generate_password_hash(payload["password"]),
            0,
            datetime.now().isoformat(),
        ),
    )
    user_id = cur.lastrowid
    conn.commit()
    row = cur.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()
    conn.close()

    session["user_id"] = user_id
    return jsonify({"ok": True, "user": user_row_to_dict(row)})


@app.route("/api/auth/login", methods=["POST"])
def auth_login():
    payload = request.get_json(silent=True) or {}
    username = str(payload.get("username", "")).strip()
    password = str(payload.get("password", ""))

    if not username or not password:
        return jsonify({"ok": False, "message": "아이디와 비밀번호를 입력해주세요."}), 400

    conn = get_db_connection()
    row = conn.execute("SELECT * FROM users WHERE username = ?", (username,)).fetchone()
    conn.close()

    if not row or not check_password_hash(row["password_hash"], password):
        return jsonify({"ok": False, "message": "아이디 또는 비밀번호가 틀렸습니다."}), 401

    session["user_id"] = row["id"]
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
    row = conn.execute(
        "SELECT username, email, phone FROM users"
    ).fetchall()
    conn.close()

    for item in row:
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
        "UPDATE users SET password_hash = ? WHERE id = ?",
        (generate_password_hash(new_password), row["id"]),
    )
    conn.commit()
    conn.close()
    return jsonify({"ok": True, "message": "비밀번호가 재설정되었습니다."})


@app.route("/<path:path>")
def static_proxy(path):
    return send_from_directory(BASE_DIR, path)


init_db()


if __name__ == "__main__":
    app.run(host="127.0.0.1", port=5000, debug=False, threaded=True)
