from __future__ import annotations


def decide_role_request(conn, request_id, approver, approve, now_iso_func, log_audit_func):
    req = conn.execute("SELECT * FROM role_requests WHERE id = ?", (request_id,)).fetchone()
    if not req:
        return None, "not_found"
    if req["status"] != "PENDING":
        return None, "already_decided"

    next_status = "APPROVED" if approve else "REJECTED"
    conn.execute(
        "UPDATE role_requests SET status = ?, decided_at = ?, decided_by = ? WHERE id = ?",
        (next_status, now_iso_func(), approver["id"], request_id),
    )
    if approve:
        conn.execute(
            "UPDATE users SET role = ?, is_admin = CASE WHEN ? = 'ADMIN' THEN 1 ELSE is_admin END WHERE id = ?",
            (req["to_role"], req["to_role"], req["user_id"]),
        )
    log_audit_func(
        conn,
        f"role_request_{next_status.lower()}",
        "role_request",
        request_id,
        approver["id"],
        {"user_id": req["user_id"]},
    )
    return next_status, ""
