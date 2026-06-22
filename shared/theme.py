"""App-shell theme constants and element ids shared across the app.

Previously these lived on :mod:`shell`, which forced dashboard callback
modules (e.g. the SAAS callbacks, which sync their charts to the active theme)
to ``import shell`` just to read the theme id/options. Hoisting them here lets
both the shell and any dashboard depend on a neutral shared module instead.
"""

from __future__ import annotations

# --- App-shell element ids -------------------------------------------------
URL_ID = "app-url"
PAGE_CONTENT_ID = "page-content"
APP_SHELL_ID = "app-shell"
APP_THEME_ID = "app-theme"

# --- Theme options ---------------------------------------------------------
THEME_OPTIONS = [
    {"label": "Light", "value": "light"},
    {"label": "Dark", "value": "dark"},
]
DEFAULT_THEME_VALUE = "light"
THEME_CLASS_NAMES = {
    "light": "theme-light",
    "dark": "theme-dark",
}


def normalize_theme_value(theme_value: str | None) -> str:
    """Return a valid theme value, falling back to the default."""
    valid_values = {option["value"] for option in THEME_OPTIONS}
    return theme_value if theme_value in valid_values else DEFAULT_THEME_VALUE
