from __future__ import annotations

import time
from functools import wraps

from weave import core


def get_db_connection():
    conn = core.sqlite3.connect(core.DB_PATH, timeout=10)
    conn.row_factory = core.sqlite3.Row
    conn.execute("PRAGMA busy_timeout = 10000")
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def db_write_retry(func):
    @wraps(func)
    def wrapper(*args, **kwargs):
        last_error = None
        for attempt in range(3):
            try:
                return func(*args, **kwargs)
            except core.sqlite3.OperationalError as exc:
                if "database is locked" not in str(exc).lower():
                    raise
                last_error = exc
                time.sleep(0.1 * (attempt + 1))
        if last_error:
            raise last_error

    return wrapper
