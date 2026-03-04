from weave.core import *


CSRF_EXEMPT_PATHS = {"/healthz", "/metrics"}
REQUEST_LIMIT_BUCKETS = {}
REQUEST_LIMIT_LOCK = threading.Lock()


def _allow_rate_limit(bucket_key, limit_count, window_seconds):
    now_ts = time.time()
    with REQUEST_LIMIT_LOCK:
        values = [v for v in REQUEST_LIMIT_BUCKETS.get(bucket_key, []) if (now_ts - v) <= window_seconds]
        if len(values) >= int(limit_count):
            REQUEST_LIMIT_BUCKETS[bucket_key] = values
            return False
        values.append(now_ts)
        REQUEST_LIMIT_BUCKETS[bucket_key] = values
    return True


def _ensure_csrf_token():
    token = session.get("csrf_token")
    if not token:
        token = uuid.uuid4().hex
        session["csrf_token"] = token
    return token


def _validate_csrf_if_needed():
    if request.method not in ("POST", "PUT", "PATCH", "DELETE"):
        return None
    if request.path in CSRF_EXEMPT_PATHS:
        return None
    token = session.get("csrf_token")
    supplied = request.headers.get("X-CSRF-Token", "")
    if not supplied and request.form:
        supplied = str(request.form.get("csrf_token", ""))
    if not token or not supplied or token != supplied:
        return error_response("CSRF token mismatch", 403)
    return None


def _validate_endpoint_rate_limit():
    path = request.path
    method = request.method.upper()
    if method == "POST" and path == "/api/auth/login":
        key = f"rl:login:{get_client_ip()}"
        if not _allow_rate_limit(key, 5, 60):
            return error_response("로그인 요청이 너무 많습니다. 잠시 후 다시 시도해주세요.", 429)
    if method == "POST" and path == "/api/auth/signup":
        key = f"rl:signup:{get_client_ip()}"
        if not _allow_rate_limit(key, 3, 60):
            return error_response("회원가입 요청이 너무 많습니다. 잠시 후 다시 시도해주세요.", 429)
    if method == "POST" and re.fullmatch(r"/api/posts/\d+/files", path or ""):
        user_id = session.get("user_id")
        if user_id:
            key = f"rl:upload:{user_id}"
        else:
            key = f"rl:upload-ip:{get_client_ip()}"
        if not _allow_rate_limit(key, 10, 60):
            return error_response("업로드 요청이 너무 많습니다. 잠시 후 다시 시도해주세요.", 429)
    return None


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
        total_posts = int(conn.execute("SELECT COUNT(*) AS c FROM posts").fetchone()["c"] or 0)
        total_comments = int(conn.execute("SELECT COUNT(*) AS c FROM comments").fetchone()["c"] or 0)
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


def begin_request_context():
    g.request_started = time.time()
    g.request_id = uuid.uuid4().hex
    _ensure_csrf_token()
    limited = _validate_endpoint_rate_limit()
    if limited:
        return limited
    csrf_error = _validate_csrf_if_needed()
    if csrf_error:
        return csrf_error


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
        "Content-Security-Policy",
        "default-src 'self'; img-src 'self' data:; script-src 'self'; style-src 'self' 'unsafe-inline'; object-src 'none'",
    )
    response.headers.setdefault("Permissions-Policy", "camera=(), microphone=(), geolocation=()")
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


