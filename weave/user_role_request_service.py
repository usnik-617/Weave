from __future__ import annotations


def validate_transition(current_role, target_role):
    allowed = {("GENERAL", "MEMBER"), ("MEMBER", "EXECUTIVE")}
    return (current_role, target_role) in allowed


def role_requests_page_data(total, rows, page, page_size):
    return {
        "items": [dict(row) for row in rows],
        "pagination": {
            "total": int(total or 0),
            "page": page,
            "pageSize": page_size,
            "totalPages": max(1, (int(total or 0) + page_size - 1) // page_size),
        },
    }
