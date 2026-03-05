"""Compatibility utilities module.

Historically some imports referenced `weave.utils` directly. Runtime helpers are
defined in `weave.core`; this module re-exports them for backward compatibility.
"""

from weave import core


def __getattr__(name):
    return getattr(core, name)


def __dir__():
    return sorted(set(globals().keys()) | set(dir(core)))
