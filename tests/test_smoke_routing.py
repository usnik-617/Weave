from __future__ import annotations

from pathlib import Path

import pytest


@pytest.fixture()
def client(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    db_path = tmp_path / "test_smoke.db"
    monkeypatch.setenv("WEAVE_DB_PATH", str(db_path))
    monkeypatch.delenv("WEAVE_HEALTH_TOKEN", raising=False)
    monkeypatch.delenv("WEAVE_HEALTH_ALLOW_IPS", raising=False)

    import weave.core as core
    from weave import create_app

    core.DB_PATH = str(db_path)
    core.DATABASE_URL = f"sqlite:///{db_path}"

    app = create_app()
    app.config.update(TESTING=True)

    with app.test_client() as test_client:
        yield test_client


def _has_index_marker(text: str) -> bool:
    lowered = text.lower()
    return "<!doctype" in lowered or "<html" in lowered


def test_root_serves_index(client):
    response = client.get("/")
    body = response.get_data(as_text=True)

    assert response.status_code == 200
    assert _has_index_marker(body)


def test_spa_fallback_serves_index(client):
    response = client.get("/some/spa/route")
    body = response.get_data(as_text=True)

    assert response.status_code == 200
    assert _has_index_marker(body)


def test_api_not_swallowed_by_spa(client):
    response = client.get("/api/this-should-not-exist")
    body = response.get_data(as_text=True)

    assert response.status_code == 404
    assert not _has_index_marker(body)


def test_healthz_works(client):
    response = client.get("/healthz")

    assert response.status_code == 200
    payload = response.get_json() or {}
    assert isinstance(payload, dict)
    assert payload.get("success") is True

    data = payload.get("data") or {}
    assert data.get("status") in {"healthy", "ok"}


def test_metrics_route_behavior(client):
    response = client.get("/metrics")
    body = response.get_data(as_text=True)

    assert response.status_code in {200, 401, 403}
    assert not _has_index_marker(body)


def test_no_duplicate_route_method_mappings(client):
    duplicates = []
    route_map = {}

    for rule in client.application.url_map.iter_rules():
        methods = tuple(
            sorted(
                method
                for method in (rule.methods or set())
                if method not in {"HEAD", "OPTIONS"}
            )
        )
        if not methods:
            continue

        key = (rule.rule, methods)
        endpoint = rule.endpoint
        route_map.setdefault(key, []).append(endpoint)

    for (rule, methods), endpoints in route_map.items():
        if len(endpoints) > 1:
            duplicates.append(
                {
                    "rule": rule,
                    "methods": methods,
                    "endpoints": endpoints,
                }
            )

    assert duplicates == [], f"duplicate route mappings found: {duplicates}"
