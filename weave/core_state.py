from __future__ import annotations


def parse_rate_limit_bucket(ip):
    from weave import core

    now = core.datetime.now()
    bucket = core.LOGIN_ATTEMPTS.get(ip, {"fails": [], "blocked_until": None})
    bucket["fails"] = [
        ts for ts in bucket.get("fails", []) if (now - ts) <= core.LOGIN_RATE_LIMIT_WINDOW
    ]
    blocked_until = bucket.get("blocked_until")
    if blocked_until and blocked_until <= now:
        bucket["blocked_until"] = None
    core.LOGIN_ATTEMPTS[ip] = bucket
    return bucket


def get_rate_limit_key(action, username_hint=""):
    from weave import core

    return f"{action}:{core.get_client_ip()}:{str(username_hint or '').strip().lower()}"


def is_rate_limited(action, username_hint=""):
    from weave import core

    if core.WEAVE_ENV != "production":
        return False, None
    key = get_rate_limit_key(action, username_hint)
    blocked, blocked_until = is_ip_blocked(key)
    return blocked, blocked_until


def mark_rate_limit_failure(action, username_hint=""):
    from weave import core

    if core.WEAVE_ENV != "production":
        return None
    key = get_rate_limit_key(action, username_hint)
    return register_login_failure(key)


def clear_rate_limit(action, username_hint=""):
    from weave import core

    if core.WEAVE_ENV != "production":
        return
    key = get_rate_limit_key(action, username_hint)
    reset_login_failures_by_ip(key)


def is_ip_blocked(ip):
    from weave import core

    bucket = parse_rate_limit_bucket(ip)
    blocked_until = bucket.get("blocked_until")
    if blocked_until and blocked_until > core.datetime.now():
        return True, blocked_until
    return False, None


def register_login_failure(ip):
    from weave import core

    bucket = parse_rate_limit_bucket(ip)
    now = core.datetime.now()
    bucket["fails"].append(now)
    if len(bucket["fails"]) >= core.LOGIN_RATE_LIMIT_COUNT:
        bucket["blocked_until"] = now + core.LOGIN_RATE_LIMIT_BLOCK
        bucket["fails"] = []
    core.LOGIN_ATTEMPTS[ip] = bucket
    return bucket.get("blocked_until")


def reset_login_failures_by_ip(ip):
    from weave import core

    if ip in core.LOGIN_ATTEMPTS:
        core.LOGIN_ATTEMPTS.pop(ip, None)


def clear_all_rate_limit_state():
    from weave import core
    from weave import rate_limit

    core.LOGIN_ATTEMPTS.clear()
    with rate_limit.REQUEST_LIMIT_LOCK:
        rate_limit.REQUEST_LIMIT_BUCKETS.clear()


def _cache_now():
    from weave import core

    return core.time.time()


def get_cache(key):
    from weave import core

    with core.APP_CACHE_LOCK:
        cached = core.APP_CACHE.get(key)
        if not cached:
            return None
        if cached["expires_at"] <= _cache_now():
            core.APP_CACHE.pop(key, None)
            return None
        return cached["value"]


def set_cache(key, value, ttl_seconds):
    from weave import core

    with core.APP_CACHE_LOCK:
        core.APP_CACHE[key] = {
            "value": value,
            "expires_at": _cache_now() + int(ttl_seconds),
        }


def invalidate_cache(prefix):
    from weave import core

    with core.APP_CACHE_LOCK:
        keys = [key for key in core.APP_CACHE.keys() if str(key).startswith(str(prefix))]
        for key in keys:
            core.APP_CACHE.pop(key, None)
