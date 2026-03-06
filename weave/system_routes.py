"""Thin system-endpoint module.

This module intentionally keeps only true system-level endpoints.
SPA routing lives in weave.spa, and request/error hooks live in weave.security.
"""

from weave.health import healthz, metrics

__all__ = ["healthz", "metrics"]
