# Weave

Weave is a Flask-based SPA backend/frontend service.

## Runtime architecture

- Web framework: Flask
- SPA serving: static files under `static/`
- Database strategy (chosen): **sqlite3 repository layer**
  - Runtime DB access uses `weave.core.get_db_connection()`
  - Convenience wrapper remains in `weave.db`

## Routing (SPA-safe)

Application-level SPA routes are intentionally limited to:

- `GET /` -> `root`
- `GET /<path:path>` -> `static_proxy`

This avoids duplicate registration and keeps API paths under `/api/*` unaffected.

## system_routes refactor map

`weave/system_routes.py` is now a thin facade. Focused concerns are split to:

- `weave/system_routes.py` -> thin system endpoints only (`healthz`, `metrics`)
- `weave/security_headers.py` -> `set_security_headers`
- `weave/csrf.py` -> `ensure_csrf_token`, `validate_csrf_if_needed`
- `weave/rate_limit.py` -> `validate_endpoint_rate_limit`
- `weave/security.py` -> request/error hook registration (`register_hooks`)
- `weave/authz.py` -> role/permission policy checks and decorators
- `weave/health.py` -> `/healthz`, `/metrics` handler implementations
- `weave/spa.py` -> SPA entry + fallback/static proxy (`root`, `static_proxy`)

Public endpoints and hook registration behavior remain unchanged.

## About SQLAlchemy files

`models.py` and `db_repository.py` are kept only for legacy compatibility (historical Alembic usage).
They are **not** the active runtime DB path.

## Docs

- Testing guide: `TESTING.md`
- Legacy response migration: `LEGACY_RESPONSE_MIGRATION.md`

## Frontend Sync Rule

- Canonical frontend source is under `static/`.
- `scripts/sync_static_root.py` copies `static/*` into root mirror files (`index.html`, `styles.css`, `js/*`).
- Edit `static/` first, then run `python scripts/sync_static_root.py` (or `npm run sync:static-root`).
- Use `npm run check:sync-static-root` to detect accidental drift between `static/` and root mirror files.

## Frontend Quality Checks

- `npm run lint:frontend`: frontend guardrails + CSS duplicate block detection.
- `npm run test:e2e:full`: full Playwright suite with line reporter.

## Windows Shell Note

- In PowerShell environments with execution-policy restrictions, use `npm.cmd` instead of `npm`.
- Example: `npm.cmd run test:e2e`
