from __future__ import annotations

import sys
from pathlib import Path


def test_runtime_does_not_import_legacy_handlers_by_default():
    import weave  # noqa: F401
    from weave import create_app

    app = create_app()
    assert app is not None
    assert "weave.legacy_handlers" not in sys.modules


def test_no_route_module_imports_legacy_handlers():
    weave_dir = Path(__file__).resolve().parents[1] / "weave"
    route_files = sorted(weave_dir.glob("*_routes.py"))
    offenders = []
    for file_path in route_files:
        text = file_path.read_text(encoding="utf-8")
        if "legacy_handlers" in text:
            offenders.append(file_path.name)

    assert offenders == []
