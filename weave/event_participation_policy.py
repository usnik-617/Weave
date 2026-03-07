from __future__ import annotations


def is_account_blocked(user):
    return bool(user and user["status"] in ("suspended", "deleted"))


def can_reapply_activity(existing_row):
    if not existing_row:
        return True
    return str(existing_row["status"] or "").lower() in {"cancelled", "noshow"}


def event_capacity_reached(limit_count, active_count):
    return int(limit_count or 0) > 0 and int(active_count or 0) >= int(limit_count or 0)


def next_activity_status(limit_count, confirmed_count):
    if int(limit_count or 0) <= 0 or int(confirmed_count or 0) < int(limit_count or 0):
        return "confirmed"
    return "waiting"
