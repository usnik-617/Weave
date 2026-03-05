"""Compatibility utilities module.

Historically some imports referenced `weave.utils` directly. Runtime helpers are
defined in `weave.core`; this module re-exports them for backward compatibility.
"""

from weave.core import *  # noqa: F401,F403
