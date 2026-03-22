from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
STATIC = ROOT / "static"

SYNC_PAIRS = [
    (STATIC / "index.html", ROOT / "index.html"),
    (STATIC / "styles.css", ROOT / "styles.css"),
]


def discover_js_pairs() -> list[tuple[Path, Path]]:
    pairs: list[tuple[Path, Path]] = []
    root_js = ROOT / "js"
    static_js = STATIC / "js"
    if not root_js.exists() or not static_js.exists():
        return pairs
    for root_file in sorted(root_js.glob("app-*.js")):
        pairs.append((static_js / root_file.name, root_file))
    return pairs


def main() -> int:
    violations: list[str] = []
    pairs = [*SYNC_PAIRS, *discover_js_pairs()]
    for static_file, root_file in pairs:
        if not static_file.exists() or not root_file.exists():
            continue
        static_mtime = static_file.stat().st_mtime
        root_mtime = root_file.stat().st_mtime
        if root_mtime > static_mtime:
            violations.append(
                f"{root_file.relative_to(ROOT)} is newer than {static_file.relative_to(ROOT)}"
            )

    if violations:
        print("Canonical source violation: static/* must be the editable source of truth.")
        print("Fix: edit static/* then run `python scripts/sync_static_root.py`.")
        for violation in violations:
            print(f"- {violation}")
        return 1

    print("Canonical source rule passed (static/* is authoritative).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
