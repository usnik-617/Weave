from __future__ import annotations

from pathlib import Path
import re
import sys


ROOT = Path(__file__).resolve().parents[1]
SPA_PATH = ROOT / "weave" / "spa.py"
INDEX_PATH = ROOT / "static" / "index.html"
CONTRACT_TEST_PATH = ROOT / "tests" / "test_spa_static_proxy_contract.py"


def fail(message: str) -> None:
    print(f"[cache-check] FAIL: {message}")
    raise SystemExit(1)


def assert_contains(text: str, pattern: str, label: str) -> None:
    if pattern not in text:
        fail(f"{label} missing: {pattern}")


def main() -> None:
    if not SPA_PATH.exists():
        fail(f"spa.py not found: {SPA_PATH}")
    if not INDEX_PATH.exists():
        fail(f"index.html not found: {INDEX_PATH}")

    spa_text = SPA_PATH.read_text(encoding="utf-8")
    index_text = INDEX_PATH.read_text(encoding="utf-8")

    # Static strategy contracts in runtime shell builder.
    assert_contains(spa_text, 'def _public_asset_version(', "asset hash function")
    assert_contains(spa_text, 'def _version_local_asset_urls(', "asset URL versioning function")
    assert_contains(spa_text, 'name="weave-asset-version"', "asset version marker injection")
    assert_contains(spa_text, '"SPA_HTML_CACHE_CONTROL", "no-store"', "HTML no-store policy")
    assert_contains(spa_text, '"SPA_ASSET_CACHE_CONTROL", "public, max-age=3600"', "asset max-age policy")
    assert_contains(spa_text, '"SPA_SW_CACHE_CONTROL", "no-cache, no-store, must-revalidate"', "SW cache policy")

    # index shell should reference local assets through src/href so runtime versioning can rewrite them.
    if not re.search(r'src="js/app-auth-init\.js"', index_text):
        fail("static/index.html must include js/app-auth-init.js for runtime asset version rewriting")
    if "meta name=\"weave-asset-version\"" in index_text:
        fail("static/index.html should not hardcode weave-asset-version meta (injected at runtime)")

    # Guard that contract tests still exist.
    if not CONTRACT_TEST_PATH.exists():
        fail("SPA cache contract test file is missing")
    contract_text = CONTRACT_TEST_PATH.read_text(encoding="utf-8")
    assert_contains(contract_text, 'name="weave-asset-version"', "contract test meta marker assertion")
    assert_contains(contract_text, "app-auth-init.js?v=", "contract test versioned asset assertion")

    print("[cache-check] PASS: cache key/static hash strategy contract is healthy.")


if __name__ == "__main__":
    try:
        main()
    except Exception as error:  # pragma: no cover
        print(f"[cache-check] FAIL: {error}")
        sys.exit(1)
