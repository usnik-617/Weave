import os

from flask import abort

from weave.core import STATIC_DIR, send_from_directory


def root():
    return send_from_directory(STATIC_DIR, "index.html")


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
        abort(404)
    if is_sensitive_path(normalized):
        abort(403)

    candidate = os.path.join(STATIC_DIR, normalized)
    if os.path.isfile(candidate):
        return send_from_directory(STATIC_DIR, normalized)

    if normalized.startswith("static/"):
        alt = normalized[len("static/") :]
        alt_candidate = os.path.join(STATIC_DIR, alt)
        if os.path.isfile(alt_candidate):
            return send_from_directory(STATIC_DIR, alt)

    return send_from_directory(STATIC_DIR, "index.html")
