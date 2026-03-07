from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_TARGETS = [
    ROOT / "static" / "js",
    ROOT / "static" / "index.html",
    ROOT / "static" / "styles.css",
]
ALERT_PATTERN = re.compile(r"\balert\s*\(")
MOJIBAKE_MARKERS = ("�",)


def iter_targets(argv: list[str]) -> list[Path]:
    if argv:
        return [Path(item).resolve() for item in argv]
    return DEFAULT_TARGETS


def iter_files(targets: list[Path]) -> list[Path]:
    files: list[Path] = []
    for target in targets:
        if target.is_dir():
            files.extend(sorted(target.rglob("*")))
        elif target.is_file():
            files.append(target)
    return [path for path in files if path.suffix.lower() in {".js", ".html", ".css"}]


def main(argv: list[str]) -> int:
    failures: list[str] = []
    for file_path in iter_files(iter_targets(argv)):
        try:
            text = file_path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            failures.append(f"{file_path}: non-utf8 encoding")
            continue

        if ALERT_PATTERN.search(text):
            failures.append(f"{file_path}: uses alert(); use notifyMessage/notifyError")

        if any(marker in text for marker in MOJIBAKE_MARKERS):
            failures.append(f"{file_path}: suspicious mojibake marker detected")

    if failures:
        print("Frontend guardrail check failed:")
        for item in failures:
            print(f"- {item}")
        return 1

    print("Frontend guardrail check passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
