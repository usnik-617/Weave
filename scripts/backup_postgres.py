from __future__ import annotations

import argparse
import datetime as dt
import os
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_BACKUP_DIR = Path(os.environ.get('WEAVE_PG_BACKUP_DIR', str(ROOT / 'backups' / 'postgres')))


def main() -> int:
    parser = argparse.ArgumentParser(description='PostgreSQL pg_dump 백업 실행')
    parser.add_argument('--dsn', default=os.environ.get('DATABASE_URL', ''))
    parser.add_argument('--backup-dir', default=str(DEFAULT_BACKUP_DIR))
    parser.add_argument('--label', default='weave')
    args = parser.parse_args()

    dsn = str(args.dsn or '').strip()
    if not dsn.lower().startswith('postgres'):
        raise SystemExit('DATABASE_URL 또는 --dsn 에 PostgreSQL DSN이 필요합니다.')

    backup_dir = Path(args.backup_dir)
    backup_dir.mkdir(parents=True, exist_ok=True)
    stamp = dt.datetime.now().strftime('%Y%m%d-%H%M%S')
    target = backup_dir / f"{args.label}-{stamp}.dump"

    cmd = ['pg_dump', '--format=custom', '--file', str(target), dsn]
    completed = subprocess.run(cmd, check=False)
    if completed.returncode != 0:
        raise SystemExit(completed.returncode)
    print(f'백업 완료: {target}')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
