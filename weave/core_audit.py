from __future__ import annotations

from weave import core


def write_app_log(level, action, user_id=None, extra=None):
    payload = {
        "action": action,
        "ip": core.get_client_ip() if core.request else "unknown",
        "user_id": user_id,
        "user_agent": core.get_user_agent() if core.request else "",
    }
    if extra:
        payload.update(extra)
    line = core.json.dumps(payload, ensure_ascii=False)
    if level == "warning":
        core.logger.warning(line)
    elif level == "error":
        core.logger.error(line)
    else:
        core.logger.info(line)


def log_audit(*args, **kwargs):
    conn = None
    owns_connection = False
    if args and isinstance(args[0], core.sqlite3.Connection):
        conn, action, target_type, target_id, actor_user_id, metadata = (
            list(args) + [None] * 6
        )[0:6]
    else:
        actor_user_id = args[0] if len(args) > 0 else kwargs.get("actor_user_id")
        action = args[1] if len(args) > 1 else kwargs.get("action")
        target_type = args[2] if len(args) > 2 else kwargs.get("target_type")
        target_id = args[3] if len(args) > 3 else kwargs.get("target_id")
        metadata = args[4] if len(args) > 4 else kwargs.get("metadata")

    actor = actor_user_id if actor_user_id is not None else core.current_user_id()
    sql = (
        "INSERT INTO audit_logs (actor_user_id, action, target_type, target_id, metadata_json, created_at) "
        "VALUES (?, ?, ?, ?, ?, ?)"
    )
    values = (
        actor,
        str(action or "").strip(),
        str(target_type or "").strip(),
        int(target_id) if target_id is not None else None,
        core.json.dumps(metadata or {}, ensure_ascii=False),
        core.now_iso(),
    )

    try:
        if conn is None:
            conn = core.get_db_connection()
            owns_connection = True
        conn.execute(sql, values)
        if owns_connection:
            conn.commit()
    except Exception as exc:
        core.logger.error(
            core.json.dumps(
                {"action": "audit_log_failed", "error": str(exc)},
                ensure_ascii=False,
            )
        )
    finally:
        if conn and owns_connection:
            conn.close()
