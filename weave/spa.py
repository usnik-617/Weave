import os

from flask import abort, current_app

from weave.core import STATIC_DIR, send_from_directory


def root():
    response = send_from_directory(STATIC_DIR, "index.html")
    response.headers["Cache-Control"] = current_app.config.get(
        "SPA_HTML_CACHE_CONTROL", "no-store"
    )
    return response


def is_sensitive_path(path):
    lowered = str(path or "").replace("\\", "/").lower().strip("/")
    sensitive_suffixes = current_app.config.get(
        "SPA_SENSITIVE_SUFFIXES", (".db", ".env", ".py", ".sqlite", ".sqlite3")
    )
    segments = [segment for segment in lowered.split("/") if segment]
    if any(segment in {".", ".."} for segment in segments):
        return True
    if any(segment.startswith(".") for segment in segments):
        return True
    if any(segment in {"instance", "__pycache__"} for segment in segments):
        return True
    return lowered.endswith(sensitive_suffixes)


def _normalize_public_path(path):
    text = str(path or "").strip().replace("\\", "/").lstrip("/")
    normalized = os.path.normpath(text).replace("\\", "/")
    return "" if normalized in {"", "."} else normalized.lstrip("/")


def _is_static_file(path):
    static_root = os.path.realpath(STATIC_DIR)
    candidate = os.path.realpath(os.path.join(static_root, path))
    try:
        in_static_root = os.path.commonpath([static_root, candidate]) == static_root
    except ValueError:
        return False
    return in_static_root and os.path.isfile(candidate)


def _serve_static_asset(path):
    response = send_from_directory(STATIC_DIR, path)
    response.headers["Cache-Control"] = current_app.config.get(
        "SPA_ASSET_CACHE_CONTROL", "public, max-age=3600"
    )
    return response


def static_proxy(path):
    normalized = _normalize_public_path(path)
    if normalized.startswith("api/"):
        abort(404)
    if is_sensitive_path(normalized):
        abort(403)

    if normalized and _is_static_file(normalized):
        return _serve_static_asset(normalized)

    # Optional compatibility alias for older frontend links that still use /static/*.
    allow_static_alias = bool(current_app.config.get("SPA_ALLOW_STATIC_ALIAS", True))
    if allow_static_alias and normalized.startswith("static/"):
        alt = normalized[len("static/") :]
        if alt and _is_static_file(alt):
            return _serve_static_asset(alt)

    response = send_from_directory(STATIC_DIR, "index.html")
    response.headers["Cache-Control"] = current_app.config.get(
        "SPA_HTML_CACHE_CONTROL", "no-store"
    )
    return response
