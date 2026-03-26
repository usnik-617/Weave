from __future__ import annotations

import os
import shutil
from pathlib import Path


BASE_DIR = Path(__file__).resolve().parents[1]
SOURCE_DB = BASE_DIR / "weave.db"
SOURCE_UPLOADS = BASE_DIR / "uploads"
SNAPSHOT_DIR = BASE_DIR / "storage" / "runtime_snapshot"
SNAPSHOT_DB = SNAPSHOT_DIR / "weave.db"
SNAPSHOT_UPLOADS = SNAPSHOT_DIR / "uploads"


def main() -> int:
    SNAPSHOT_DIR.mkdir(parents=True, exist_ok=True)

    if not SOURCE_DB.exists():
        raise FileNotFoundError(f"source db not found: {SOURCE_DB}")
    shutil.copy2(SOURCE_DB, SNAPSHOT_DB)

    if SNAPSHOT_UPLOADS.exists():
        shutil.rmtree(SNAPSHOT_UPLOADS)
    if SOURCE_UPLOADS.exists():
        shutil.copytree(SOURCE_UPLOADS, SNAPSHOT_UPLOADS)
    else:
        SNAPSHOT_UPLOADS.mkdir(parents=True, exist_ok=True)

    upload_count = 0
    upload_bytes = 0
    for root, _, files in os.walk(SNAPSHOT_UPLOADS):
        for name in files:
            upload_count += 1
            upload_bytes += (Path(root) / name).stat().st_size

    print(
        {
            "snapshot_db": str(SNAPSHOT_DB),
            "snapshot_db_bytes": SNAPSHOT_DB.stat().st_size,
            "snapshot_upload_count": upload_count,
            "snapshot_upload_bytes": upload_bytes,
        }
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
