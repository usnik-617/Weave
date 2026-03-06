"""User table schema/data migrations.

This module keeps user-related migration logic isolated so ``weave.core`` can stay
as a compatibility-oriented facade.
"""


def ensure_users_migration(cur):
    """Ensure users table columns and normalize legacy values."""
    existing_cols = {
        row["name"] for row in cur.execute("PRAGMA table_info(users)").fetchall()
    }
    migrations = [
        ("role", "TEXT NOT NULL DEFAULT 'GENERAL'"),
        ("is_admin", "INTEGER NOT NULL DEFAULT 0"),
        ("status", "TEXT NOT NULL DEFAULT 'active'"),
        ("generation", "TEXT DEFAULT ''"),
        ("interests", "TEXT DEFAULT ''"),
        ("certificates", "TEXT DEFAULT ''"),
        ("availability", "TEXT DEFAULT ''"),
        ("failed_login_count", "INTEGER NOT NULL DEFAULT 0"),
        ("locked_until", "TEXT"),
        ("approved_at", "TEXT"),
        ("approved_by", "INTEGER"),
        ("retention_until", "TEXT"),
        ("deleted_at", "TEXT"),
        ("nickname", "TEXT"),
        ("nickname_updated_at", "TEXT"),
        ("last_active_at", "TEXT"),
    ]
    for column_name, column_type in migrations:
        if column_name not in existing_cols:
            cur.execute(f"ALTER TABLE users ADD COLUMN {column_name} {column_type}")

    cur.execute("UPDATE users SET role = 'MEMBER' WHERE role = 'member'")
    cur.execute("UPDATE users SET role = 'EXECUTIVE' WHERE role = 'staff'")
    cur.execute(
        "UPDATE users SET role = 'ADMIN' WHERE role IN ('admin', 'operator', 'OPERATOR')"
    )
    cur.execute(
        "UPDATE users SET role = 'GENERAL' WHERE role IS NULL OR TRIM(role) = ''"
    )
    cur.execute(
        "UPDATE users SET status = 'active' WHERE status IS NULL OR TRIM(status) = ''"
    )
    cur.execute(
        "UPDATE users SET status = 'deleted' WHERE status IN ('withdrawn', 'WITHDRAWN')"
    )
    cur.execute(
        "UPDATE users SET status = 'suspended' WHERE status IN ('locked', 'LOCKED')"
    )
    cur.execute("UPDATE users SET is_admin = 1 WHERE role = 'ADMIN'")
    cur.execute(
        "UPDATE users SET nickname = username WHERE nickname IS NULL OR TRIM(nickname) = ''"
    )
    cur.execute(
        "UPDATE users SET nickname_updated_at = COALESCE(nickname_updated_at, join_date, datetime('now'))"
    )
    cur.execute(
        "UPDATE users SET last_active_at = COALESCE(last_active_at, join_date, datetime('now'))"
    )


def ensure_table_indexes(cur):
    """Ensure user table indexes required by current query patterns."""
    cur.execute("CREATE INDEX IF NOT EXISTS idx_users_status ON users(status)")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_users_role ON users(role)")
