from functools import wraps

from flask import session

from weave.responses import error_response


ROLE_ORDER = {
    "GENERAL": 1,
    "MEMBER": 2,
    "EXECUTIVE": 3,
    "VICE_LEADER": 4,
    "LEADER": 5,
    "ADMIN": 6,
}

LEGACY_ROLE_MAP = {
    "member": "MEMBER",
    "staff": "EXECUTIVE",
    "admin": "ADMIN",
    "general": "GENERAL",
    "executive": "EXECUTIVE",
    "leader": "LEADER",
    "vice_leader": "VICE_LEADER",
    "operator": "ADMIN",
    "ADMIN": "ADMIN",
    "MEMBER": "MEMBER",
    "EXECUTIVE": "EXECUTIVE",
    "LEADER": "LEADER",
    "VICE_LEADER": "VICE_LEADER",
    "GENERAL": "GENERAL",
}


def normalize_role(role):
    text = str(role or "GENERAL").strip()
    if text in ROLE_ORDER:
        return text
    mapped = LEGACY_ROLE_MAP.get(text.lower())
    return mapped or "GENERAL"


def role_to_label(role):
    labels = {
        "GENERAL": "일반",
        "MEMBER": "단원",
        "EXECUTIVE": "임원",
        "LEADER": "단장",
        "VICE_LEADER": "부단장",
        "ADMIN": "운영자",
    }
    return labels.get(normalize_role(role), "일반")


def role_to_icon(role):
    icons = {
        "ADMIN": "🛡️",
        "LEADER": "👑",
        "VICE_LEADER": "⭐",
        "MEMBER": "🙋",
        "EXECUTIVE": "🎯",
    }
    return icons.get(normalize_role(role), "")


def role_at_least(role, minimum):
    current = normalize_role(role)
    required = normalize_role(minimum)
    return ROLE_ORDER.get(current, 0) >= ROLE_ORDER.get(required, 0)


def _role_from_user_or_role(user_or_role):
    if isinstance(user_or_role, dict):
        return normalize_role(user_or_role.get("role"))
    if user_or_role is not None:
        try:
            return normalize_role(user_or_role["role"])
        except Exception:
            pass
    return normalize_role(user_or_role)


def _read_user_field(user, field_name, default=None):
    if user is None:
        return default
    if isinstance(user, dict):
        return user.get(field_name, default)
    try:
        return user[field_name]
    except Exception:
        return default


def is_admin_like(user_or_role):
    role_value = _role_from_user_or_role(user_or_role)
    if role_at_least(role_value, "ADMIN"):
        return True
    return bool(_read_user_field(user_or_role, "is_admin", False))


def can_view_event_details(user):
    if not user:
        return False
    return role_at_least(_read_user_field(user, "role"), "MEMBER")


def can_join_event(user):
    if not user:
        return False
    return role_at_least(_read_user_field(user, "role"), "MEMBER")


def can_comment_notice(user):
    if not user:
        return False
    return role_at_least(_read_user_field(user, "role"), "MEMBER")


def can_create_notice(user):
    if not user:
        return False
    return role_at_least(_read_user_field(user, "role"), "EXECUTIVE")


def can_create_gallery(user):
    if not user:
        return False
    return role_at_least(_read_user_field(user, "role"), "EXECUTIVE")


def get_current_user_row(conn=None):
    user_id = session.get("user_id")
    if not user_id:
        return None

    owned = False
    if conn is None:
        from weave import core

        conn = core.get_db_connection()
        owned = True

    row = conn.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()
    if owned:
        conn.close()
    return row


def roles_allowed(user_row, allowed_roles):
    if not user_row:
        return False
    return normalize_role(user_row["role"]) in {
        normalize_role(role) for role in allowed_roles
    }


def login_required(func):
    @wraps(func)
    def wrapper(*args, **kwargs):
        user = get_current_user_row()
        if not user:
            return error_response("Unauthorized", 401)
        if user["status"] in ("suspended", "deleted"):
            return error_response("계정 상태로 인해 요청을 처리할 수 없습니다.", 403)
        return func(*args, **kwargs)

    return wrapper


def admin_required(func):
    @wraps(func)
    def wrapper(*args, **kwargs):
        user = get_current_user_row()
        if not user:
            return error_response("Unauthorized", 401)
        if not roles_allowed(user, {"ADMIN", "LEADER", "VICE_LEADER"}):
            return error_response("Forbidden", 403)
        return func(*args, **kwargs)

    return wrapper


def role_required(min_role):
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            user = get_current_user_row()
            if not user:
                return error_response("Unauthorized", 401)
            if not role_at_least(user["role"], min_role):
                return error_response("Forbidden", 403)
            return func(*args, **kwargs)

        return wrapper

    return decorator


def roles_required(allowed_roles):
    allowed = {normalize_role(role) for role in allowed_roles}

    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            user = get_current_user_row()
            if not user:
                return error_response("Unauthorized", 401)
            user_role = normalize_role(user["role"])
            if user_role not in allowed:
                return error_response("권한이 없습니다.", 403)
            return func(*args, **kwargs)

        return wrapper

    return decorator


def active_member_required(func):
    @wraps(func)
    def wrapper(*args, **kwargs):
        user = get_current_user_row()
        if not user:
            return error_response("Unauthorized", 401)
        if user["status"] != "active":
            return error_response("승인된 정식 단원만 이용할 수 있습니다.", 403)
        return func(*args, **kwargs)

    return wrapper
