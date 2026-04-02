from __future__ import annotations

import argparse
import sqlite3
from typing import Iterable

import psycopg2
from psycopg2.extras import RealDictCursor

CORE_TABLES: tuple[str, ...] = (
    'users',
    'posts',
    'post_files',
    'comments',
    'recommends',
    'activities',
    'activity_applications',
    'audit_logs',
    'in_app_notifications',
)


def sqlite_count(conn: sqlite3.Connection, table: str) -> int:
    row = conn.execute(f'SELECT COUNT(*) FROM "{table}"').fetchone()
    return int(row[0] or 0) if row else 0


def postgres_count(conn, table: str) -> int:
    with conn.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute(f'SELECT COUNT(*) AS c FROM "{table}"')
        row = cur.fetchone()
        return int((row or {}).get('c') or 0)


def compare_tables(sqlite_path: str, postgres_dsn: str, tables: Iterable[str]) -> int:
    sqlite_conn = sqlite3.connect(sqlite_path)
    pg_conn = psycopg2.connect(postgres_dsn)
    mismatch = 0
    try:
        for table in tables:
            s_count = sqlite_count(sqlite_conn, table)
            p_count = postgres_count(pg_conn, table)
            mark = 'OK' if s_count == p_count else 'MISMATCH'
            print(f'- {table}: sqlite={s_count} postgres={p_count} [{mark}]')
            if s_count != p_count:
                mismatch += 1
    finally:
        sqlite_conn.close()
        pg_conn.close()
    return mismatch


def main() -> int:
    parser = argparse.ArgumentParser(description='SQLite/PostgreSQL 핵심 테이블 건수 비교')
    parser.add_argument('--sqlite', required=True)
    parser.add_argument('--postgres-dsn', required=True)
    args = parser.parse_args()

    mismatch = compare_tables(args.sqlite, args.postgres_dsn, CORE_TABLES)
    if mismatch:
        print(f'mismatch tables: {mismatch}')
        return 2
    print('all core tables matched')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
