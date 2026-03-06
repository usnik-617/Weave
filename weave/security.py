import time

from weave.core import (
    STATIC_DIR,
    g,
    json,
    logger,
    request,
    send_from_directory,
    session,
    uuid,
)
from weave.responses import error_response, is_api_request
from weave.time_utils import now_iso
from weave.csrf import ensure_csrf_token
from weave.csrf import validate_csrf_if_needed
from weave.rate_limit import validate_endpoint_rate_limit
from weave.security_headers import set_security_headers


def _begin_request_context():
    g.request_started = time.time()
    g.request_id = uuid.uuid4().hex

    ensure_csrf_token()

    limited = validate_endpoint_rate_limit()
    if limited:
        return limited

    csrf_error = validate_csrf_if_needed()
    if csrf_error:
        return csrf_error


def _handle_400(error):
    if is_api_request():
        return error_response("Bad Request", 400)
    return error


def _handle_401(error):
    if is_api_request():
        return error_response("Unauthorized", 401)
    return error


def _handle_403(error):
    if is_api_request():
        return error_response("Forbidden", 403)
    return error


def _handle_404(error):
    if is_api_request():
        return error_response("Not Found", 404)
    return send_from_directory(STATIC_DIR, "index.html")


def _handle_500(error):
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


def register_hooks(app):
    app.before_request(_begin_request_context)
    app.after_request(set_security_headers)
    app.register_error_handler(400, _handle_400)
    app.register_error_handler(401, _handle_401)
    app.register_error_handler(403, _handle_403)
    app.register_error_handler(404, _handle_404)
    app.register_error_handler(500, _handle_500)
