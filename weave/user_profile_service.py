from __future__ import annotations


def get_user_profile_payload(conn, row, user_row_to_dict):
    summary = conn.execute(
        """
        SELECT COALESCE(SUM(minutes), 0) AS total_minutes,
               COUNT(DISTINCT event_id) AS attended_events
        FROM volunteer_activity
        WHERE user_id = ?
        """,
        (row["id"],),
    ).fetchone()
    return {
        "user": user_row_to_dict(row),
        "volunteerSummary": {
            "totalVolunteerHours": round(float(summary["total_minutes"] or 0) / 60.0, 2),
            "totalEventsAttended": int(summary["attended_events"] or 0),
        },
    }
