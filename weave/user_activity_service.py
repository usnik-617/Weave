from __future__ import annotations

import json


def build_my_activity_history_response(rows):
    total_hours = sum(float(row["hours"] or 0) for row in rows)
    total_points = sum(int(row["points"] or 0) for row in rows) - sum(
        int(row["penalty_points"] or 0) for row in rows
    )
    items = [
        {
            "activityId": row["activity_id"],
            "title": row["title"],
            "startAt": row["start_at"],
            "endAt": row["end_at"],
            "place": row["place"],
            "status": row["status"],
            "attendanceStatus": row["attendance_status"],
            "hours": row["hours"],
            "points": row["points"],
            "penaltyPoints": row["penalty_points"],
        }
        for row in rows
    ]
    return {
        "ok": True,
        "summary": {
            "totalHours": round(total_hours, 2),
            "totalPoints": total_points,
            "certificateDownloadUrl": "/api/me/certificate.csv",
        },
        "items": items,
    }


def build_list_my_activity_items(rows):
    return {
        "items": [
            {
                "type": row["activity_type"],
                "targetType": row["target_type"],
                "targetId": row["target_id"],
                "metadata": json.loads(row["metadata_json"] or "{}"),
                "createdAt": row["created_at"],
            }
            for row in rows
        ]
    }
