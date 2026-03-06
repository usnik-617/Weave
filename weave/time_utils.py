from datetime import datetime, timedelta, timezone


KST = timezone(timedelta(hours=9))


def parse_iso_datetime(value):
    if not value:
        return None
    try:
        normalized = str(value).strip()
        if normalized.endswith("Z"):
            normalized = normalized[:-1] + "+00:00"
        return datetime.fromisoformat(normalized)
    except Exception:
        return None


def activity_start_date_local(value):
    dt = parse_iso_datetime(value)
    if not dt:
        return None
    if dt.tzinfo is not None:
        dt = dt.astimezone(KST)
    return dt.date()


def now_iso():
    return datetime.now().isoformat()
