from __future__ import annotations


def calculate_activity_hours(activity):
    from weave import core

    start_dt = core.parse_iso_datetime(activity["start_at"])
    end_dt = core.parse_iso_datetime(activity["end_at"])
    if start_dt and end_dt and end_dt > start_dt:
        return max(round((end_dt - start_dt).total_seconds() / 3600, 2), 0.5)
    return 2.0
