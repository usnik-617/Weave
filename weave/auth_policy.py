from __future__ import annotations


def blocked_until_text(blocked_until, now_iso_func):
    return blocked_until.isoformat() if blocked_until else now_iso_func()


def should_bypass_login_rate_limit(request_obj, db_path):
    is_playwright_db = str(db_path).replace("\\", "/").endswith("/instance/playwright.db")
    test_bypass = (
        request_obj.headers.get("X-Playwright-Test", "") == "1"
        or str(request_obj.args.get("playwright_test", "")) == "1"
    )
    return bool(test_bypass or is_playwright_db)


def validate_login_payload(username, password):
    return bool(str(username or "").strip() and str(password or ""))


def signup_rate_limit_hint(payload):
    username = str((payload or {}).get("username", "")).strip().lower()
    email = str((payload or {}).get("email", "")).strip().lower()
    if username and email:
        return f"{username}|{email}"
    return username or email
