#!/usr/bin/env python
from __future__ import annotations

import argparse
import sqlite3
from typing import List

import psycopg2
from psycopg2.extras import execute_batch


def map_sqlite_type_to_pg(sqlite_type: str) -> str:
    t = str(sqlite_type or "").strip().upper()
    if "INT" in t:
        return "BIGINT"
    if any(token in t for token in ("CHAR", "CLOB", "TEXT")):
        return "TEXT"
    if "BLOB" in t:
        return "BYTEA"
    if any(token in t for token in ("REAL", "FLOA", "DOUB")):
        return "DOUBLE PRECISION"
    return "TEXT"


def load_tables(sqlite_conn: sqlite3.Connection) -> List[str]:
    rows = sqlite_conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%' ORDER BY name"
    ).fetchall()
    return [str(row[0]) for row in rows]


def migrate_table(sqlite_conn: sqlite3.Connection, pg_conn, table_name: str):
    pragma_rows = sqlite_conn.execute(f"PRAGMA table_info({table_name})").fetchall()
    columns = [str(row[1]) for row in pragma_rows]
    col_defs = []
    for row in pragma_rows:
        col = str(row[1])
        is_pk = int(row[5] or 0) == 1
        if is_pk and col == "id":
            col_defs.append('"id" BIGSERIAL PRIMARY KEY')
            continue
        typ = map_sqlite_type_to_pg(str(row[2]))
        nullable = "NOT NULL" if int(row[3] or 0) else ""
        col_defs.append(f'"{col}" {typ} {nullable}'.strip())

    ddl = f'CREATE TABLE IF NOT EXISTS "{table_name}" ({", ".join(col_defs)})'
    with pg_conn.cursor() as cur:
        cur.execute(ddl)

    rows = sqlite_conn.execute(f'SELECT {", ".join([f"\"{c}\"" for c in columns])} FROM "{table_name}"').fetchall()
    if not rows:
        pg_conn.commit()
        return

    placeholders = ", ".join(["%s"] * len(columns))
    sql = f'INSERT INTO "{table_name}" ({", ".join([f"\"{c}\"" for c in columns])}) VALUES ({placeholders})'
    with pg_conn.cursor() as cur:
        execute_batch(cur, sql, rows, page_size=500)
        if "id" in columns:
            cur.execute(
                f"SELECT setval(pg_get_serial_sequence('\"{table_name}\"', 'id'), COALESCE((SELECT MAX(id) FROM \"{table_name}\"), 1), true)"
            )
    pg_conn.commit()


def main():
    parser = argparse.ArgumentParser(description="Migrate SQLite data to PostgreSQL")
    parser.add_argument("--sqlite", required=True, help="SQLite DB path")
    parser.add_argument("--postgres-dsn", required=True, help="PostgreSQL DSN")
    args = parser.parse_args()

    sqlite_conn = sqlite3.connect(args.sqlite)
    sqlite_conn.row_factory = sqlite3.Row
    pg_conn = psycopg2.connect(args.postgres_dsn)

    try:
        tables = load_tables(sqlite_conn)
        for table in tables:
            migrate_table(sqlite_conn, pg_conn, table)
            print(f"migrated: {table}")
    finally:
        sqlite_conn.close()
        pg_conn.close()


if __name__ == "__main__":
    main()
