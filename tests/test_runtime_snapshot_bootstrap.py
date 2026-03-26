from __future__ import annotations

import shutil
import uuid
from pathlib import Path

from weave.runtime_bootstrap import bootstrap_runtime_snapshot


def _make_local_test_root() -> Path:
    root = (
        Path(__file__).resolve().parents[1]
        / "instance"
        / "pytest_runtime"
        / uuid.uuid4().hex
    )
    root.mkdir(parents=True, exist_ok=True)
    return root


def test_bootstrap_runtime_snapshot_restores_missing_db_and_uploads():
    root = _make_local_test_root()
    try:
        snapshot_dir = root / "snapshot"
        snapshot_uploads = snapshot_dir / "uploads" / "2026" / "03"
        snapshot_uploads.mkdir(parents=True, exist_ok=True)
        (snapshot_dir / "weave.db").write_bytes(b"seed-db")
        (snapshot_uploads / "sample.txt").write_text("seed-upload", encoding="utf-8")

        db_path = root / "runtime" / "weave.db"
        upload_dir = root / "runtime" / "uploads"

        result = bootstrap_runtime_snapshot(
            str(db_path),
            str(upload_dir),
            str(snapshot_dir),
            "sqlite:///runtime.db",
        )

        assert result["db_copied"] is True
        assert result["uploads_copied"] is True
        assert db_path.read_bytes() == b"seed-db"
        assert (upload_dir / "2026" / "03" / "sample.txt").read_text(encoding="utf-8") == "seed-upload"
    finally:
        shutil.rmtree(root, ignore_errors=True)


def test_bootstrap_runtime_snapshot_does_not_override_existing_runtime_data():
    root = _make_local_test_root()
    try:
        snapshot_dir = root / "snapshot"
        snapshot_uploads = snapshot_dir / "uploads"
        snapshot_uploads.mkdir(parents=True, exist_ok=True)
        (snapshot_dir / "weave.db").write_bytes(b"seed-db")
        (snapshot_uploads / "sample.txt").write_text("seed-upload", encoding="utf-8")

        runtime_dir = root / "runtime"
        runtime_dir.mkdir(parents=True, exist_ok=True)
        db_path = runtime_dir / "weave.db"
        upload_dir = runtime_dir / "uploads"
        upload_dir.mkdir(parents=True, exist_ok=True)
        db_path.write_bytes(b"live-db")
        (upload_dir / "keep.txt").write_text("live-upload", encoding="utf-8")

        result = bootstrap_runtime_snapshot(
            str(db_path),
            str(upload_dir),
            str(snapshot_dir),
            "sqlite:///runtime.db",
        )

        assert result["db_copied"] is False
        assert result["uploads_copied"] is False
        assert db_path.read_bytes() == b"live-db"
        assert (upload_dir / "keep.txt").read_text(encoding="utf-8") == "live-upload"
    finally:
        shutil.rmtree(root, ignore_errors=True)
