import shutil
import time
from datetime import datetime, timedelta

from weave import core
from weave.media_queue import get_queue_metrics
from weave.storage_backend import snapshot_storage_stats


def _is_health_access_allowed():
    token = str(core.os.environ.get("WEAVE_HEALTH_TOKEN", "")).strip()
    allowed_ips_text = str(core.os.environ.get("WEAVE_HEALTH_ALLOW_IPS", "")).strip()
    allowed_ips = {ip.strip() for ip in allowed_ips_text.split(",") if ip.strip()}

    if token:
        supplied = str(core.request.headers.get("X-Weave-Health-Token", "")).strip()
        if supplied != token:
            return False

    if allowed_ips:
        client_ip = core.get_client_ip()
        if client_ip not in allowed_ips:
            return False

    return True


def metrics():
    if not _is_health_access_allowed():
        return core.error_response("Forbidden", 403)

    active_users_last_hour = 0
    total_posts = 0
    total_comments = 0

    try:
        conn = core.get_db_connection()
        one_hour_ago = (datetime.now() - timedelta(hours=1)).isoformat()
        active_users_last_hour = int(
            conn.execute(
                "SELECT COUNT(*) AS c FROM users WHERE status = 'active' AND last_active_at >= ?",
                (one_hour_ago,),
            ).fetchone()["c"]
            or 0
        )
        total_posts = int(
            conn.execute("SELECT COUNT(*) AS c FROM posts").fetchone()["c"] or 0
        )
        total_comments = int(
            conn.execute("SELECT COUNT(*) AS c FROM comments").fetchone()["c"] or 0
        )
        conn.close()
    except Exception:
        active_users_last_hour = 0
        total_posts = 0
        total_comments = 0

    return core.jsonify(
        {
            "uptime_seconds": int(time.time() - core.APP_STARTED_AT),
            "total_requests": int(core.APP_METRICS["total_requests"]),
            "error_count": int(core.APP_METRICS["error_count"]),
            "active_users_last_hour": active_users_last_hour,
            "total_posts": total_posts,
            "total_comments": total_comments,
            "media_queue": get_queue_metrics(),
            "storage": snapshot_storage_stats(),
            "database_mode": (
                "sqlite" if str(core.DATABASE_URL).strip().lower().startswith("sqlite")
                else "postgres"
            ),
        }
    )


def healthz():
    if not _is_health_access_allowed():
        return core.error_response("Forbidden", 403)

    try:
        conn = core.get_db_connection()
        conn.execute("SELECT 1")
        conn.close()
        disk_free_mb = int(shutil.disk_usage(core.BASE_DIR).free / (1024 * 1024))
        return core.success_response(
            {
                "status": "healthy",
                "database": "ok",
                "disk_space_mb": disk_free_mb,
                "uptime_seconds": int(time.time() - core.APP_STARTED_AT),
            },
            200,
        )
    except Exception as exc:
        return core.error_response(
            "DB connectivity check failed", 500, {"reason": str(exc)}
        )
