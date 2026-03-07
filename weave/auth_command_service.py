from __future__ import annotations

import sqlite3

from werkzeug.security import generate_password_hash

from weave.time_utils import now_iso
from weave.validators import to_list_text


def create_signup_user(conn, payload, nickname):
    cur = conn.cursor()
    try:
        cur.execute(
            """
            INSERT INTO users (
                name, username, email, phone, birth_date, password_hash, join_date,
                role, status, generation, interests, certificates, availability, nickname, nickname_updated_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                payload["name"].strip(),
                payload["username"].strip(),
                payload["email"].strip(),
                payload["phone"].strip(),
                payload["birthDate"].strip(),
                generate_password_hash(payload["password"]),
                now_iso(),
                "GENERAL",
                "active",
                str(payload.get("generation", "")).strip(),
                to_list_text(payload.get("interests", "")),
                to_list_text(payload.get("certificates", "")),
                str(payload.get("availability", "")).strip(),
                nickname,
                now_iso(),
            ),
        )
    except sqlite3.IntegrityError:
        return None, "nickname"
    return cur.lastrowid, ""
