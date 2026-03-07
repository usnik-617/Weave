from __future__ import annotations

from weave import core


def get_client_ip():
    forwarded = core.request.headers.get("X-Forwarded-For", "")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return core.request.remote_addr or "unknown"


def get_user_agent():
    return core.request.headers.get("User-Agent", "")[:500]
