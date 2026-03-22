import os
import hashlib
import re
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from flask import abort, current_app

from weave.core import BASE_DIR, Response, STATIC_DIR, send_from_directory


VERSIONED_EXTENSIONS = {
    ".css",
    ".js",
    ".png",
    ".jpg",
    ".jpeg",
    ".webp",
    ".gif",
    ".svg",
    ".ico",
    ".json",
    ".avif",
}


def _public_asset_version():
    tracked = []
    candidates = [
        os.path.join(STATIC_DIR, "index.html"),
        os.path.join(STATIC_DIR, "styles.css"),
        os.path.join(STATIC_DIR, "manifest.json"),
        os.path.join(STATIC_DIR, "sw.js"),
    ]
    js_dir = os.path.join(STATIC_DIR, "js")
    if os.path.isdir(js_dir):
        for name in sorted(os.listdir(js_dir)):
            if name.endswith(".js"):
                candidates.append(os.path.join(js_dir, name))

    for candidate in candidates:
        if not os.path.isfile(candidate):
            continue
        stat = os.stat(candidate)
        rel = os.path.relpath(candidate, STATIC_DIR).replace("\\", "/")
        tracked.append(f"{rel}:{int(stat.st_mtime)}:{int(stat.st_size)}")

    return hashlib.sha256("|".join(tracked).encode("utf-8")).hexdigest()[:12]


def _inject_cache_debug_panel(html):
    if not current_app.config.get("WEAVE_DEBUG_CLIENT_CACHE_PANEL", False):
        return html
    script = """
<script>
(() => {
  if (!/localhost|127\\.0\\.0\\.1/i.test(location.hostname)) return;
  const badge = document.createElement('aside');
  badge.setAttribute('aria-live', 'polite');
  badge.style.cssText = 'position:fixed;right:10px;bottom:10px;z-index:99999;padding:8px 10px;border-radius:10px;background:rgba(17,24,39,.88);color:#fff;font:12px/1.4 monospace;box-shadow:0 6px 16px rgba(0,0,0,.3)';
  const v = (document.querySelector('meta[name="weave-asset-version"]') || {}).content || 'n/a';
  const controller = navigator.serviceWorker && navigator.serviceWorker.controller ? 'yes' : 'no';
  badge.textContent = `asset=${v} | sw-controller=${controller}`;
  document.body.appendChild(badge);
})();
</script>
""".strip()
    return html.replace("</body>", f"{script}\n</body>")


def _version_local_asset_urls(html, version):
    marker = re.compile(r"""(?P<attr>src|href)=["'](?P<url>[^"'<>]+)["']""")

    def _replace(match):
        raw_url = str(match.group("url") or "").strip()
        if not raw_url:
            return match.group(0)
        lowered = raw_url.lower()
        if (
            lowered.startswith(("http://", "https://", "//", "data:", "#", "mailto:", "tel:"))
            or "://" in lowered
        ):
            return match.group(0)

        parsed = urlsplit(raw_url)
        path = parsed.path or ""
        _, ext = os.path.splitext(path)
        if ext.lower() not in VERSIONED_EXTENSIONS:
            return match.group(0)

        query = dict(parse_qsl(parsed.query, keep_blank_values=True))
        query["v"] = version
        rewritten = urlunsplit(
            (parsed.scheme, parsed.netloc, path, urlencode(query), parsed.fragment)
        )
        attr = match.group("attr")
        return f'{attr}="{rewritten}"'

    return marker.sub(_replace, html)


def _serve_shell():
    shell_path = os.path.join(STATIC_DIR, "index.html")
    with open(shell_path, "r", encoding="utf-8") as handle:
        html = handle.read()
    version = _public_asset_version()
    html = _version_local_asset_urls(html, version)
    html = html.replace(
        "<head>",
        f'<head>\n  <meta name="weave-asset-version" content="{version}">',
        1,
    )
    html = _inject_cache_debug_panel(html)
    response = Response(html, mimetype="text/html; charset=utf-8")
    response.headers["Cache-Control"] = current_app.config.get(
        "SPA_HTML_CACHE_CONTROL", "no-store"
    )
    response.headers["X-Weave-Asset-Version"] = version
    return response


def root():
    return _serve_shell()


def is_sensitive_path(path):
    lowered = str(path or "").replace("\\", "/").lower().strip("/")
    sensitive_suffixes = current_app.config.get(
        "SPA_SENSITIVE_SUFFIXES", (".db", ".env", ".py", ".sqlite", ".sqlite3")
    )
    segments = [segment for segment in lowered.split("/") if segment]
    if any(segment in {".", ".."} for segment in segments):
        return True
    if any(segment.startswith(".") for segment in segments):
        return True
    if any(segment in {"instance", "__pycache__"} for segment in segments):
        return True
    return lowered.endswith(sensitive_suffixes)


def _normalize_public_path(path):
    text = str(path or "").strip().replace("\\", "/").lstrip("/")
    normalized = os.path.normpath(text).replace("\\", "/")
    return "" if normalized in {"", "."} else normalized.lstrip("/")


def _is_static_file(path):
    static_root = os.path.realpath(STATIC_DIR)
    candidate = os.path.realpath(os.path.join(static_root, path))
    try:
        in_static_root = os.path.commonpath([static_root, candidate]) == static_root
    except ValueError:
        return False
    return in_static_root and os.path.isfile(candidate)


def _is_root_mirror_path(path):
    normalized = _normalize_public_path(path)
    if normalized in {"index.html", "styles.css"}:
        return True
    return normalized.startswith("js/") and normalized.endswith(".js")


def _pick_asset_root(path):
    normalized = _normalize_public_path(path)
    static_candidate = os.path.realpath(os.path.join(STATIC_DIR, normalized))

    if not _is_root_mirror_path(normalized):
        return STATIC_DIR

    mirror_candidate = os.path.realpath(os.path.join(BASE_DIR, normalized))
    if not os.path.isfile(mirror_candidate):
        return STATIC_DIR
    if not os.path.isfile(static_candidate):
        return BASE_DIR

    try:
        mirror_mtime = os.path.getmtime(mirror_candidate)
        static_mtime = os.path.getmtime(static_candidate)
    except OSError:
        return STATIC_DIR

    return BASE_DIR if mirror_mtime > static_mtime else STATIC_DIR


def _serve_static_asset(path):
    asset_root = _pick_asset_root(path)
    response = send_from_directory(asset_root, path)
    response.headers["X-Weave-Asset-Source"] = (
        "root-mirror" if os.path.realpath(asset_root) == os.path.realpath(BASE_DIR) else "static"
    )
    if str(path or "").lower().endswith("sw.js"):
        response.headers["Cache-Control"] = current_app.config.get(
            "SPA_SW_CACHE_CONTROL", "no-cache, no-store, must-revalidate"
        )
    else:
        response.headers["Cache-Control"] = current_app.config.get(
            "SPA_ASSET_CACHE_CONTROL", "public, max-age=3600"
        )
    return response


def static_proxy(path):
    normalized = _normalize_public_path(path)
    if normalized.startswith("api/"):
        abort(404)
    if is_sensitive_path(normalized):
        abort(403)

    if normalized and _is_static_file(normalized):
        return _serve_static_asset(normalized)

    # Optional compatibility alias for older frontend links that still use /static/*.
    allow_static_alias = bool(current_app.config.get("SPA_ALLOW_STATIC_ALIAS", False))
    if allow_static_alias and normalized.startswith("static/"):
        alt = normalized[len("static/") :]
        if alt and _is_static_file(alt):
            return _serve_static_asset(alt)

    return _serve_shell()
