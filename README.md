# Weave

Weave is a Flask-based SPA backend/frontend service.

## Runtime architecture

- Web framework: Flask
- SPA serving: static files under `static/`
- Database strategy (chosen): **sqlite3 repository layer**
  - Runtime DB access uses `weave.core.get_db_connection()`
  - Convenience wrapper remains in `weave.db`
  - PostgreSQL migration utility: `scripts/migrate_sqlite_to_postgres.py`

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
- Operations setup: `docs/WEAVE_OPERATIONS_SETUP.md`
- DB structure notes: `docs/WEAVE_DB_STRUCTURE.md`
- PostgreSQL cutover checklist: `docs/WEAVE_POSTGRES_CUTOVER_CHECKLIST.md`
- Production quickstart: `docs/WEAVE_PRODUCTION_QUICKSTART.md`
- R2 checklist: `docs/WEAVE_R2_CHECKLIST.md`

## Scalable Upload Architecture

- Object storage abstraction:
  - `WEAVE_STORAGE_BACKEND=local|s3|r2|minio`
  - `WEAVE_S3_BUCKET`, `WEAVE_S3_ENDPOINT_URL`, `WEAVE_S3_REGION`
  - `WEAVE_S3_ACCESS_KEY_ID`, `WEAVE_S3_SECRET_ACCESS_KEY`
- CDN edge delivery:
  - `WEAVE_CDN_BASE_URL=https://cdn.example.com` (gallery/about public assets redirect)
- Media derivative queue (thumbnail/WebP):
  - `WEAVE_MEDIA_QUEUE_BACKEND=rq|local|inline`
  - `WEAVE_MEDIA_WORKER_COUNT=1..8` (for `local`)
  - `WEAVE_REDIS_URL=redis://...` and `WEAVE_MEDIA_QUEUE_NAME=weave-media` (for `rq`)
  - dedicated worker: `python scripts/run_rq_worker.py` (Windows: `powershell -File scripts/run_rq_worker.ps1`)
- Upload throughput knobs:
  - `UPLOAD_RATE_LIMIT_COUNT` / `UPLOAD_RATE_LIMIT_WINDOW_SEC`
  - `UPLOAD_BATCH_MAX_FILES`
  - `UPLOAD_GALLERY_THUMBNAIL_MODE=cover_only|always`

## PostgreSQL Transition (Staged)

- Runtime remains sqlite by default to preserve behavior.
- Runtime PostgreSQL adapter is available when `DATABASE_URL` starts with `postgres...`:
  - query placeholder compatibility (`?` -> `%s`) is handled at connection adapter layer
  - startup sqlite bootstrap is skipped in PostgreSQL mode
- Use migration utility for data copy:
  - `python scripts/migrate_sqlite_to_postgres.py --sqlite weave.db --postgres-dsn \"postgresql://weave:weave@localhost:5432/weave\"`
- Recommended production sequence:
  1. migrate into PostgreSQL
  2. run read-only validation and row-count checks
  3. switch runtime adapter in a dedicated branch after SQL placeholder compatibility migration

## Production Separation Guard

- For production, the recommended stack is:
  - `DATABASE_URL=postgresql://...`
  - `WEAVE_STORAGE_BACKEND=s3|r2|minio`
  - `WEAVE_MEDIA_QUEUE_BACKEND=rq`
- To make this mandatory at startup, set:
  - `WEAVE_REQUIRE_EXTERNAL_SERVICES=1`
- Example environment file:
  - `deploy/.env.production.example`
- Preflight check:
  - `python scripts/preflight_ops_check.py --env production`
- Core table count compare after migration:
  - `python scripts/compare_sqlite_postgres_counts.py --sqlite weave.db --postgres-dsn "postgresql://..."`
- PowerShell helpers:
  - `powershell -ExecutionPolicy Bypass -File .\scripts\ops_preflight_production.ps1`
  - `powershell -ExecutionPolicy Bypass -File .\scripts\ops_postgres_cutover.ps1 -PostgresDsn "postgresql://..."`

## Frontend Sync Rule

- Canonical frontend source is under `static/`.
- `scripts/sync_static_root.py` copies `static/*` into root mirror files (`index.html`, `styles.css`, `js/*`).
- Edit `static/` first, then run `python scripts/sync_static_root.py` (or `npm run sync:static-root`).
- Use `npm run check:sync-static-root` to detect accidental drift between `static/` and root mirror files.
- Use `npm run check:static-canonical` to ensure root mirror files were not edited ahead of `static/*`.

## Runtime Snapshot Bootstrap

- If `weave.db` or `uploads/` are missing on a fresh PC, startup now restores them from `storage/runtime_snapshot/` automatically.
- If an empty/blank sqlite runtime DB was already created on another PC, startup replaces that blank DB with the bundled snapshot automatically.
- Refresh the bundled snapshot from the current runtime with:
  - `python scripts/refresh_runtime_snapshot.py`
- This keeps a pull-only development PC aligned with the current local homepage state without manual DB/upload copying.

## Cache & Service Worker Policy

- `sw.js` is served with `Cache-Control: no-cache, no-store, must-revalidate`.
- Service worker registration uses a versioned URL (`/sw.js?v=<asset-version>`) derived from server-calculated asset version metadata.
- Static assets in service worker now use network-first strategy (fallback to cache only when offline) to prevent stale UI after deploy.
- `/static/*` alias fallback is disabled by default (`WEAVE_SPA_ALLOW_STATIC_ALIAS=false`) and should only be enabled for temporary compatibility.

## CSP Rollout

- `WEAVE_CSP_LEVEL=compat|strict` controls the target CSP policy level.
- `WEAVE_CSP_REPORT_ONLY=true` enables staged rollout with `Content-Security-Policy-Report-Only` before strict enforcement.

## Frontend Quality Checks

- `npm run lint:frontend`: frontend guardrails + CSS duplicate block detection.
- `npm run test:e2e:full`: full Playwright suite with line reporter.

## Windows Shell Note

- In PowerShell environments with execution-policy restrictions, use `npm.cmd` instead of `npm`.
- Example: `npm.cmd run test:e2e`
