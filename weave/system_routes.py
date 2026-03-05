import time

from weave.core import (
    STATIC_DIR,
    error_response,
    g,
    is_api_request,
    json,
    logger,
    now_iso,
    request,
    send_from_directory,
    session,
    uuid,
)
from weave.csrf import ensure_csrf_token as _ensure_csrf_token
from weave.csrf import validate_csrf_if_needed as _validate_csrf_if_needed
from weave.health import healthz, metrics
from weave.rate_limit import (
    validate_endpoint_rate_limit as _validate_endpoint_rate_limit,
)
from weave.security_headers import set_security_headers


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
