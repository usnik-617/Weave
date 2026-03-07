from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CSS_FILE = ROOT / "static" / "styles.css"


def normalize_selector(selector: str) -> str:
    return " ".join(selector.split())


def normalize_body(body: str) -> str:
    lines = [line.strip() for line in body.splitlines() if line.strip()]
    return "\n".join(lines)


def iter_top_level_blocks(text: str):
    depth = 0
    selector_start = 0
    body_start = -1
    selector = ""

    for idx, ch in enumerate(text):
        if ch == "{":
            if depth == 0:
                selector = text[selector_start:idx]
                body_start = idx + 1
            depth += 1
            continue

        if ch == "}":
            depth -= 1
            if depth == 0 and body_start >= 0:
                body = text[body_start:idx]
                yield selector, body
                selector_start = idx + 1
                body_start = -1
            continue

        if depth == 0 and ch == "\n":
            selector_start = idx + 1


def main() -> int:
    text = CSS_FILE.read_text(encoding="utf-8")
    seen: dict[tuple[str, str], int] = {}
    duplicates: list[str] = []

    for idx, (raw_selector, raw_body) in enumerate(iter_top_level_blocks(text), start=1):
        selector = normalize_selector(raw_selector)
        body = normalize_body(raw_body)
        if not selector or not body or selector.startswith("@"):
            continue
        key = (selector, body)
        if key in seen:
            duplicates.append(f"duplicate block: {selector}")
        else:
            seen[key] = idx

    if duplicates:
        print("Duplicate CSS blocks detected:")
        for item in duplicates:
            print(f"- {item}")
        return 1

    print("No duplicate CSS blocks detected.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
