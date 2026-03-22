from __future__ import annotations
import os


def test_spa_root_uses_no_store_cache(client):
    response = client.get("/")

    assert response.status_code == 200
    cache_control = (response.headers.get("Cache-Control") or "").lower()
    assert "no-store" in cache_control


def test_static_asset_uses_asset_cache_policy(client):
    response = client.get("/styles.css")

    assert response.status_code == 200
    assert response.headers.get("X-Weave-Asset-Source") in {"static", "root-mirror"}
    cache_control = (response.headers.get("Cache-Control") or "").lower()
    assert "max-age=3600" in cache_control


def test_sw_asset_uses_dedicated_cache_policy(client):
    response = client.get("/sw.js")

    assert response.status_code == 200
    cache_control = (response.headers.get("Cache-Control") or "").lower()
    assert "no-store" in cache_control


def test_root_injects_asset_version_marker(client):
    response = client.get("/")
    body = response.get_data(as_text=True)

    assert response.status_code == 200
    assert 'name="weave-asset-version"' in body
    assert "app-auth-init.js?v=" in body
    assert response.headers.get("X-Weave-Asset-Version")


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


def test_spa_proxy_static_alias_is_disabled_by_default(client):
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


def test_csp_report_only_header_is_present(client):
    response = client.get("/")

    assert response.status_code == 200
    assert response.headers.get("Content-Security-Policy")
    assert response.headers.get("Content-Security-Policy-Report-Only")


def test_root_mirror_file_wins_when_newer(client):
    root_path = os.path.join(client.application.root_path, "..", "js", "app-auth-init.js")
    root_path = os.path.realpath(root_path)

    root_mtime = os.path.getmtime(root_path)
    try:
        os.utime(root_path, (root_mtime + 5, root_mtime + 5))
        response = client.get("/js/app-auth-init.js")
        body = response.get_data(as_text=True)
        assert response.status_code == 200
        assert "navigator.serviceWorker.register(swUrl)" in body
    finally:
        os.utime(root_path, (root_mtime, root_mtime))
