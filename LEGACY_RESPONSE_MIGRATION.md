# Legacy Response Migration Plan

## Goal
- Reduce mixed response contracts by migrating `*_legacy` payloads to `success_response` / `error_response` consistently.

## Scope Guardrails
- Do not change endpoint paths during migration.
- Keep status codes and semantic behavior identical.
- Migrate route groups incrementally with contract tests before/after each step.

## Milestones
1. Freeze
- New endpoints must not introduce `success_response_legacy` or `error_response_legacy`.
- Require contract tests for every new endpoint.

2. Inventory
- Track legacy usage in `weave/auth_routes.py`, `weave/admin_routes.py`, and user-role request legacy handlers.
- Record each endpoint's current payload shape and dependent frontend fields.

3. Adapter Phase
- Add temporary payload adapters in frontend only where unavoidable.
- Keep backend migration endpoint-by-endpoint to avoid broad breakage.

4. Route Family Migration
- Migrate auth routes first, then admin routes, then user role-request routes.
- For each family: convert handlers, update tests, and remove dead compatibility branches.

5. Cleanup
- Remove legacy helper exports and dead compatibility code from `weave/responses.py`.
- Keep one canonical API payload shape in docs and tests.

## Validation Checklist
- Pytest contracts pass for migrated routes.
- Frontend smoke checks pass for login, profile, role request, and admin approval flows.
- No `*_legacy` helper calls remain in migrated route families.

## Route Checklist
| Phase | Target module | Endpoints to migrate | Required tests | Done criteria |
|---|---|---|---|---|
| A1 | `weave/auth_routes.py` | `/api/auth/login`, `/api/auth/signup`, `/api/auth/me`, `/api/auth/logout` | `tests/test_auth_routes_contract.py`, `tests/test_auth_rate_limit_contract.py` | No `success_response_legacy`/`error_response_legacy` in auth routes |
| A2 | `weave/users_routes.py` | `/api/user/profile`, `/api/me/activity`, `/api/me/history`, `/api/role/request` | `tests/test_users_routes_contract.py`, `tests/test_auth_permission_contract.py` | Legacy payload adapter removed for user APIs |
| A3 | `weave/admin_routes.py` | `/api/admin/dashboard`, `/api/admin/pending-users`, role request approval/reject routes | `tests/test_auth_permission_contract.py`, dashboard smoke tests | Admin UI works with canonical payload shape |
| A4 | Shared contracts | Response helpers and remaining compatibility bridges | `tests/test_response_contract_guard.py` | `weave/responses.py` exports only canonical helpers for active APIs |

## Definition Of Done
- Each phase PR includes endpoint diff, contract test diff, and frontend consumer diff.
- No new legacy helper usages are introduced in changed files.
- CI passes: pytest contracts + Playwright smoke for affected flows.

## Current Progress
- 2026-03-08: Admin canonical migration started.
	- Converted to `success_response`: `/api/admin/pending-users`, `/api/admin/users/<id>/approve`
	- Added contract tests: `tests/test_admin_routes_contract.py`
