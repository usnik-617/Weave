"""Compatibility shim for moved legacy handlers.

The legacy monolith has moved to `weave._legacy.legacy_handlers` and is not used by runtime routes.
Keep this file minimal to discourage accidental coupling.
"""

LEGACY_HANDLERS_RUNTIME_DISABLED = True

from weave._legacy.legacy_handlers import *  # noqa: F401,F403
