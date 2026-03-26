from __future__ import annotations

import logging
import os
import sqlite3
import shutil


logger = logging.getLogger("weave.runtime_bootstrap")


def directory_has_files(path: str) -> bool:
    if not path or not os.path.isdir(path):
        return False
    for _, _, files in os.walk(path):
        if files:
            return True
    return False


def sqlite_db_looks_blank(path: str) -> bool:
    if not path or not os.path.isfile(path):
        return True
    try:
        conn = sqlite3.connect(path)
        tables = {
            row[0]
            for row in conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            ).fetchall()
        }
        if "users" not in tables or "posts" not in tables:
            conn.close()
            return True
        user_count = int(conn.execute("SELECT COUNT(*) FROM users").fetchone()[0] or 0)
        post_count = int(conn.execute("SELECT COUNT(*) FROM posts").fetchone()[0] or 0)
        conn.close()
        return post_count == 0 and user_count <= 1
    except Exception:
        return False


def bootstrap_runtime_snapshot(
    db_path: str,
    upload_dir: str,
    snapshot_dir: str,
    database_url: str = "",
) -> dict:
    result = {
        "db_copied": False,
        "uploads_copied": False,
        "snapshot_dir": snapshot_dir,
    }
    if str(database_url or "").strip().lower().startswith("postgres"):
        return result
    if not snapshot_dir or not os.path.isdir(snapshot_dir):
        return result

    snapshot_db = os.path.join(snapshot_dir, "weave.db")
    snapshot_uploads = os.path.join(snapshot_dir, "uploads")

    db_missing_or_blank = not os.path.exists(db_path) or sqlite_db_looks_blank(db_path)
    if db_path and os.path.isfile(snapshot_db) and db_missing_or_blank:
        os.makedirs(os.path.dirname(db_path), exist_ok=True)
        shutil.copy2(snapshot_db, db_path)
        result["db_copied"] = True
        logger.info("runtime_snapshot db restored from %s", snapshot_db)

    uploads_missing = not os.path.isdir(upload_dir) or not directory_has_files(upload_dir)
    if upload_dir and os.path.isdir(snapshot_uploads) and uploads_missing:
        os.makedirs(upload_dir, exist_ok=True)
        shutil.copytree(snapshot_uploads, upload_dir, dirs_exist_ok=True)
        result["uploads_copied"] = True
        logger.info("runtime_snapshot uploads restored from %s", snapshot_uploads)

    return result
