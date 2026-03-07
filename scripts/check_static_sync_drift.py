from __future__ import annotations

import hashlib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
STATIC = ROOT / "static"

SYNC_PAIRS = [
    (STATIC / "index.html", ROOT / "index.html"),
    (STATIC / "styles.css", ROOT / "styles.css"),
    (STATIC / "js" / "app-core.js", ROOT / "js" / "app-core.js"),
    (STATIC / "js" / "app-comments.js", ROOT / "js" / "app-comments.js"),
    (STATIC / "js" / "app-editor-upload.js", ROOT / "js" / "app-editor-upload.js"),
    (STATIC / "js" / "app-activities-ops.js", ROOT / "js" / "app-activities-ops.js"),
    (STATIC / "js" / "app-calendar-events.js", ROOT / "js" / "app-calendar-events.js"),
    (STATIC / "js" / "app-news-gallery.js", ROOT / "js" / "app-news-gallery.js"),
    (STATIC / "js" / "app-inline-helpers.js", ROOT / "js" / "app-inline-helpers.js"),
]


def sha256(path: Path) -> str:
    data = path.read_bytes()
    return hashlib.sha256(data).hexdigest()


def main() -> int:
    mismatches: list[str] = []
    for src, dst in SYNC_PAIRS:
        if not src.exists() or not dst.exists():
            mismatches.append(f"missing pair: {src} <-> {dst}")
            continue
        if sha256(src) != sha256(dst):
            mismatches.append(f"out of sync: {src.relative_to(ROOT)} != {dst.relative_to(ROOT)}")

    if mismatches:
        print("Static/root mirror drift detected.")
        print("Run: python scripts/sync_static_root.py")
        for item in mismatches:
            print(f"- {item}")
        return 1

    print("Static/root mirror is in sync.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
