"""Idempotent callback-registration guard.

Registry-driven wiring can call a module's ``register_callbacks`` more than
once if that module is imported from more than one place -- a common source of
Dash "callback already registered" / duplicate-output errors. This helper
makes every ``register_callbacks`` safe to call repeatedly.

The guard is keyed *per app* (markers are stored on the Dash app instance)
rather than as a module-level global, so re-calling on the same app is a
no-op while building a second, independent app (e.g. in tests) still registers
its callbacks correctly.
"""

from __future__ import annotations

_ATTR = "_statpy_registered_callbacks"


def already_registered(app, key: str) -> bool:
    """Return ``True`` if ``key`` was already registered on ``app``.

    On the first call for a given ``(app, key)`` this records the key and
    returns ``False`` so the caller proceeds to register; subsequent calls
    return ``True`` so the caller can return early.
    """
    registered = getattr(app, _ATTR, None)
    if registered is None:
        registered = set()
        setattr(app, _ATTR, registered)
    if key in registered:
        return True
    registered.add(key)
    return False
