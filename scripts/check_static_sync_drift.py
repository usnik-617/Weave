from __future__ import annotations

import hashlib
from pathlib import Path

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


def sha256(path: Path) -> str:
    data = path.read_bytes()
    return hashlib.sha256(data).hexdigest()


def main() -> int:
    mismatches: list[str] = []
    for src, dst in build_sync_pairs():
        if not src.exists() or not dst.exists():
            mismatches.append(f"missing pair: {src} <-> {dst}")
            continue
        src_hash = sha256(src)
        dst_hash = sha256(dst)
        if src_hash != dst_hash:
            mismatches.append(
                "out of sync: "
                f"{src.relative_to(ROOT)} ({src_hash[:12]}) "
                f"!= {dst.relative_to(ROOT)} ({dst_hash[:12]})"
            )

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
