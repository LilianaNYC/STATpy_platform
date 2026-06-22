"""Typed application settings, loaded once at startup.

Environment-specific values (data file locations, the active environment name,
debug flag, and feature flags) are resolved here and exposed as a single
frozen :data:`settings` object. Source-data files are bundled inside the
package (``source_data/``) so the app is self-contained regardless of where it
is checked out; the directory can be overridden with ``STATPY_SOURCE_DATA_DIR``.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field, replace
from pathlib import Path

from .environments import active_environment, environment_overrides

# Package root (the directory that contains this ``config/`` package).
PACKAGE_ROOT = Path(__file__).resolve().parent.parent


def _default_source_data_dir() -> Path:
    override = os.environ.get("STATPY_SOURCE_DATA_DIR")
    if override:
        return Path(override).expanduser().resolve()
    return PACKAGE_ROOT / "source_data"


@dataclass(frozen=True)
class Settings:
    """Resolved application settings.

    Data-access modules read paths from here instead of constructing them
    inline, so relocating ``source_data/`` or pointing at a different
    environment is a one-line change.
    """

    environment: str = "dev"
    debug: bool = True
    source_data_dir: Path = field(default_factory=_default_source_data_dir)

    # Feature flags live here rather than as scattered booleans in callbacks.
    feature_flags: dict[str, bool] = field(default_factory=dict)

    # --- Source-data file locations -------------------------------------
    @property
    def portfolio_file(self) -> Path:
        return self.source_data_dir / "portfolio.xlsx"

    @property
    def monitoring_thresholds_file(self) -> Path:
        return self.source_data_dir / "statpy_monitoring_thresholds.xlsm"

    @property
    def dummy_mev_data_file(self) -> Path:
        return self.source_data_dir / "dummy_mev_data.xlsx"

    @property
    def facilities_dummy_data_file(self) -> Path:
        return self.source_data_dir / "facilities_dummy_data.json"

    def feature_enabled(self, name: str, default: bool = False) -> bool:
        """Return whether feature flag ``name`` is enabled."""
        return bool(self.feature_flags.get(name, default))


def build_settings(environment: str | None = None) -> Settings:
    """Build a :class:`Settings` object for ``environment`` (or the active one)."""
    name = (environment or active_environment()).lower()
    overrides = environment_overrides(name)
    base = Settings(environment=name)

    source_data_dir = overrides.pop("source_data_dir", None)
    if source_data_dir is not None:
        base = replace(base, source_data_dir=Path(source_data_dir).expanduser().resolve())

    # Apply remaining scalar overrides that map to dataclass fields.
    field_overrides = {key: value for key, value in overrides.items() if hasattr(base, key)}
    return replace(base, **field_overrides) if field_overrides else base


# Built once at import time and shared across the app.
settings = build_settings()
