from __future__ import annotations

import sqlite3
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DB_PATH = ROOT / 'weave.db'


def scalar(conn: sqlite3.Connection, sql: str) -> int:
    row = conn.execute(sql).fetchone()
    return int(row[0] or 0) if row else 0


def main() -> int:
    if not DB_PATH.exists():
        print(f'[db-health] missing database: {DB_PATH}')
        return 1

    conn = sqlite3.connect(DB_PATH)
    try:
        checks = {
            'users': 'SELECT COUNT(*) FROM users',
            'posts': 'SELECT COUNT(*) FROM posts',
            'post_files': 'SELECT COUNT(*) FROM post_files',
            'comments': 'SELECT COUNT(*) FROM comments',
            'recommends': 'SELECT COUNT(*) FROM recommends',
            'activities': 'SELECT COUNT(*) FROM activities',
            'activity_applications': 'SELECT COUNT(*) FROM activity_applications',
            'orphan_post_files': 'SELECT COUNT(*) FROM post_files pf LEFT JOIN posts p ON p.id = pf.post_id WHERE p.id IS NULL',
            'orphan_comments': 'SELECT COUNT(*) FROM comments c LEFT JOIN posts p ON p.id = c.post_id WHERE p.id IS NULL',
            'orphan_recommends': 'SELECT COUNT(*) FROM recommends r LEFT JOIN posts p ON p.id = r.post_id WHERE p.id IS NULL',
            'orphan_notice_links': 'SELECT COUNT(*) FROM activities a LEFT JOIN posts p ON p.id = a.notice_post_id WHERE a.notice_post_id IS NOT NULL AND p.id IS NULL',
            'orphan_activity_applications': 'SELECT COUNT(*) FROM activity_applications aa LEFT JOIN activities a ON a.id = aa.activity_id WHERE a.id IS NULL',
        }
        print('[db-health] counts')
        has_issue = False
        for name, sql in checks.items():
            value = scalar(conn, sql)
            print(f'- {name}: {value}')
            if name.startswith('orphan_') and value > 0:
                has_issue = True
        if has_issue:
            print('[db-health] orphan references detected')
            return 2
        print('[db-health] OK')
        return 0
    finally:
        conn.close()


if __name__ == '__main__':
    raise SystemExit(main())
