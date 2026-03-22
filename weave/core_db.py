from __future__ import annotations

import re
import time
from contextlib import contextmanager
from functools import wraps

from weave import core


class PgRow(dict):
    pass


def _is_postgres_mode() -> bool:
    return str(core.DATABASE_URL or "").strip().lower().startswith("postgres")


def _convert_qmark_to_pyformat(sql: str) -> str:
    text = str(sql or "")
    out = []
    in_single = False
    i = 0
    while i < len(text):
        ch = text[i]
        if ch == "'":
            in_single = not in_single
            out.append(ch)
            i += 1
            continue
        if ch == "?" and not in_single:
            out.append("%s")
            i += 1
            continue
        out.append(ch)
        i += 1
    converted = "".join(out)
    converted = converted.replace("date('now')", "CURRENT_DATE")
    converted = converted.replace("date('now', '+7 day')", "(CURRENT_DATE + INTERVAL '7 day')::date")
    converted = converted.replace("datetime('now')", "CURRENT_TIMESTAMP")
    converted = converted.replace("substr(", "substring(")
    converted = converted.replace(",1,7)", " from 1 for 7)")
    return converted


class PostgresCursorAdapter:
    def __init__(self, conn, cursor):
        self._conn = conn
        self._cursor = cursor
        self.lastrowid = None

    def execute(self, sql, params=None):
        converted = _convert_qmark_to_pyformat(sql)
        payload = tuple(params or [])
        self._cursor.execute(converted, payload)
        lowered = str(converted or "").strip().lower()
        if lowered.startswith("insert") and " returning " not in lowered:
            try:
                self._cursor.execute("SELECT LASTVAL() AS id")
                row = self._cursor.fetchone()
                self.lastrowid = int((row or {}).get("id") or 0)
            except Exception:
                self.lastrowid = None
        return self

    def fetchone(self):
        row = self._cursor.fetchone()
        if row is None:
            return None
        return PgRow(dict(row))

    def fetchall(self):
        rows = self._cursor.fetchall() or []
        return [PgRow(dict(row)) for row in rows]

    def __iter__(self):
        for row in self.fetchall():
            yield row

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        self.close()

    def close(self):
        try:
            self._cursor.close()
        except Exception:
            return


class PostgresConnectionAdapter:
    def __init__(self, conn):
        self._conn = conn

    def execute(self, sql, params=None):
        cur = self.cursor()
        cur.execute(sql, params)
        return cur

    def cursor(self):
        from psycopg2.extras import RealDictCursor  # type: ignore

        return PostgresCursorAdapter(self, self._conn.cursor(cursor_factory=RealDictCursor))

    def commit(self):
        return self._conn.commit()

    def rollback(self):
        return self._conn.rollback()

    def close(self):
        return self._conn.close()


def get_db_connection():
    if not _is_postgres_mode():
        conn = core.sqlite3.connect(core.DB_PATH, timeout=10)
        conn.row_factory = core.sqlite3.Row
        conn.execute("PRAGMA busy_timeout = 10000")
        conn.execute("PRAGMA foreign_keys = ON")
        return conn

    try:
        import psycopg2  # type: ignore
    except Exception as exc:  # pragma: no cover
        raise RuntimeError("PostgreSQL 모드에는 psycopg2-binary가 필요합니다.") from exc

    raw = psycopg2.connect(core.DATABASE_URL)
    raw.autocommit = False
    return PostgresConnectionAdapter(raw)


def db_write_retry(func):
    @wraps(func)
    def wrapper(*args, **kwargs):
        last_error = None
        for attempt in range(3):
            try:
                return func(*args, **kwargs)
            except Exception as exc:
                text = str(exc).lower()
                is_retryable = (
                    "database is locked" in text
                    or "deadlock detected" in text
                    or "could not serialize access" in text
                )
                if not is_retryable:
                    raise
                last_error = exc
                time.sleep(0.1 * (attempt + 1))
        if last_error:
            raise last_error

    return wrapper


@contextmanager
def transaction(conn):
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
