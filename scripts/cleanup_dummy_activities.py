import sqlite3
from pathlib import Path


def main() -> None:
    db_path = Path(__file__).resolve().parents[1] / "weave.db"
    conn = sqlite3.connect(db_path)
    conn.execute(
        """
        UPDATE activities
        SET is_cancelled = 1,
            cancelled_at = COALESCE(cancelled_at, datetime('now'))
        WHERE is_cancelled = 0
          AND (
            created_by IS NULL
            OR created_by NOT IN (
              SELECT id
              FROM users
              WHERE UPPER(COALESCE(role, '')) IN ('EXECUTIVE', 'LEADER', 'VICE_LEADER', 'ADMIN')
            )
          )
        """
    )
    changed = conn.total_changes
    conn.commit()
    conn.close()
    print(f"cleanup_done: {changed}")


if __name__ == "__main__":
    main()
