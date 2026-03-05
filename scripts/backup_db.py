import argparse
import os
import sqlite3
from datetime import datetime, timedelta
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parents[1]
DEFAULT_DB_PATH = os.environ.get("WEAVE_DB_PATH", str(BASE_DIR / "weave.db"))
DEFAULT_BACKUP_DIR = os.environ.get("WEAVE_BACKUP_DIR", str(BASE_DIR / "backups"))


def sqlite_backup(src_db: Path, dest_db: Path):
    dest_db.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(src_db) as source:
        with sqlite3.connect(dest_db) as target:
            source.backup(target)


def rotate_backups(backup_dir: Path):
    now = datetime.now()
    daily_files = sorted(
        backup_dir.glob("daily-*.db"), key=lambda p: p.name, reverse=True
    )
    weekly_files = sorted(
        backup_dir.glob("weekly-*.db"), key=lambda p: p.name, reverse=True
    )

    for old in daily_files[7:]:
        old.unlink(missing_ok=True)
    for old in weekly_files[4:]:
        old.unlink(missing_ok=True)

    # 추가 안전장치: 날짜 기준 삭제
    threshold_daily = now - timedelta(days=7)
    threshold_weekly = now - timedelta(days=28)
    for file in backup_dir.glob("daily-*.db"):
        if datetime.fromtimestamp(file.stat().st_mtime) < threshold_daily:
            file.unlink(missing_ok=True)
    for file in backup_dir.glob("weekly-*.db"):
        if datetime.fromtimestamp(file.stat().st_mtime) < threshold_weekly:
            file.unlink(missing_ok=True)


def main():
    parser = argparse.ArgumentParser(description="SQLite DB 백업 및 회전")
    parser.add_argument("--db-path", default=DEFAULT_DB_PATH)
    parser.add_argument("--backup-dir", default=DEFAULT_BACKUP_DIR)
    args = parser.parse_args()

    db_path = Path(args.db_path)
    backup_dir = Path(args.backup_dir)
    backup_dir.mkdir(parents=True, exist_ok=True)

    if not db_path.exists():
        raise FileNotFoundError(f"DB 파일을 찾을 수 없습니다: {db_path}")

    now = datetime.now()
    daily_name = f"daily-{now.strftime('%Y%m%d')}.db"
    iso = now.isocalendar()
    weekly_name = f"weekly-{iso.year}-W{iso.week:02d}.db"

    daily_path = backup_dir / daily_name
    weekly_path = backup_dir / weekly_name

    sqlite_backup(db_path, daily_path)
    sqlite_backup(db_path, weekly_path)
    rotate_backups(backup_dir)

    print(f"백업 완료: {daily_path}")
    print(f"백업 완료: {weekly_path}")


if __name__ == "__main__":
    main()
