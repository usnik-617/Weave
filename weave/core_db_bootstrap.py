from __future__ import annotations

from datetime import datetime

from werkzeug.security import check_password_hash, generate_password_hash

from weave.time_utils import now_iso


def seed_initial_data(cur, default_admin_password):
    admin_email = "admin@weave.com"
    admin_defaults = {
        "name": "관리자",
        "username": "admin",
        "email": admin_email,
        "phone": "010-0000-0000",
        "birth_date": "1990.01.01",
        "role": "ADMIN",
        "status": "active",
        "generation": "운영",
        "interests": "운영 총괄",
        "certificates": "CPR",
        "availability": "상시",
    }
    admin_now = now_iso()
    admin_row = cur.execute(
        "SELECT * FROM users WHERE username = ?", (admin_defaults["username"],)
    ).fetchone()
    if not admin_row:
        admin_row = cur.execute(
            "SELECT * FROM users WHERE email = ?", (admin_defaults["email"],)
        ).fetchone()

    if admin_row:
        needs_password_reset = not check_password_hash(
            admin_row["password_hash"], default_admin_password
        )
        password_hash_value = (
            generate_password_hash(default_admin_password)
            if needs_password_reset
            else admin_row["password_hash"]
        )
        cur.execute(
            """
            UPDATE users
            SET name = ?,
                username = ?,
                email = ?,
                phone = ?,
                birth_date = ?,
                password_hash = ?,
                role = ?,
                is_admin = 1,
                status = ?,
                approved_at = COALESCE(approved_at, ?),
                generation = CASE WHEN generation IS NULL OR generation = '' THEN ? ELSE generation END,
                interests = CASE WHEN interests IS NULL OR interests = '' THEN ? ELSE interests END,
                certificates = CASE WHEN certificates IS NULL OR certificates = '' THEN ? ELSE certificates END,
                availability = CASE WHEN availability IS NULL OR availability = '' THEN ? ELSE availability END
            WHERE id = ?
            """,
            (
                admin_defaults["name"],
                admin_defaults["username"],
                admin_defaults["email"],
                admin_defaults["phone"],
                admin_defaults["birth_date"],
                password_hash_value,
                admin_defaults["role"],
                admin_defaults["status"],
                admin_now,
                admin_defaults["generation"],
                admin_defaults["interests"],
                admin_defaults["certificates"],
                admin_defaults["availability"],
                admin_row["id"],
            ),
        )
    else:
        cur.execute(
            """
            INSERT INTO users (
                name, username, email, phone, birth_date, password_hash, join_date,
                role, is_admin, status, approved_at, generation, interests, certificates, availability, nickname, nickname_updated_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                admin_defaults["name"],
                admin_defaults["username"],
                admin_defaults["email"],
                admin_defaults["phone"],
                admin_defaults["birth_date"],
                generate_password_hash(default_admin_password),
                admin_now,
                admin_defaults["role"],
                1,
                admin_defaults["status"],
                admin_now,
                admin_defaults["generation"],
                admin_defaults["interests"],
                admin_defaults["certificates"],
                admin_defaults["availability"],
                admin_defaults["username"],
                admin_now,
            ),
        )

    seed_rules = cur.execute("SELECT id FROM rules_versions LIMIT 1").fetchone()
    if not seed_rules:
        cur.execute(
            """
            INSERT INTO rules_versions (version_tag, effective_date, summary, content, created_at)
            VALUES (?, ?, ?, ?, ?)
            """,
            (
                "v1.0",
                datetime.now().date().isoformat(),
                "초기 운영 규칙 등록",
                "규칙/규약 초기 버전",
                now_iso(),
            ),
        )

    seed_year = datetime.now().year
    sample_activities = [
        {
            "title": "유기견 봉사",
            "description": "유기견 보호소 환경정리 및 산책 봉사",
            "start_at": f"{seed_year}-03-14T09:30:00",
            "end_at": f"{seed_year}-03-14T12:00:00",
            "place": "남양주 유기동물 보호소",
            "supplies": "편한 복장, 장갑",
            "gather_time": "09:20",
            "manager_name": "운영진",
            "recruitment_limit": 30,
        },
        {
            "title": "백봉산 플로깅 및 산불조심 캠페인 봉사",
            "description": "백봉산 일대 플로깅 및 산불예방 캠페인 진행",
            "start_at": f"{seed_year}-03-28T09:00:00",
            "end_at": f"{seed_year}-03-28T12:30:00",
            "place": "백봉산 입구",
            "supplies": "집게, 봉투, 물",
            "gather_time": "08:50",
            "manager_name": "운영진",
            "recruitment_limit": 40,
        },
    ]
    for item in sample_activities:
        already_exists = cur.execute(
            "SELECT id FROM activities WHERE title = ? AND start_at = ? LIMIT 1",
            (item["title"], item["start_at"]),
        ).fetchone()
        if already_exists:
            continue
        cur.execute(
            """
            INSERT INTO activities (
                title, description, start_at, end_at, place, supplies, gather_time,
                manager_name, recruitment_limit, created_by, created_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, NULL, ?)
            """,
            (
                item["title"],
                item["description"],
                item["start_at"],
                item["end_at"],
                item["place"],
                item["supplies"],
                item["gather_time"],
                item["manager_name"],
                item["recruitment_limit"],
                now_iso(),
            ),
        )

    cur.execute(
        """
        UPDATE activities
        SET start_at = ?, end_at = ?
        WHERE title = ?
          AND start_at = ?
          AND end_at = ?
        """,
        (
            f"{seed_year}-03-28T09:00:00",
            f"{seed_year}-03-28T12:30:00",
            "백봉산 플로깅 및 산불조심 캠페인 봉사",
            f"{seed_year}-03-21T09:00:00",
            f"{seed_year}-03-21T12:30:00",
        ),
    )

    cur.execute(
        """
        DELETE FROM activities
        WHERE title = ?
          AND start_at = ?
          AND id NOT IN (
              SELECT MIN(id)
              FROM activities
              WHERE title = ? AND start_at = ?
          )
        """,
        (
            "백봉산 플로깅 및 산불조심 캠페인 봉사",
            f"{seed_year}-03-28T09:00:00",
            "백봉산 플로깅 및 산불조심 캠페인 봉사",
            f"{seed_year}-03-28T09:00:00",
        ),
    )

