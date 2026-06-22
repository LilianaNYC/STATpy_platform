"""Per-environment overrides for application settings.

The active environment is selected by the ``STATPY_ENV`` environment variable
(``dev`` by default). Each environment is a small dict of overrides applied on
top of the defaults defined in :mod:`config.settings`; this keeps environment
differences in one obvious place instead of scattered ``os.environ.get`` calls
across page and callback modules.
"""

from __future__ import annotations

import os

DEFAULT_ENVIRONMENT = "dev"

# Environment-specific overrides. Keys correspond to fields on
# :class:`config.settings.Settings`. Only values that differ from the defaults
# need to be listed here. Paths may be absolute or relative to the package
# root; relative paths are resolved against ``source_data_dir`` in settings.
ENVIRONMENTS: dict[str, dict[str, object]] = {
    "dev": {
        "debug": True,
    },
    "uat": {
        "debug": False,
    },
    "prod": {
        "debug": False,
    },
}


def active_environment() -> str:
    """Return the currently selected environment name."""
    return os.environ.get("STATPY_ENV", DEFAULT_ENVIRONMENT).strip().lower() or DEFAULT_ENVIRONMENT


def environment_overrides(environment: str | None = None) -> dict[str, object]:
    """Return the override dict for ``environment`` (or the active one)."""
    name = (environment or active_environment()).lower()
    return dict(ENVIRONMENTS.get(name, ENVIRONMENTS[DEFAULT_ENVIRONMENT]))
