import argparse
import sqlite3
from pathlib import Path


def sqlite_restore(backup_path: Path, target_db: Path):
    if not backup_path.exists():
        raise FileNotFoundError(f"백업 파일이 없습니다: {backup_path}")
    target_db.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(backup_path) as source:
        with sqlite3.connect(target_db) as target:
            source.backup(target)


def main():
    parser = argparse.ArgumentParser(description="SQLite DB 복구")
    parser.add_argument("--backup", required=True, help="복구할 백업 파일 경로")
    parser.add_argument("--target", required=True, help="대상 DB 경로")
    args = parser.parse_args()

    backup_path = Path(args.backup)
    target_db = Path(args.target)

    sqlite_restore(backup_path, target_db)
    print(f"복구 완료: {backup_path} -> {target_db}")


if __name__ == "__main__":
    main()
