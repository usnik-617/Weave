from __future__ import annotations


def find_signup_conflict(conn, payload, nickname):
    cur = conn.cursor()
    exists_email = cur.execute(
        "SELECT id FROM users WHERE email = ?", (payload["email"],)
    ).fetchone()
    if exists_email:
        return "email"

    exists_username = cur.execute(
        "SELECT id FROM users WHERE username = ?", (payload["username"],)
    ).fetchone()
    if exists_username:
        return "username"

    exists_nickname = cur.execute(
        "SELECT id FROM users WHERE nickname = ?", (nickname,)
    ).fetchone()
    if exists_nickname:
        return "nickname"

    return ""


def get_user_by_username(conn, username):
    return conn.execute("SELECT * FROM users WHERE username = ?", (username,)).fetchone()


def get_user_contacts_by_username(conn, username):
    return conn.execute(
        "SELECT * FROM users WHERE username = ?",
        (username,),
    ).fetchone()
