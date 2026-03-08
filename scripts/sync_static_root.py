from __future__ import annotations

from pathlib import Path
import shutil

ROOT = Path(__file__).resolve().parents[1]
STATIC = ROOT / "static"

BASE_SYNC_PAIRS = [
    (STATIC / "index.html", ROOT / "index.html"),
    (STATIC / "styles.css", ROOT / "styles.css"),
    (STATIC / "js" / "app-core.js", ROOT / "js" / "app-core.js"),
    (STATIC / "js" / "app-comments.js", ROOT / "js" / "app-comments.js"),
    (STATIC / "js" / "app-editor-upload.js", ROOT / "js" / "app-editor-upload.js"),
    (STATIC / "js" / "app-activities-ops.js", ROOT / "js" / "app-activities-ops.js"),
    (STATIC / "js" / "app-calendar-events.js", ROOT / "js" / "app-calendar-events.js"),
    (STATIC / "js" / "app-news-gallery.js", ROOT / "js" / "app-news-gallery.js"),
    (STATIC / "js" / "app-inline-helpers.js", ROOT / "js" / "app-inline-helpers.js"),
    (STATIC / "js" / "app-main.js", ROOT / "js" / "app-main.js"),
    (STATIC / "js" / "app-auth-init.js", ROOT / "js" / "app-auth-init.js"),
    (STATIC / "js" / "app-navigation-init.js", ROOT / "js" / "app-navigation-init.js"),
    (STATIC / "js" / "app-admin-init.js", ROOT / "js" / "app-admin-init.js"),
    (STATIC / "js" / "app-site-editor-config.js", ROOT / "js" / "app-site-editor-config.js"),
    (STATIC / "js" / "app-site-editor-core.js", ROOT / "js" / "app-site-editor-core.js"),
    (STATIC / "js" / "app-site-editor-sanitize.js", ROOT / "js" / "app-site-editor-sanitize.js"),
]


def discover_js_pairs() -> list[tuple[Path, Path]]:
    pairs: list[tuple[Path, Path]] = []
    root_js = ROOT / "js"
    static_js = STATIC / "js"
    if not root_js.exists() or not static_js.exists():
        return pairs
    for root_file in sorted(root_js.glob("app-*.js")):
        static_file = static_js / root_file.name
        pairs.append((static_file, root_file))
    return pairs


def build_sync_pairs() -> list[tuple[Path, Path]]:
    merged = list(BASE_SYNC_PAIRS)
    known = {(src, dst) for src, dst in merged}
    for src, dst in discover_js_pairs():
        if (src, dst) not in known:
            merged.append((src, dst))
    return merged


def sync() -> None:
    for src, dst in build_sync_pairs():
        if not src.exists():
            raise FileNotFoundError(f"Missing source file: {src}")
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dst)
        print(f"synced: {src.relative_to(ROOT)} -> {dst.relative_to(ROOT)}")


if __name__ == "__main__":
    sync()
