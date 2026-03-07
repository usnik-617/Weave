from __future__ import annotations

# Message-key to stable code mapping (for logging/client telemetry rollout)
ERROR_CODE_BY_KEY = {
    "AUTH_TOO_MANY_REQUESTS": "AUTH_001",
    "AUTH_INVALID_CREDENTIALS": "AUTH_002",
    "AUTH_WITHDRAWN": "AUTH_003",
    "AUTH_SUSPENDED": "AUTH_004",
    "AUTH_LOGIN_RATE_LIMITED": "AUTH_005",
    "AUTH_EMAIL_EXISTS": "AUTH_006",
    "AUTH_USERNAME_EXISTS": "AUTH_007",
    "AUTH_NICKNAME_EXISTS": "AUTH_008",
    "EVENT_NOT_FOUND": "EVT_001",
    "EVENT_VIEW_FORBIDDEN": "EVT_002",
    "POST_NOT_FOUND": "PST_001",
    "UNAUTHORIZED": "COMMON_001",
}


def error_code(key):
    return ERROR_CODE_BY_KEY.get(str(key or ""), "UNKNOWN")
