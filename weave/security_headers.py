import json
import time

from flask import current_app

from weave.core import (
    APP_METRICS,
    g,
    logger,
    now_iso,
    request,
    session,
    touch_user_activity,
)


def _build_csp(level):
    csp_level = str(level or "compat").strip().lower()
    if csp_level == "strict":
        return (
            "default-src 'self'; "
            "img-src 'self' data: https://images.unsplash.com; "
            "script-src 'self' https://cdn.jsdelivr.net https://cdnjs.cloudflare.com; "
            "style-src 'self' https://cdn.jsdelivr.net https://cdnjs.cloudflare.com; "
            "font-src 'self' data: https://cdnjs.cloudflare.com; "
            "object-src 'none'"
        )
    return (
        "default-src 'self'; "
        "img-src 'self' data: https://images.unsplash.com; "
        "script-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net https://cdnjs.cloudflare.com; "
        "style-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net https://cdnjs.cloudflare.com; "
        "font-src 'self' data: https://cdnjs.cloudflare.com; "
        "object-src 'none'"
    )


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
    csp_value = _build_csp(current_app.config.get("WEAVE_CSP_LEVEL", "compat"))
    if current_app.config.get("WEAVE_CSP_REPORT_ONLY", True):
        response.headers.setdefault("Content-Security-Policy", _build_csp("compat"))
        response.headers.setdefault("Content-Security-Policy-Report-Only", csp_value)
    else:
        response.headers.setdefault("Content-Security-Policy", csp_value)
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
