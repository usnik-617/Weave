from flask import jsonify, request


def success_response(data=None, status_code=200):
    return jsonify({"success": True, "data": data}), status_code


def success_response_legacy(data=None, status_code=200):
    body = {"success": True, "data": data}
    if isinstance(data, dict):
        for key, value in data.items():
            if key == "success":
                continue
            body[key] = value
    return jsonify(body), status_code


def error_response(message, code=400, details=None):
    body = {"success": False, "error": str(message)}
    if details is not None:
        body["details"] = details
    return jsonify(body), code


def is_api_request():
    return request.path.startswith("/api")


def author_payload_from_user(user_row):
    if not user_row:
        return None
    from weave.authz import normalize_role, role_to_icon, role_to_label

    role_value = normalize_role(user_row["role"])
    nickname = (
        user_row["nickname"]
        if "nickname" in user_row.keys() and user_row["nickname"]
        else user_row["username"]
    )
    return {
        "id": user_row["id"],
        "nickname": nickname,
        "role": role_value,
        "role_label": role_to_label(role_value),
        "role_icon": role_to_icon(role_value),
    }


def user_row_to_dict(row):
    if not row:
        return None
    from weave.authz import normalize_role, role_to_icon, role_to_label

    role_value = normalize_role(row["role"])
    nickname_value = (
        row["nickname"]
        if "nickname" in row.keys() and row["nickname"]
        else row["username"]
    )
    is_admin_value = bool(row["is_admin"]) if "is_admin" in row.keys() else False
    if role_value == "ADMIN":
        is_admin_value = True
    return {
        "id": row["id"],
        "name": row["name"],
        "username": row["username"],
        "nickname": nickname_value,
        "nicknameUpdatedAt": row["nickname_updated_at"]
        if "nickname_updated_at" in row.keys()
        else None,
        "email": row["email"],
        "phone": row["phone"],
        "birthDate": row["birth_date"],
        "joinDate": row["join_date"],
        "role": role_value,
        "roleLabel": f"[{role_to_label(role_value)}]",
        "roleIcon": role_to_icon(role_value),
        "status": row["status"],
        "generation": row["generation"],
        "interests": row["interests"],
        "certificates": row["certificates"],
        "availability": row["availability"],
        "isAdmin": is_admin_value,
        "is_admin": is_admin_value,
        "failedLoginCount": row["failed_login_count"],
        "lockedUntil": row["locked_until"],
    }
