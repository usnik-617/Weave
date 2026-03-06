from weave.core import request, session, uuid
from weave.responses import error_response

CSRF_EXEMPT_PATHS = {"/healthz", "/metrics"}


def ensure_csrf_token():
    token = session.get("csrf_token")
    if not token:
        token = uuid.uuid4().hex
        session["csrf_token"] = token
    return token


def validate_csrf_if_needed():
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
