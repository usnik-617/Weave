import os
import logging
from datetime import timedelta


logger = logging.getLogger("weave.config")


def _parse_spa_sensitive_suffixes(raw):
    values = [item.strip().lower() for item in str(raw or "").split(",") if item.strip()]
    sanitized = []
    for value in values:
        if not value.startswith("."):
            logger.warning(
                "config_warning category=spa_sensitive_suffix reason=missing_dot value=%s",
                value,
            )
            continue
        if "/" in value or "\\" in value:
            logger.warning(
                "config_warning category=spa_sensitive_suffix reason=contains_path_separator value=%s",
                value,
            )
            continue
        sanitized.append(value)
    if not sanitized:
        return (".db", ".env", ".py", ".sqlite", ".sqlite3")
    return tuple(dict.fromkeys(sanitized))


def _sanitize_cache_control(raw, fallback):
    value = str(raw or "").strip()
    if not value:
        return fallback
    if "\n" in value or "\r" in value:
        logger.warning(
            "config_warning category=cache_control reason=contains_newline value=%r",
            value,
        )
        return fallback
    return value


def _is_truthy(raw, fallback=False):
    text = str(raw).strip().lower() if raw is not None else ""
    if not text:
        return bool(fallback)
    return text in {"1", "true", "yes", "on"}


def load_config(app):
    weave_env = os.environ.get("WEAVE_ENV", "development").lower()
    max_upload_mb = int(os.environ.get("MAX_UPLOAD_MB", "25"))
    app.config["SECRET_KEY"] = os.environ.get(
        "WEAVE_SECRET_KEY", "weave-local-dev-secret-key"
    )
    app.config["MAX_CONTENT_LENGTH"] = max_upload_mb * 1024 * 1024
    app.config["SESSION_COOKIE_HTTPONLY"] = True
    app.config["SESSION_COOKIE_SAMESITE"] = os.environ.get(
        "WEAVE_SESSION_SAMESITE", "Lax"
    )
    app.config["SESSION_COOKIE_SECURE"] = weave_env == "production"
    app.config["PERMANENT_SESSION_LIFETIME"] = timedelta(
        seconds=int(os.environ.get("WEAVE_SESSION_LIFETIME_SEC", 60 * 60 * 24 * 7))
    )
    app.config["SPA_SENSITIVE_SUFFIXES"] = _parse_spa_sensitive_suffixes(
        os.environ.get("WEAVE_SPA_SENSITIVE_SUFFIXES", ".db,.env,.py,.sqlite,.sqlite3")
    )
    app.config["SPA_ASSET_CACHE_CONTROL"] = _sanitize_cache_control(
        os.environ.get("WEAVE_SPA_ASSET_CACHE_CONTROL", "public, max-age=3600"),
        "public, max-age=3600",
    )
    app.config["SPA_SW_CACHE_CONTROL"] = _sanitize_cache_control(
        os.environ.get(
            "WEAVE_SPA_SW_CACHE_CONTROL", "no-cache, no-store, must-revalidate"
        ),
        "no-cache, no-store, must-revalidate",
    )
    app.config["SPA_HTML_CACHE_CONTROL"] = _sanitize_cache_control(
        os.environ.get("WEAVE_SPA_HTML_CACHE_CONTROL", "no-store"),
        "no-store",
    )
    app.config["SPA_ALLOW_STATIC_ALIAS"] = _is_truthy(
        os.environ.get("WEAVE_SPA_ALLOW_STATIC_ALIAS", "false"),
        fallback=False,
    )
    app.config["WEAVE_DEBUG_CLIENT_CACHE_PANEL"] = _is_truthy(
        os.environ.get("WEAVE_DEBUG_CLIENT_CACHE_PANEL", "false"),
        fallback=False,
    )
    app.config["WEAVE_CSP_LEVEL"] = str(
        os.environ.get("WEAVE_CSP_LEVEL", "compat")
    ).strip().lower() or "compat"
    app.config["WEAVE_CSP_REPORT_ONLY"] = _is_truthy(
        os.environ.get("WEAVE_CSP_REPORT_ONLY", "true"),
        fallback=True,
    )

    trusted_hosts = [
        item.strip()
        for item in os.environ.get("WEAVE_TRUSTED_HOSTS", "").split(",")
        if item.strip()
    ]
    if trusted_hosts:
        app.config["TRUSTED_HOSTS"] = trusted_hosts

    if (
        weave_env == "production"
        and app.config["SECRET_KEY"] == "weave-local-dev-secret-key"
    ):
        raise RuntimeError("WEAVE_SECRET_KEY 환경변수가 필요합니다.")
