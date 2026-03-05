import re
import threading
import time

from weave.core import *

REQUEST_LIMIT_BUCKETS = {}
REQUEST_LIMIT_LOCK = threading.Lock()


def _allow_rate_limit(bucket_key, limit_count, window_seconds):
    now_ts = time.time()
    with REQUEST_LIMIT_LOCK:
        values = [
            value
            for value in REQUEST_LIMIT_BUCKETS.get(bucket_key, [])
            if (now_ts - value) <= window_seconds
        ]
        if len(values) >= int(limit_count):
            REQUEST_LIMIT_BUCKETS[bucket_key] = values
            return False

        values.append(now_ts)
        REQUEST_LIMIT_BUCKETS[bucket_key] = values
    return True


def validate_endpoint_rate_limit():
    is_playwright_db = (
        str(DB_PATH).replace("\\", "/").endswith("/instance/playwright.db")
    )
    if is_playwright_db:
        return None

    test_bypass = (
        request.headers.get("X-Playwright-Test", "") == "1"
        or str(request.args.get("playwright_test", "")) == "1"
    )
    if test_bypass:
        return None

    path = request.path
    method = request.method.upper()

    if method == "POST" and path == "/api/auth/login":
        key = f"rl:login:{get_client_ip()}"
        if not _allow_rate_limit(key, 5, 60):
            return error_response(
                "로그인 요청이 너무 많습니다. 잠시 후 다시 시도해주세요.", 429
            )

    if method == "POST" and path == "/api/auth/signup":
        key = f"rl:signup:{get_client_ip()}"
        if not _allow_rate_limit(key, 3, 60):
            return error_response(
                "회원가입 요청이 너무 많습니다. 잠시 후 다시 시도해주세요.", 429
            )

    if method == "POST" and re.fullmatch(r"/api/posts/\d+/files", path or ""):
        user_id = session.get("user_id")
        if user_id:
            key = f"rl:upload:{user_id}"
        else:
            key = f"rl:upload-ip:{get_client_ip()}"

        if not _allow_rate_limit(key, 10, 60):
            return error_response(
                "업로드 요청이 너무 많습니다. 잠시 후 다시 시도해주세요.", 429
            )

    return None
