import os
from datetime import timedelta


def load_config(app):
    weave_env = os.environ.get("WEAVE_ENV", "development").lower()
    max_upload_mb = int(os.environ.get("MAX_UPLOAD_MB", "5"))
    app.config["SECRET_KEY"] = os.environ.get("WEAVE_SECRET_KEY", "weave-local-dev-secret-key")
    app.config["MAX_CONTENT_LENGTH"] = max_upload_mb * 1024 * 1024
    app.config["SESSION_COOKIE_HTTPONLY"] = True
    app.config["SESSION_COOKIE_SAMESITE"] = os.environ.get("WEAVE_SESSION_SAMESITE", "Lax")
    app.config["SESSION_COOKIE_SECURE"] = weave_env == "production"
    app.config["PERMANENT_SESSION_LIFETIME"] = timedelta(
        seconds=int(os.environ.get("WEAVE_SESSION_LIFETIME_SEC", 60 * 60 * 24 * 7))
    )

    trusted_hosts = [item.strip() for item in os.environ.get("WEAVE_TRUSTED_HOSTS", "").split(",") if item.strip()]
    if trusted_hosts:
        app.config["TRUSTED_HOSTS"] = trusted_hosts

    if weave_env == "production" and app.config["SECRET_KEY"] == "weave-local-dev-secret-key":
        raise RuntimeError("WEAVE_SECRET_KEY 환경변수가 필요합니다.")
