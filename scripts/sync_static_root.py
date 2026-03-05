from __future__ import annotations

from pathlib import Path
import shutil

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
]


def sync() -> None:
    for src, dst in SYNC_PAIRS:
        if not src.exists():
            raise FileNotFoundError(f"Missing source file: {src}")
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dst)
        print(f"synced: {src.relative_to(ROOT)} -> {dst.relative_to(ROOT)}")


if __name__ == "__main__":
    sync()
