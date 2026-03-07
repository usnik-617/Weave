from __future__ import annotations

from pathlib import Path


def test_route_modules_do_not_use_direct_ok_jsonify_errors():
    root = Path(__file__).resolve().parents[1] / "weave"
    route_files = sorted(root.glob("*_routes.py"))
    offenders = []
    for file_path in route_files:
        text = file_path.read_text(encoding="utf-8")
        if 'jsonify({"ok": False' in text:
            offenders.append(str(file_path.name))

    assert offenders == []
