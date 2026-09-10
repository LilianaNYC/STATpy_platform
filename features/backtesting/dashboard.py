"""Backtesting dashboard metadata and callback-registration entrypoint."""

from __future__ import annotations

from ...shared.registration import already_registered
from ...shared.types import DashboardDefinition
from . import page_registry, stores


def register_callbacks(app) -> None:
    """Register every backtesting page's callbacks (idempotent)."""
    if already_registered(app, "dashboard:backtesting"):
        return
    for page in page_registry.PAGES:
        page.register_callbacks(app)


DASHBOARD = DashboardDefinition(
    key="backtesting",
    label="Backtesting",
    icon="🎯",
    base_path="/backtesting",
    register_callbacks=register_callbacks,
    pages=page_registry.PAGES,
    build_stores=stores.build_stores,
)
