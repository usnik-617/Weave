from __future__ import annotations

from datetime import datetime, timedelta


def mark_dormant_users(reference_time=None):
    from weave import core

    ref = reference_time or datetime.now()
    threshold = (ref - timedelta(days=365)).isoformat()
    conn = core.get_db_connection()
    rows = conn.execute(
        "SELECT id FROM users WHERE status = 'active' AND COALESCE(last_active_at, join_date) < ?",
        (threshold,),
    ).fetchall()
    if rows:
        ids = [row["id"] for row in rows]
        placeholders = ",".join(["?"] * len(ids))
        conn.execute(
            f"UPDATE users SET status = 'dormant' WHERE id IN ({placeholders})", ids
        )
        conn.commit()
    conn.close()
    return len(rows)
