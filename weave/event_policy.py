from __future__ import annotations

import re
from datetime import datetime, timedelta

from weave.authz import can_view_event_details, normalize_role, role_at_least


def resolve_activity_calendar_window(date_value, view):
    normalized_view = str(view or "month").strip().lower()
    if normalized_view not in ("month", "week"):
        normalized_view = "month"

    normalized_date = str(date_value or "").strip()
    if not normalized_date:
        base_date = datetime.now().date()
    else:
        try:
            base_date = datetime.fromisoformat(normalized_date).date()
        except Exception:
            base_date = datetime.now().date()

    if normalized_view == "week":
        start_date = base_date - timedelta(days=base_date.weekday())
        end_date = start_date + timedelta(days=6)
    else:
        start_date = base_date.replace(day=1)
        next_month = (start_date.replace(day=28) + timedelta(days=4)).replace(day=1)
        end_date = next_month - timedelta(days=1)

    return normalized_view, start_date, end_date


def is_valid_recurrence_group_id(group_id):
    value = str(group_id or "").strip()
    if not value or len(value) > 64:
        return False
    return bool(re.fullmatch(r"[A-Za-z0-9_-]+", value))


def can_manage_activity(user):
    return bool(user) and role_at_least(user["role"], "EXECUTIVE")


def can_manage_event(user):
    return bool(user) and role_at_least(user["role"], "VICE_LEADER")


def can_vote_event(user):
    return bool(user) and role_at_least(user["role"], "MEMBER")


def can_view_event(user):
    return can_view_event_details(user)


def normalize_vote_status(raw_status):
    value = str(raw_status or "").strip().upper()
    if value in ("ATTEND", "ABSENT", "WAITING"):
        return value
    return ""


def event_capacity(row):
    return int(row["capacity"] or row["max_participants"] or 0)


def serialize_event_list_item(row):
    return {
        "id": row["id"],
        "title": row["title"],
        "description": row["description"],
        "location": row["location"],
        "supplies": row["supplies"],
        "noticePostId": row["notice_post_id"],
        "startDatetime": row["start_datetime"] or row["event_date"],
        "endDatetime": row["end_datetime"] or row["start_datetime"] or row["event_date"],
        "capacity": event_capacity(row),
        "eventDate": row["event_date"],
        "maxParticipants": row["max_participants"],
        "participantCount": row["participant_count"],
        "createdBy": row["created_by"],
        "createdByUsername": row["author_username"],
        "createdAt": row["created_at"],
        "myStatus": row["my_status"],
    }


def serialize_event_participant(row):
    return {
        "userId": row["user_id"],
        "status": row["status"],
        "joinedAt": row["created_at"],
        "nickname": row["nickname"] or row["username"],
        "role": normalize_role(row["role"]),
    }


def serialize_event_detail(row, participants):
    return {
        "id": row["id"],
        "title": row["title"],
        "description": row["description"],
        "location": row["location"],
        "supplies": row["supplies"],
        "noticePostId": row["notice_post_id"],
        "startDatetime": row["start_datetime"] or row["event_date"],
        "endDatetime": row["end_datetime"] or row["start_datetime"] or row["event_date"],
        "capacity": event_capacity(row),
        "participantCount": int(row["participant_count"] or 0),
        "myStatus": row["my_status"],
        "createdBy": row["created_by"],
        "createdByUsername": row["author_username"],
        "createdAt": row["created_at"],
        "participants": [serialize_event_participant(p) for p in participants],
    }
