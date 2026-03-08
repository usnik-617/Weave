import re


def coerce_int_in_range(value, field_name, min_value, max_value, default=None):
    raw = value
    if raw is None or str(raw).strip() == "":
        if default is None:
            return False, None, f"{field_name} 값이 필요합니다."
        return True, int(default), ""
    try:
        number = int(str(raw).strip())
    except Exception:
        return False, None, f"{field_name} 값은 정수여야 합니다."
    if number < int(min_value) or number > int(max_value):
        return (
            False,
            None,
            f"{field_name} 값은 {int(min_value)}~{int(max_value)} 범위여야 합니다.",
        )
    return True, number, ""


def validate_nickname(nickname):
    text = str(nickname or "").strip()
    if not re.fullmatch(r"^[가-힣A-Za-z0-9]{2,12}$", text):
        return (
            False,
            "닉네임은 2~12자이며 한글/영문/숫자만 사용할 수 있습니다. (띄어쓰기/특수문자 불가)",
        )
    return True, ""


def normalize_contact(value):
    return str(value or "").replace("-", "").strip().lower()


def to_list_text(value):
    if isinstance(value, list):
        return ", ".join([str(item).strip() for item in value if str(item).strip()])
    return str(value or "").strip()


def validate_password_policy(password):
    if len(password or "") < 8:
        return False, "비밀번호는 8자 이상이어야 합니다."
    if not re.search(r"[A-Z]", password or ""):
        return False, "비밀번호에 대문자 1개 이상이 필요합니다."
    if not re.search(r"[^A-Za-z0-9]", password or ""):
        return False, "비밀번호에 특수문자 1개 이상이 필요합니다."
    return True, ""


def validate_signup_payload(payload):
    required_fields = [
        "name",
        "nickname",
        "email",
        "birthDate",
        "phone",
        "username",
        "password",
    ]
    for field in required_fields:
        if not str(payload.get(field, "")).strip():
            return False, f"{field} 값이 필요합니다."

    password_ok, password_message = validate_password_policy(
        str(payload.get("password", ""))
    )
    if not password_ok:
        return False, password_message

    nickname_ok, nickname_message = validate_nickname(payload.get("nickname", ""))
    if not nickname_ok:
        return False, nickname_message

    return True, ""
