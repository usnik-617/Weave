from __future__ import annotations


def serialize_activity_row(row):
    return {
        "id": row["id"],
        "title": row["title"],
        "description": row["description"],
        "startAt": row["start_at"],
        "endAt": row["end_at"],
        "place": row["place"],
        "supplies": row["supplies"],
        "gatherTime": row["gather_time"],
        "manager": row["manager_name"],
        "recruitmentLimit": row["recruitment_limit"],
        "recurrenceGroupId": row["recurrence_group_id"],
        "isCancelled": bool(row["is_cancelled"]),
    }


def build_annual_report(conn, year):
    start = f"{year}-01-01"
    end = f"{year}-12-31"
    total_activities = conn.execute(
        "SELECT COUNT(*) AS c FROM activities WHERE date(start_at) BETWEEN ? AND ?",
        (start, end),
    ).fetchone()["c"]
    total_hours = conn.execute(
        """
        SELECT COALESCE(SUM(ap.hours), 0) AS h
        FROM activity_applications ap
        JOIN activities a ON a.id = ap.activity_id
        WHERE ap.attendance_status = 'present' AND date(a.start_at) BETWEEN ? AND ?
        """,
        (start, end),
    ).fetchone()["h"]
    total_participants = conn.execute(
        """
        SELECT COUNT(DISTINCT ap.user_id) AS c
        FROM activity_applications ap
        JOIN activities a ON a.id = ap.activity_id
        WHERE ap.status IN ('confirmed', 'waiting', 'cancelled', 'noshow')
          AND date(a.start_at) BETWEEN ? AND ?
        """,
        (start, end),
    ).fetchone()["c"]

    impact_metric = (
        f"활동 {total_activities}건, 누적 {round(float(total_hours or 0), 1)}시간"
    )
    return {
        "year": year,
        "totalActivities": int(total_activities or 0),
        "totalHours": round(float(total_hours or 0), 2),
        "totalParticipants": int(total_participants or 0),
        "impact": impact_metric,
    }


def csv_response(filename, headers, rows):
    from weave import core

    output = core.io.StringIO()
    writer = core.csv.writer(output)
    writer.writerow(headers)
    for row in rows:
        writer.writerow(row)
    response = core.Response(output.getvalue(), mimetype="text/csv; charset=utf-8")
    response.headers["Content-Disposition"] = f"attachment; filename={filename}"
    return response
