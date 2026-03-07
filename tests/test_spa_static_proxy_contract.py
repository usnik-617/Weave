from __future__ import annotations


def test_spa_root_uses_no_store_cache(client):
    response = client.get("/")

    assert response.status_code == 200
    cache_control = (response.headers.get("Cache-Control") or "").lower()
    assert "no-store" in cache_control


def test_static_asset_uses_asset_cache_policy(client):
    response = client.get("/styles.css")

    assert response.status_code == 200
    cache_control = (response.headers.get("Cache-Control") or "").lower()
    assert "max-age=3600" in cache_control


def test_spa_proxy_blocks_sensitive_suffix(client):
    response = client.get("/server.py")

    assert response.status_code == 403


def test_spa_proxy_rejects_api_like_paths(client):
    response = client.get("/api/anything")

    assert response.status_code == 404


def test_spa_proxy_fallback_is_shell_with_no_store_cache(client):
    response = client.get("/unknown/deep/path")

    assert response.status_code == 200
    cache_control = (response.headers.get("Cache-Control") or "").lower()
    assert "no-store" in cache_control


def test_spa_proxy_blocks_encoded_path_traversal(client):
    response = client.get("/%2e%2e/%2e%2e/weave.db")

    assert response.status_code == 403


def test_spa_proxy_blocks_windows_encoded_traversal(client):
    response = client.get("/%2e%2e%5c%2e%2e%5cweave.db")

    assert response.status_code == 403


def test_spa_proxy_respects_runtime_sensitive_suffix_config(client):
    client.application.config["SPA_SENSITIVE_SUFFIXES"] = (".custom",)

    blocked = client.get("/secrets.custom")
    allowed = client.get("/secrets.py")

    assert blocked.status_code == 403
    assert allowed.status_code == 200


def test_spa_proxy_static_alias_can_be_disabled(client):
    client.application.config["SPA_ALLOW_STATIC_ALIAS"] = False

    response = client.get("/static/styles.css")

    assert response.status_code == 200
    cache_control = (response.headers.get("Cache-Control") or "").lower()
    assert "no-store" in cache_control


def test_spa_proxy_static_alias_can_be_enabled(client):
    client.application.config["SPA_ALLOW_STATIC_ALIAS"] = True

    response = client.get("/static/styles.css")

    assert response.status_code == 200
    cache_control = (response.headers.get("Cache-Control") or "").lower()
    assert "max-age=3600" in cache_control
