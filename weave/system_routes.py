"""Thin system-endpoint facade.

Boundary contract for this module:
- Keep only true system-level handlers (for example: ``healthz``, ``metrics``).
- Do not add SPA fallback/static routing here (belongs in ``weave.spa``).
- Do not add authz, upload policy, post/event business logic here.
- Do not add request/error hook registration here (belongs in ``weave.security``).

This file is intentionally small to prevent route overgrowth over time.
"""

from weave.health import healthz, metrics

__all__ = ["healthz", "metrics"]
