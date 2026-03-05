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

- `weave/security_headers.py` -> `set_security_headers`
- `weave/csrf.py` -> `ensure_csrf_token`, `validate_csrf_if_needed`
- `weave/rate_limit.py` -> `validate_endpoint_rate_limit`
- `weave/health.py` -> `/healthz`, `/metrics` handlers
- `weave/spa.py` -> `root`, `static_proxy`

Public endpoints and hook registration behavior remain unchanged.

## About SQLAlchemy files

`models.py` and `db_repository.py` are kept only for legacy compatibility (historical Alembic usage).
They are **not** the active runtime DB path.
